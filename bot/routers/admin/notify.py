from aiogram import Router, F
from datetime import datetime, timedelta
from aiogram.types import Message, InlineKeyboardButton, CallbackQuery
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters.callback_data import CallbackData
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest, TelegramRetryAfter
from aiogram_calendar import SimpleCalendar, SimpleCalendarCallback, get_user_locale
from loguru import logger
import asyncio

from pytz import timezone

from bot.common.general_states import GeneralStates
from bot.common.kbds.markup.admin_panel import AdminKeyboard
from bot.common.kbds.markup.cancel import get_cancel_kb
from bot.config import bot
from bot.db.dao import BroadcastDAO, UserDAO
from bot.common.utils.i18n import get_all_locales_for_key
from bot.config import translator_hub
from bot.db.models import BroadcastStatus
from bot.config import scheduler
from bot.db.schemas import SBroadcast
# Инициализация роутера
broadcast_router = Router()

# CallbackData для обработки подтверждения, выбора группы и кнопки "Без медиа"
class BroadcastCallback(CallbackData, prefix="broadcast"):
    action: str  # confirm, cancel, no_media, all_users, with_purchases, without_purchases

# Определение состояний для FSM
class BroadcastStates(StatesGroup):
    waiting_for_text = State()
    waiting_for_media = State()
    waiting_for_confirmation = State()
    waiting_for_date = State()
    waiting_for_time = State()

# Функция отправки сообщения пользователю
async def notify_user(user_id: int, text: str, media_id: str = None, media_type: str = None):
    """
    Отправляет сообщение пользователю с опциональным медиа.
    
    Args:
        user_id: ID пользователя
        text: Текст сообщения
        media_id: file_id медиафайла (опционально)
        media_type: Тип медиа ('photo' или 'video', опционально)
    """
    try:
        if media_id and media_type:
            if media_type == "photo":
                await bot.send_photo(
                    chat_id=user_id,
                    photo=media_id,
                    caption=text
                )
            elif media_type == "video":
                await bot.send_video(
                    chat_id=user_id,
                    video=media_id,
                    caption=text
                )
            else:
                logger.warning(f"Неподдерживаемый тип медиа: {media_type} для пользователя {user_id}")
                await bot.send_message(user_id, text)
        else:
            await bot.send_message(user_id, text)
        return True
    except TelegramForbiddenError:
        logger.warning(f"Пользователь {user_id} заблокировал бота. Сообщение не доставлено.")
        return False
    except TelegramBadRequest as e:
        logger.warning(f"Ошибка отправки сообщения пользователю {user_id}: {e}")
        return False
    except TelegramRetryAfter as e:
        logger.warning(f"Флуд-контроль для пользователя {user_id}. Ожидание {e.retry_after} секунд.")
        await asyncio.sleep(e.retry_after)
        return await notify_user(user_id, text, media_id, media_type)
    except Exception as e:
        logger.error(f"Неожиданная ошибка при отправке сообщения пользователю {user_id}: {e}")
        return False

# Функция рассылки
async def broadcast_message(user_ids: list[int], text: str, media_id: str = None, media_type: str = None):
    """
    Выполняет рассылку сообщений.
    
    Args:
        user_ids: Список ID пользователей
        text: Текст сообщения
        media_id: file_id медиафайла (опционально)
        media_type: Тип медиа ('photo' или 'video', опционально)
    """
    if not user_ids:
        logger.info("Список пользователей для рассылки пуст.")
        return 0, 0

    successful = 0
    failed = 0
    
    for user_id in user_ids:
        if await notify_user(user_id, text, media_id, media_type):
            successful += 1
        else:
            failed += 1
        await asyncio.sleep(0.1)  # Задержка для предотвращения флуда
    
    logger.info(f"Рассылка завершена. Успешно: {successful}, Неудачно: {failed}")
    return successful, failed


# Команда для старта рассылки
@broadcast_router.message(F.text == AdminKeyboard.get_kb_text().get('notify'))
async def start_broadcast(message: Message, state: FSMContext):
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(
            text="Все пользователи",
            callback_data=BroadcastCallback(action="all_users").pack()
        ),
        InlineKeyboardButton(
            text="С покупками или промокодами",
            callback_data=BroadcastCallback(action="with_purchases").pack()
        ),
        InlineKeyboardButton(
            text="Без покупок и промокодов",
            callback_data=BroadcastCallback(action="without_purchases").pack()
        )
    )
    builder.adjust(1) 
    await message.answer(
        "Выберите группу пользователей для рассылки:",
        reply_markup=builder.as_markup()
    )


