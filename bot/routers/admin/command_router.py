from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import StateFilter
from bot.common.kbds.markup.admin_panel import AdminKeyboard
from bot.db.dao import UserDAO
from bot.db.models import User
from loguru import logger
from bot.db.redis import sync_redis_client
from bot.common.general_states import GeneralStates
from bot.db.schemas import SUser
import asyncio
from redis import Redis
from bot.config import settings, admins, scheduler
from bot.common.tasks.monitor_notification import check_for_user
from bot.common.rq_queue_maintenance import (
    HINT_QUEUE_NAMES,
    QUEUE_TITLES,
    cleanup_rq_queues,
    get_live_worker_stats,
)
import uuid
from sqlalchemy import delete as sqlalchemy_delete
from bot.db.models import UserContentCard

commands_router = Router()


class MonitorStates(StatesGroup):
    waiting_threshold = State()


@commands_router.message(F.text.startswith("/makeadmin"))
async def make_admin(message: Message, session_without_commit):
    try:
        parts = message.text.split()
        if len(parts) != 2 or not parts[1].isdigit():
            return await message.answer("Использование: /makeadmin <user_id>")

        user_id = int(parts[1])

        user_dao = UserDAO(session_without_commit)
        user = await user_dao.find_one_or_none_by_id(user_id)

        if not user:
            return await message.answer(f"Пользователь с ID {user_id} не найден.")

        user.role = User.Role.ADMIN.value
        await session_without_commit.commit()

        await message.answer(f"Пользователь с ID {user_id} теперь администратор.")
    except Exception as e:
        logger.error(f"Ошибка при выполнении команды /makeadmin: {e}")
        await message.answer("Произошла ошибка при выполнении команды.")


@commands_router.message(F.text.startswith("/delete_user"))
async def make_admin(message: Message, session_without_commit):
    try:
        parts = message.text.split()
        if len(parts) != 2 or not parts[1].isdigit():
            return await message.answer("Использование: /makeadmin <user_id>")

        user_id = int(parts[1])

        user_dao = UserDAO(session_without_commit)
        user = await user_dao.find_one_or_none_by_id(user_id)

        if not user:
            return await message.answer(f"Пользователь с ID {user_id} не найден.")

        await user_dao.delete(SUser(id=user_id))
        await session_without_commit.commit()

        await message.answer(f"Пользователь с ID {user_id} удален")
    except Exception as e:
        logger.error(f"Ошибка при выполнении команды /delete_user: {e}")
        await message.answer("Произошла ошибка при выполнении команды.")


@commands_router.message(F.text.startswith("/listusers"))
async def list_users(message: Message, session_without_commit):
    try:
        user_dao = UserDAO(session_without_commit)
        users: list[User] = await user_dao.find_all()

        if not users:
            return await message.answer("Нет зарегистрированных пользователей.")

        user_list = "\n".join(
            [
                f"ID: <code>{user.id}</code>, Username: <code>{user.username or 'нет'}</code>, Role: {user.role}"
                for user in users
            ]
        )
        await message.answer(f"Список пользователей:\n{user_list}")
    except Exception as e:
        logger.error(f"Ошибка при выполнении команды /listusers: {e}")
        await message.answer("Произошла ошибка при выполнении команды.")


@commands_router.message(F.text.startswith("/clear_user_cards"))
async def clear_user_cards(message: Message, session_without_commit):
    try:
        parts = message.text.split()
        if len(parts) != 2 or not parts[1].isdigit():
            return await message.answer("Использование: /clear_user_cards <user_id>")

        user_id = int(parts[1])
        result = await session_without_commit.execute(
            sqlalchemy_delete(UserContentCard).where(UserContentCard.user_id == user_id)
        )
        await session_without_commit.commit()
        deleted_count = int(result.rowcount or 0)
        await message.answer(
            f"Удалено карточек у пользователя {user_id}: {deleted_count}"
        )
    except Exception as e:
        logger.error(f"Ошибка при выполнении команды /clear_user_cards: {e}")
        await message.answer("Произошла ошибка при выполнении команды.")


@commands_router.message(F.text == "/clear_rq_cache")
async def clear_rq_cache(message: Message):
    """Очищает кэш мониторинга и «мёртвые» записи воркеров/очередей RQ."""
    try:
        if message.from_user is None or message.from_user.id not in admins:
            return await message.reply("Доступ запрещен.")

        redis_conn = Redis.from_url(settings.REDIS_URL, decode_responses=False)
        result = await asyncio.to_thread(cleanup_rq_queues, redis_conn)

        lines = [
            "✅ Очистка RQ выполнена.",
            f"Кэш worker_count: {'удалён' if result['cache_deleted'] else 'не был в Redis'}.",
            (
                "Живых обработчиков: "
                f"{result['alive_before']} → {result['alive_after']}"
            ),
            (
                "Записей в реестре: "
                f"{result['workers_before_global']} → {result['workers_after_global']}"
            ),
        ]
        if result.get("stale_removed_from_registry"):
            lines.append(
                f"Удалено неактуальных записей: {result['stale_removed_from_registry']}"
            )
        for qname in HINT_QUEUE_NAMES:
            stats = result["per_queue"][qname]
            live = result.get("per_queue_live", {}).get(qname, {})
            title = QUEUE_TITLES.get(qname, qname)
            lines.append(
                f"{title}: реестр {stats['before']} → {stats['after']}, "
                f"ожидание={live.get('waiting', '—')}, активно={live.get('active', '—')}"
            )

        await message.answer("\n".join(lines))
        logger.info("RQ cache cleanup by admin {}: {}", message.from_user.id, result)
    except Exception as e:
        logger.exception(f"Ошибка при выполнении команды /clear_rq_cache: {e}")
        await message.answer("Произошла ошибка при очистке кэша RQ.")


