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
from rq import Queue, Worker
from rq.registry import StartedJobRegistry
from bot.config import settings, admins, scheduler
from bot.common.tasks.monitor_notification import check_for_user
import uuid

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
    """Показывает текущую загрузку RQ очередей и количество воркеров. Только для админов."""
    try:
        if message.from_user is None or message.from_user.id not in admins:
            return await message.reply("Доступ запрещен.")

        redis_conn = Redis.from_url(settings.REDIS_URL, decode_responses=False)
        queue_names = ["backgammon_analysis", "backgammon_batch_analysis"]

        total_waiting = 0
        total_active = 0
        lines: list[str] = []
        names = {
            "backgammon_analysis": "Одиночные игры",
            "backgammon_batch_analysis": "Пакеты игр",
        }
        for qname in queue_names:
            q = Queue(qname, connection=redis_conn)
            registry = StartedJobRegistry(queue=q)
            active = len(registry)
            total_active += active
            lines.append(f"{names.get(qname, qname)}: Активно={active}")

        worker_count = await asyncio.to_thread(
            lambda: len(Worker.all(connection=redis_conn))
        )

        msg = "Мониторинг очередей: \n" + "\n".join(lines)
        total_waiting = worker_count - total_active
        msg += f"\n\nВсего обработчиков: {worker_count}\nВсего в ожидании: {total_waiting}, активно: {total_active}"

        # Создаем кнопку для установки уведомления
        keyboard = InlineKeyboardBuilder()
        keyboard.button(
            text="🔔 Установить уведомление", callback_data="monitor:set_notification"
        )
        keyboard.adjust(1)

        await message.answer(msg, reply_markup=keyboard.as_markup())
        await state.clear()
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