@broadcast_router.callback_query(BroadcastCallback.filter(F.action.in_(['all_users', 'with_purchases', 'without_purchases'])))
async def process_broadcast_group(callback: CallbackQuery, callback_data: BroadcastCallback, state: FSMContext,i18n):
    await callback.message.delete()
    
    # Сохраняем выбранную группу
    await state.update_data(group=callback_data.action)
    
    await callback.message.answer(
        "Введите текст для рассылки:",
        reply_markup=get_cancel_kb(i18n)  
    )
    await state.set_state(BroadcastStates.waiting_for_text)

@broadcast_router.message(F.text.in_(get_all_locales_for_key(translator_hub, "keyboard-reply-cancel")), StateFilter(BroadcastStates))
async def cancel_broadcast(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(GeneralStates.admin_panel)
    await message.answer(
        "Рассылка отменена.",
        reply_markup=AdminKeyboard.build()
    )

@broadcast_router.message(F.text, StateFilter(BroadcastStates.waiting_for_text))
async def process_broadcast_text(message: Message, state: FSMContext):
    await state.update_data(broadcast_text=message.text)
    
    # Создание инлайн-кнопки "Без медиа"
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(
            text="Без медиа",
            callback_data=BroadcastCallback(action="no_media").pack()
        )
    )
    await message.answer(
        "Отправьте фото или видео, или нажмите 'Без медиа':",
        reply_markup=builder.as_markup()
    )
    await state.set_state(BroadcastStates.waiting_for_media)

# Получение медиа или обработка кнопки "Без медиа"
@broadcast_router.message(StateFilter(BroadcastStates.waiting_for_media), F.photo | F.video)
@broadcast_router.callback_query(StateFilter(BroadcastStates.waiting_for_media), BroadcastCallback.filter(F.action == "no_media"))
async def process_broadcast_media(event: Message | CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    
    # Определение объекта сообщения
    message = event if isinstance(event, Message) else event.message
    
    media_id = None
    media_type = None
    
    # Обработка в зависимости от типа события
    if isinstance(event, Message):
        if event.photo:
            media_type = "photo"
            media_id = event.photo[-1].file_id
        elif event.video:
            media_type = "video"
            media_id = event.video.file_id
        else:
            sent_message = await message.answer("Пожалуйста, отправьте фото, видео или нажмите 'Без медиа'.")
            await state.update_data(sent_message_id=sent_message.message_id)
            return
    elif isinstance(event, CallbackQuery):
        await event.message.delete()
        if event.data == BroadcastCallback(action="no_media").pack():
            pass  # Без медиа
        else:
            sent_message = await message.answer("Неверный коллбэк.")
            await state.update_data(sent_message_id=sent_message.message_id)
            return
    
    await state.update_data(media_id=media_id, media_type=media_type)
    
    # Формирование превью
    preview_text = f"Превью рассылки:\n\nТекст: {user_data['broadcast_text']}"
    if media_id:
        preview_text += f"\nМедиа: {media_type}"
    
    # Создание инлайн-кнопок для подтверждения
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(
            text="Подтвердить",
            callback_data=BroadcastCallback(action="confirm").pack()
        ),
        InlineKeyboardButton(
            text="Отменить",
            callback_data=BroadcastCallback(action="cancel").pack()
        ),
        InlineKeyboardButton(
            text="Добавить время рассылки",
            callback_data=BroadcastCallback(action="date").pack()
        )
    )
    builder.adjust(1)  
    # Отправка превью
    if media_id and media_type:
        if media_type == "photo":
            sent_message = await message.answer_photo(
                photo=media_id,
                caption=preview_text,
                reply_markup=builder.as_markup()
            )
        elif media_type == "video":
            sent_message = await message.answer_video(
                video=media_id,
                caption=preview_text,
                reply_markup=builder.as_markup()
            )
        else:
            sent_message = await message.answer(
                text=preview_text,
                reply_markup=builder.as_markup()
            )
    else:
        sent_message = await message.answer(
            text=preview_text,
            reply_markup=builder.as_markup()
        )
    
    await state.update_data(sent_message_id=sent_message.message_id)
    await state.set_state(BroadcastStates.waiting_for_confirmation)