@commands_router.message(F.text.startswith("/clear_active_jobs"))
async def clear_active_jobs(message: Message):
    try:
        parts = message.text.split()
        if len(parts) != 2 or not parts[1].isdigit():
            return await message.answer("Использование: /clear_active_jobs <user_id>")

        user_id = int(parts[1])

        # Удаляем все активные задачи для пользователя
        key = f"user_active_jobs:{user_id}"
        active_jobs = sync_redis_client.smembers(key)
        if active_jobs:
            sync_redis_client.delete(key)
            await message.answer(
                f"Удалено активных задач для пользователя {user_id}: {len(active_jobs)}"
            )
            logger.info(f"Cleared active jobs for user {user_id}: {active_jobs}")
        else:
            await message.answer(f"У пользователя {user_id} нет активных задач.")
    except Exception as e:
        logger.error(f"Ошибка при выполнении команды /clear_active_jobs: {e}")
        await message.answer("Произошла ошибка при выполнении команды.")


@commands_router.callback_query(F.data == "monitor:set_notification")
async def set_notification_callback(callback: CallbackQuery, state: FSMContext):
    """Обработка нажатия на кнопку установки уведомления."""
    try:
        if callback.from_user is None or callback.from_user.id not in admins:
            return await callback.answer("Доступ запрещен.", show_alert=True)

        await state.set_state(MonitorStates.waiting_threshold)
        await callback.message.answer(
            "Введите значение кол-ва активных обработчиков, при котором нужно отправить уведомление.\n"
            "Пример: 10"
        )
        await callback.answer()
    except Exception as e:
        logger.exception(f"Ошибка в set_notification_callback: {e}")
        await callback.answer("Ошибка при установке уведомления.", show_alert=True)

@commands_router.message(F.text == AdminKeyboard.admin_text_kb['monitor'])
async def monitor(message: Message, state: FSMContext):
    """Показывает текущую загрузку RQ очередей и количество живых воркеров. Только для админов."""
    try:
        if message.from_user is None or message.from_user.id not in admins:
            return await message.reply("Доступ запрещен.")

        redis_conn = Redis.from_url(settings.REDIS_URL, decode_responses=False)

        stats = await asyncio.to_thread(
            get_live_worker_stats,
            redis_conn,
            cleanup_registry=True,
            include_worker_details=True,
        )

        lines: list[str] = ["Мониторинг очередей:"]
        for qname in HINT_QUEUE_NAMES:
            qstats = stats.per_queue[qname]
            title = QUEUE_TITLES.get(qname, qname)
            lines.append(
                f"{title}: ожидание={qstats['waiting']}, активно={qstats['active']}"
            )

        lines.append("")
        lines.append(f"Обработчиков (живых): {stats.alive_count}")
        if stats.registry_before != stats.registry_after or stats.stale_removed_from_registry:
            lines.append(
                "Записей в реестре: "
                f"{stats.registry_before} → {stats.registry_after}"
            )
        if stats.stale_removed_from_registry:
            lines.append(
                f"Удалено неактуальных записей: {stats.stale_removed_from_registry}"
            )
        lines.append(
            f"Итого: {stats.total_waiting} в ожидании, {stats.total_active} активных задач"
        )

        if stats.workers:
            lines.append("")
            lines.append("Живые обработчики:")
            for item in sorted(stats.workers, key=lambda w: (w["hostname"], str(w["pid"]))):
                lines.append(
                    f"• {item['name']} ({item['hostname']}:{item['pid']}) "
                    f"[{item['state']}] — {item['queues']}, hb {item['last_heartbeat']}"
                )

        keyboard = InlineKeyboardBuilder()
        keyboard.button(
            text="🔔 Установить уведомление", callback_data="monitor:set_notification"
        )
        keyboard.adjust(1)

        await message.answer("\n".join(lines), reply_markup=keyboard.as_markup())
    except Exception as e:
        logger.exception(f"Ошибка в /monitor: {e}")
        await message.answer("Ошибка при получении статуса очередей.")


@commands_router.message(StateFilter(MonitorStates.waiting_threshold))
async def process_threshold(message: Message, state: FSMContext):
    """Обработка ввода значения порога."""
    try:
        if not message.text.isdigit():
            await message.answer("Пожалуйста, введите число.")
            return

        threshold = int(message.text)
        user_id = message.from_user.id

        # Регистрируем задачу в локальном scheduler (в том же процессе), job_id позволяет обновлять задачу
        job_id = f"monitor_notification:{user_id}"
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)
        scheduler.add_job(
            check_for_user,
            "interval",
            seconds=30,
            args=[user_id, threshold],
            id=job_id,
            replace_existing=True,
            coalesce=True,
        )

        notification_key = f"monitor:notification:{user_id}"
        sync_redis_client.set(notification_key, threshold)

        await message.answer(
            f"✅ Уведомление установлено!\n"
            f"Вы получите сообщение когда кол-во активных воркеров станет равно {threshold}."
        )
        logger.info(
            f"Monitor notification set for user {user_id}: threshold={threshold}"
        )
        await state.clear()
        await state.set_state(GeneralStates.admin_panel)
    except Exception as e:
        logger.exception(f"Ошибка в process_threshold: {e}")
        await message.answer("Ошибка при сохранении уведомления.")
        await state.set_state(GeneralStates.admin_panel)