@broadcast_router.callback_query(BroadcastStates.waiting_for_confirmation, BroadcastCallback.filter(F.action == "date"))
async def process_broadcast_date(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    tz = timezone("Europe/Moscow")
    today = datetime.now(tz).replace(tzinfo=None)
    yesterday = today - timedelta(days=1)
    next_month = (yesterday.replace(day=1) + timedelta(days=32)).replace(day=1)
    calendar = SimpleCalendar(
        show_alerts=True
    )
    calendar.set_dates_range(yesterday, next_month)
    await callback.message.answer(
        "Выберите дату рассылки:",
        reply_markup=await calendar.start_calendar()
    )
    await state.set_state(BroadcastStates.waiting_for_date)

@broadcast_router.callback_query(SimpleCalendarCallback.filter())
async def process_simple_calendar(callback_query: CallbackQuery, callback_data: CallbackData, state: FSMContext):
    tz = timezone("Europe/Moscow")
    today = datetime.now(tz).replace(tzinfo=None)
    yesterday = today - timedelta(days=1)
    next_month = (yesterday.replace(day=1) + timedelta(days=32)).replace(day=1)
    calendar = SimpleCalendar(
        show_alerts=True
    )
    calendar.set_dates_range(yesterday, next_month)

    selected, date = await calendar.process_selection(callback_query, callback_data)
    if selected:
        await state.update_data(selected_date=date.strftime("%Y-%m-%d"))
        await callback_query.message.answer(
            f"Вы выбрали дату: {date.strftime('%d.%m.%Y')}\n"
            "Введите время рассылки в формате HH:MM (по Москве):"
        )
        await state.set_state(BroadcastStates.waiting_for_time)

@broadcast_router.message(StateFilter(BroadcastStates.waiting_for_time))
async def process_time(message: Message, state: FSMContext, session_without_commit):
    try:
        parts = message.text.strip().split(":")
        if len(parts) != 2:
            raise ValueError
        hour, minute = map(int, parts)
    except ValueError:
        await message.answer("Неверный формат. Введите время как HH:MM, например 14:30")
        return

    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        await message.answer("Неверное время. Час должен быть от 0 до 23, минуты — от 0 до 59.")
        return

    user_data = await state.get_data()
    date = datetime.strptime(user_data["selected_date"], "%Y-%m-%d")

    tz = timezone("Europe/Moscow")
    now = datetime.now(tz)

    # создаём datetime с учётом выбранной даты и введённого времени
    run_time = tz.localize(
        date.replace(hour=hour, minute=minute, second=0, microsecond=0, tzinfo=None)
    )

    # 🚨 проверка на прошлое
    if run_time <= now:
        await message.answer("Указанное время уже прошло. Выберите время позже текущего момента.",reply_markup=AdminKeyboard.build())
        await state.clear()
        await state.set_state(GeneralStates.admin_panel)
        return

    text = user_data["broadcast_text"]
    media_id = user_data.get("media_id")
    media_type = user_data.get("media_type")
    group = user_data.get("group")

    # сохраняем рассылку в БД
    broadcast_dao = BroadcastDAO(session_without_commit)
    broadcast = await broadcast_dao.add(
        SBroadcast(
            text=text,
            media_id=media_id,
            media_type=media_type,
            group=group,
            run_time=run_time,
            status=BroadcastStatus.SCHEDULED,
            created_by=message.from_user.id
        )
    )
    # сразу же регистрируем задачу в APScheduler
    scheduler.add_job(
        run_broadcast_job,
        "date",
        run_date=run_time,
        args=[broadcast.id],
        id=f"broadcast_{broadcast.id}"
    )
    await session_without_commit.commit()
    await message.answer(
        f"Рассылка запланирована на {run_time.strftime('%d.%m.%Y %H:%M (МСК)')}",
        reply_markup=AdminKeyboard.build()
    )
    await state.clear()
    await state.set_state(GeneralStates.admin_panel)


async def run_broadcast_job(broadcast_id: int):
    """
    Выполняет рассылку по ID из БД
    """
    from bot.db.database import async_session_maker
    async with async_session_maker() as session:
        broadcast_dao = BroadcastDAO(session)
        user_dao = UserDAO(session)

        broadcast = await broadcast_dao.find_one_or_none_by_id(broadcast_id)
        if not broadcast or broadcast.status != BroadcastStatus.SCHEDULED:
            return

        # Сохраняем все нужные поля локально, чтобы не вызывать lazy-load после await
        b_id = broadcast.id
        b_group = broadcast.group
        b_text = broadcast.text
        b_media_id = broadcast.media_id
        b_media_type = broadcast.media_type
        b_created_by = broadcast.created_by
        # выборка пользователей
        if b_group == "all_users":
            user_ids = [user.id for user in await user_dao.find_all()]
        elif b_group == "with_purchases":
            user_ids = [user.id for user in await user_dao.get_users_with_payments()]
        elif b_group == "without_purchases":
            user_ids = [user.id for user in await user_dao.get_users_without_payments()]
        else:
            return

        successful, failed = await broadcast_message(
            user_ids=user_ids,
            text=b_text,
            media_id=b_media_id,
            media_type=b_media_type,
        )

        # обновляем статус, используя локальную переменную id (не access через detached объект)
        await broadcast_dao.update_status(b_id, BroadcastStatus.SENT)
        await bot.send_message(
            b_created_by,
            f"Рассылка {b_id} завершена. Успешно: {successful}, Неудачно: {failed}",
        )
        logger.info(f"Рассылка {b_id} завершена. Успешно: {successful}, Неудачно: {failed}")


# Обработка подтверждения через инлайн-кнопки
@broadcast_router.callback_query(BroadcastStates.waiting_for_confirmation, BroadcastCallback.filter(F.action.in_(['confirm', 'cancel'])))
async def process_broadcast_confirmation(callback: CallbackQuery, callback_data: BroadcastCallback, state: FSMContext, session_without_commit):
    user_data = await state.get_data()
    await callback.message.delete()
    if callback_data.action == "cancel":
        await callback.message.answer("Рассылка отменена.", reply_markup=AdminKeyboard.build())
        await state.clear()
        await state.set_state(GeneralStates.admin_panel)
        return
    
    text = user_data["broadcast_text"]
    media_id = user_data.get("media_id")
    media_type = user_data.get("media_type")
    group = user_data.get("group")
    
    # Выборка пользователей в зависимости от группы
    user_dao = UserDAO(session_without_commit)
    if group == "all_users":
        user_ids = [user.id for user in await user_dao.find_all()]
    elif group == "with_purchases":
        user_ids = [user.id for user in await user_dao.get_users_with_payments()]
    elif group == "without_purchases":
        user_ids = [user.id for user in await user_dao.get_users_without_payments()]
    else:
        await callback.message.answer("Выбрана неверная группа.")
        await state.clear()
        await state.set_state(GeneralStates.admin_panel)
        return
    
    successful, failed = await broadcast_message(
        user_ids=user_ids,
        text=text,
        media_id=media_id,
        media_type=media_type
    )
    
    await callback.message.answer(f"Рассылка завершена! Успешно: {successful}, Неудачно: {failed}", reply_markup=AdminKeyboard.build())
    await state.clear()
    await state.set_state(GeneralStates.admin_panel)


async def resume_scheduled_broadcasts(tz_name: str = "Europe/Moscow", immediate_delay_seconds: int = 5):
    """
    При старте приложения восстанавливает job'ы рассылок из БД для всех Broadcast.status == SCHEDULED.
    Если run_time в прошлом — заменяет run_date на текущее время + immediate_delay_seconds.
    Параметры:
      - async_session_maker: фабрика асинхронных сессий SQLAlchemy
      - scheduler: экземпляр APScheduler
      - tz_name: имя таймзоны (по умолчанию Europe/Moscow)
      - immediate_delay_seconds: задержка для немедленного выполнения просроченных задач
    """
    from bot.db.database import async_session_maker

    tz = timezone(tz_name)
    now = datetime.now(tz)

    try:
        async with async_session_maker() as session:
            dao = BroadcastDAO(session)
            broadcasts = await dao.get_scheduled_broadcasts()
            logger.info(f"Resuming {len(broadcasts)} scheduled broadcasts")
            for b in broadcasts:
                try:
                    job_id = f"broadcast_{b.id}"
                    # если job уже зарегистрирована — пропустить
                    if scheduler.get_job(job_id):
                        continue

                    run_time = b.run_time
                    if run_time is None:
                        logger.warning(f"Broadcast {b.id} has no run_time, skipping")
                        continue

                    # привести к timezone-aware (предполагаем, что naive время в MSK)
                    if run_time.tzinfo is None:
                        run_time = tz.localize(run_time)

                    # если время в прошлом — выполнить почти сразу
                    if run_time <= now:
                        run_date = now + timedelta(seconds=immediate_delay_seconds)
                        logger.info(f"Broadcast {b.id} run_time in past, scheduling now (+{immediate_delay_seconds}s)")
                    else:
                        run_date = run_time

                    scheduler.add_job(
                        run_broadcast_job,
                        "date",
                        run_date=run_date,
                        args=[b.id],
                        id=job_id
                    )
                except Exception as e:
                    logger.exception(f"Failed to schedule broadcast {getattr(b, 'id', 'unknown')}: {e}")
    except Exception as e:
        from loguru import logger
        logger.exception(f"Failed to resume scheduled broadcasts: {e}")