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
import re

from pytz import timezone

from bot.common.general_states import GeneralStates
from bot.common.kbds.inline.paginate import PaginatedCallback, PaginatedCheckboxCallback, get_paginated_checkbox_keyboard, get_paginated_keyboard
from bot.common.kbds.markup.admin_panel import AdminKeyboard
from bot.common.kbds.markup.cancel import get_cancel_kb
from bot.config import bot
from bot.db.dao import BroadcastDAO, UserDAO, UserGroupDAO
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

class BroadcastListCallback(CallbackData, prefix="broadcast_list"):
    action: str  # show_users, cancel_broadcast
    broadcast_id: int

# Определение состояний для FSM
class BroadcastStates(StatesGroup):
    waiting_broadcase_name = State()
    waiting_for_text = State()
    waiting_for_media = State()
    waiting_for_confirmation = State()
    waiting_for_date = State()
    waiting_for_time = State()
    waiting_for_targets = State()

    
group_ru={
    'user_group':'Кастомные группы',
    'without_purchases':'Без покупок',
    'all_users':'Все пользователи',
    'with_purchases':'Пользователи с покупками',
    'specific':'Таргетированная рассылка'
}
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

def build_notify_kb():
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
        ),
        InlineKeyboardButton(
            text="Конкретные пользователи",
            callback_data=BroadcastCallback(action="specific").pack()
        ),
        InlineKeyboardButton(
            text="Кастомные группы",
            callback_data=BroadcastCallback(action="user_group").pack()
        ),
        InlineKeyboardButton(
            text="Текущие рассылки",
            callback_data=BroadcastCallback(action="current_broadcast").pack()
        ),
        InlineKeyboardButton(
            text="Архив рассылок",
            callback_data=BroadcastCallback(action="archive_broadcast").pack()
        )
    )
    builder.adjust(1) 
    return builder.as_markup()


# Команда для старта рассылки
@broadcast_router.message(F.text == AdminKeyboard.get_kb_text().get('notify'))
async def start_broadcast(message: Message, state: FSMContext):
    await message.answer(
        "Выберите группу пользователей для рассылки:",
        reply_markup=build_notify_kb()
    )

@broadcast_router.callback_query(BroadcastListCallback.filter(F.action == "archive_back"))
@broadcast_router.callback_query(BroadcastCallback.filter(F.action == 'archive_broadcast'))
async def process_archive_broadcast(callback: CallbackQuery, callback_data: BroadcastCallback, state: FSMContext,session_without_commit):
    await callback.message.delete()
    broadcast_dao = BroadcastDAO(session_without_commit)
    broadcasts = await broadcast_dao.get_unique_content_broadcasts()
    await callback.message.answer(
        'Архив рассылок', reply_markup=get_paginated_keyboard(
            items=broadcasts,
            context='archive_broadcasts',
            get_display_text=lambda broadcast: f"{broadcast.name}",
            get_item_id=lambda broadcast: broadcast.id,
            page=0,
            items_per_page=7,
        )
    )

@broadcast_router.callback_query(PaginatedCallback.filter(F.context == 'archive_broadcasts'))
async def process_archive_paginate(callback: CallbackQuery, callback_data: PaginatedCallback, state: FSMContext, i18n, session_without_commit):
    match callback_data.action:
        case "select":
            await callback.message.delete()
            broadcast_dao = BroadcastDAO(session_without_commit)
            user_dao = UserDAO(session_without_commit)
            broadcast = await broadcast_dao.find_one_or_none_by_id(callback_data.item_id)
            if broadcast.media_type in ['specific','user_group']:
                group_msg = 'Кому:\n'
                users_ids = await broadcast_dao.get_recipients_for_broadcast(broadcast.id)
                for user_id in users_ids:
                    user = await user_dao.find_one_or_none_by_id(user_id)
                    group_msg += f'- {user.admin_insert_name or user.username or str(user.id)}\n'
            else:
                group_msg = f"Тип: {group_ru.get(broadcast.group)}\n"
                
            # Формируем текст для каждой рассылки
            broadcast.run_time = broadcast.run_time.replace(hour=broadcast.run_time.hour+3)
            info = f"Имя рассылки: <b>{broadcast.name}</b>\n"
            info += f"Текст: {broadcast.text[:30]}{'...' if len(broadcast.text) > 30 else ''}\n"
            info += f"Медиа: {'есть' if broadcast.media_id else 'нет'}\n"
            info += group_msg
            info += f"Время: {broadcast.run_time.strftime('%d.%m.%Y %H:%M (МСК)') if broadcast.run_time else 'без времени'}\n"
            info += f"Статус: Отправленно\n"

            builder = InlineKeyboardBuilder()
            builder.add(
                InlineKeyboardButton(
                    text="Повторить рассылку",
                    callback_data=BroadcastListCallback(action="archive_repeat", broadcast_id=broadcast.id).pack()
                )
            )
            builder.add(
                InlineKeyboardButton(
                    text="Назад",
                    callback_data=BroadcastListCallback(action="archive_back", broadcast_id=broadcast.id).pack()
                )
            )
            builder.adjust(1)
            
            match broadcast.media_type:
                case 'photo':
                    await callback.message.answer_photo(photo=broadcast.media_id, caption=info, reply_markup=builder.as_markup())
                case 'video':
                    await callback.message.answer_video(photo=broadcast.media_id, caption=info, reply_markup=builder.as_markup())
                case _:
                    await callback.message.answer(info, reply_markup=builder.as_markup())
            await asyncio.sleep(0.1)
        case "prev" | "next":
            keyboard = get_paginated_keyboard(
                items=await BroadcastDAO(session_without_commit).get_unique_content_broadcasts(),
                context="archive_broadcasts",
                get_display_text=lambda broadcast: f"{broadcast.name}",
                get_item_id=lambda broadcast: broadcast.id,
                page=callback_data.page,
                items_per_page=7,
            )
            await callback.message.edit_reply_markup(reply_markup=keyboard)

@broadcast_router.callback_query(BroadcastListCallback.filter(F.action == 'archive_repeat'))
async def process_archive_repeat(callback: CallbackQuery, callback_data: BroadcastListCallback, state: FSMContext, session_without_commit):
    await callback.message.delete()
    broadcast_dao = BroadcastDAO(session_without_commit)
    broadcast = await broadcast_dao.find_one_or_none_by_id(callback_data.broadcast_id)
    users = await broadcast_dao.get_recipients_for_broadcast(broadcast.id)
    # сохраняем в state все нужные данные
    await state.update_data(
        group=broadcast.group,
        target_user_ids=users,
        broadcast_text=broadcast.text,
        media_id=broadcast.media_id,
        user_group_id=broadcast.group_id,
        media_type=broadcast.media_type,
        broadcast_name=f"{broadcast.name} (повтор)"
    )

    preview_text = f"Повтор рассылки:\n\n{broadcast.text[:100]}"
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text="Подтвердить", callback_data=BroadcastCallback(action="confirm").pack()),
        InlineKeyboardButton(text="Отменить", callback_data=BroadcastCallback(action="cancel").pack())
    )
    builder.add(
        InlineKeyboardButton(text="Добавить время", callback_data=BroadcastCallback(action="date").pack())
    )
    builder.adjust(1)

    if broadcast.media_id and broadcast.media_type == "photo":
        await callback.message.answer_photo(broadcast.media_id, caption=preview_text, reply_markup=builder.as_markup())
    elif broadcast.media_id and broadcast.media_type == "video":
        await callback.message.answer_video(broadcast.media_id, caption=preview_text, reply_markup=builder.as_markup())
    else:
        await callback.message.answer(preview_text, reply_markup=builder.as_markup())

    await state.set_state(BroadcastStates.waiting_for_confirmation)

@broadcast_router.callback_query(BroadcastCallback.filter(F.action.in_(['all_users', 'with_purchases', 'without_purchases'])))
async def process_broadcast_group(callback: CallbackQuery, callback_data: BroadcastCallback, state: FSMContext,i18n):
    await callback.message.delete()
    
    # Сохраняем выбранную группу
    await state.update_data(group=callback_data.action)
    
    await callback.message.answer(
        "Придумайте название рассылки:",
        reply_markup=get_cancel_kb(i18n)  
    )
    await state.set_state(BroadcastStates.waiting_broadcase_name)

@broadcast_router.callback_query(BroadcastCallback.filter(F.action == "user_group"))
async def process_broadcast_user_group(callback: CallbackQuery, state: FSMContext, i18n, session_without_commit):
    await callback.message.delete()
    group_dao = UserGroupDAO(session_without_commit)
    groups = await group_dao.find_all()
    await callback.message.answer(
        "Выберите группу для рассылки:",
        reply_markup=get_paginated_keyboard(
            items=groups,
            context="broadcast_user_group",
            get_display_text=lambda group: f"{group.name}",
            get_item_id=lambda group: group.id,
            page=0,
            items_per_page=5,
            with_back_butn=True
        )
    )
    await state.set_state(GeneralStates.admin_panel)

@broadcast_router.callback_query(PaginatedCallback.filter(F.context == "broadcast_user_group"))
async def handle_broadcast_user_group_selection(callback: CallbackQuery, callback_data: PaginatedCallback, state: FSMContext, i18n, session_without_commit):
    match callback_data.action:
        case "select":
            await callback.message.delete()
            group_id = callback_data.item_id
            group_dao = UserGroupDAO(session_without_commit)
            group = await group_dao.find_one_or_none_by_id(group_id)
            await state.update_data(group="user_group", user_group_id=group_id)
            await callback.message.answer(
                f"Вы выбрали группу: {group.name}\n\nПридумайте название рассылки:",
                reply_markup=get_cancel_kb(i18n)
            )
            await state.set_state(BroadcastStates.waiting_broadcase_name)
        case "prev" | "next":
            keyboard = get_paginated_keyboard(
                items=await UserGroupDAO(session_without_commit).find_all(),
                context="broadcast_user_group",
                get_display_text=lambda group: f"{group.name}",
                get_item_id=lambda group: group.id,
                page=callback_data.page,
                items_per_page=5,
            )
            await callback.message.edit_reply_markup(reply_markup=keyboard)
        case "back":
            await callback.message.delete()
            await callback.message.answer(
                "Выберите группу пользователей для рассылки:",
                reply_markup=build_notify_kb()
            )
            await state.set_state(GeneralStates.admin_panel)

@broadcast_router.callback_query(BroadcastCallback.filter(F.action == "specific"))
async def process_specific_user(callback: CallbackQuery, callback_data: BroadcastCallback, state: FSMContext, i18n, session_without_commit):
    await callback.message.delete()
    await state.update_data(group="specific")
    user_dao = UserDAO(session_without_commit)
    users = await user_dao.find_all()
    await callback.message.answer(
        'Выберите юзера для рассылки:',
        reply_markup=get_paginated_checkbox_keyboard(
            items=users,
            context="broadcast_specific",
            get_display_text=lambda user: f"{user.admin_insert_name or user.username or user.id}",
            get_item_id=lambda user: user.id,
            selected_ids=set(),
            page=0,
            items_per_page=5,
        )
    )
    await state.set_state(BroadcastStates.waiting_for_targets)


@broadcast_router.callback_query(BroadcastCallback.filter(F.action == "current_broadcast"))
async def show_current_broadcasts(callback: CallbackQuery, state: FSMContext, session_without_commit):
    await callback.message.delete()
    broadcast_dao = BroadcastDAO(session_without_commit)
    user_dao = UserDAO(session_without_commit)
    broadcasts = await broadcast_dao.find_all(SBroadcast(
        status=BroadcastStatus.SCHEDULED
    ))
    if not broadcasts:
        await callback.message.answer("Нет запланированных рассылок.", reply_markup=AdminKeyboard.build())
        return

    for broadcast in broadcasts:
        if broadcast.media_type in ['specific','user_group']:
            group_msg = 'Кому:\n'
            users_ids = await broadcast_dao.get_recipients_for_broadcast(broadcast.id)
            for user_id in users_ids:
                user = await user_dao.find_one_or_none_by_id(user_id)
                group_msg += f'- {user.admin_insert_name or user.username or str(user.id)}\n'
        else:
            group_msg = f"Тип: {group_ru.get(broadcast.group)}\n"
            
        # Формируем текст для каждой рассылки
        broadcast.run_time = broadcast.run_time.replace(hour=broadcast.run_time.hour+3)
        info = f"Имя рассылки: <b>{broadcast.name}</b>\n"
        info += f"Текст: {broadcast.text[:30]}{'...' if len(broadcast.text) > 30 else ''}\n"
        info += f"Медиа: {'есть' if broadcast.media_id else 'нет'}\n"
        info += group_msg
        info += f"Время: {broadcast.run_time.strftime('%d.%m.%Y %H:%M (МСК)') if broadcast.run_time else 'без времени'}\n"
        info += f"Статус: Запланированно\n"

        # Создаем кнопки "Юзеры" и "Отменить рассылку"
        builder = InlineKeyboardBuilder()
        builder.add(
            InlineKeyboardButton(
                text="Юзеры",
                callback_data=BroadcastListCallback(action="show_users", broadcast_id=broadcast.id).pack()
            )
        )
        builder.add(
            InlineKeyboardButton(
                text="Отменить рассылку",
                callback_data=BroadcastListCallback(action="cancel_broadcast", broadcast_id=broadcast.id).pack()
            )
        )
        builder.adjust(1)
        
        match broadcast.media_type:
            case 'photo':
                await callback.message.answer_photo(photo=broadcast.media_id, caption=info, reply_markup=builder.as_markup())
            case 'video':
                await callback.message.answer_video(photo=broadcast.media_id, caption=info, reply_markup=builder.as_markup())
            case _:
                await callback.message.answer(info, reply_markup=builder.as_markup())
        await asyncio.sleep(0.1)


@broadcast_router.callback_query(BroadcastListCallback.filter(F.action == "show_users"))
async def show_broadcast_users(callback: CallbackQuery, callback_data: BroadcastListCallback, session_without_commit):
    broadcast_id = callback_data.broadcast_id
    broadcast_dao = BroadcastDAO(session_without_commit)
    broadcast = await broadcast_dao.find_one_or_none_by_id(broadcast_id)
    user_dao = UserDAO(session_without_commit)
    await callback.message.delete()
    # Получаем список user_id для рассылки
    user_ids = await broadcast_dao.get_recipients_for_broadcast(broadcast_id)
    if not user_ids:
        await callback.message.answer(f"Для рассылки <b>{broadcast.name}</b> нет получателей.", reply_markup=AdminKeyboard.build())
        return
    
    # Получаем информацию о пользователях
    users_info = []
    for user_id in user_ids:
        user = await user_dao.find_one_or_none_by_id(user_id)
        if user:
            display_name = user.admin_insert_name or user.username or str(user.id)
            users_info.append(f"- {display_name} (ID: {user_id})")
    
    # Формируем сообщение
    message_text = f"Получатели рассылки <b>{broadcast.name}</b>:\n\n" + "\n".join(users_info) if users_info else f"Для рассылки <b>{broadcast.name}</b> нет получателей."
    await callback.message.answer(message_text, reply_markup=AdminKeyboard.build())


@broadcast_router.callback_query(BroadcastListCallback.filter(F.action == "cancel_broadcast"))
async def cancel_broadcast_action(callback: CallbackQuery, callback_data: BroadcastListCallback, session_without_commit):
    broadcast_id = callback_data.broadcast_id
    broadcast_dao = BroadcastDAO(session_without_commit)
    await callback.message.delete()
    # Обновляем статус рассылки на CANCELLED
    broadcast = await broadcast_dao.find_one_or_none_by_id(broadcast_id)
    success = await broadcast_dao.update_status(broadcast_id, BroadcastStatus.CANCELLED)
    if not success:
        await callback.message.answer(f"Не удалось отменить рассылку ID {broadcast_id}.", reply_markup=AdminKeyboard.build())
        return
    
    # Удаляем задачу из планировщика
    job_id = f"broadcast_{broadcast_id}"
    job = scheduler.get_job(job_id)
    if job:
        scheduler.remove_job(job_id)
        logger.info(f"Scheduled job for broadcast {broadcast_id} removed.")
    
    await session_without_commit.commit()
    await callback.message.answer(f"Рассылка <b>{broadcast.name}</b> отменена.", reply_markup=AdminKeyboard.build())


@broadcast_router.message(F.text.in_(get_all_locales_for_key(translator_hub, "keyboard-reply-cancel")), StateFilter(BroadcastStates))
async def cancel_broadcast(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(GeneralStates.admin_panel)
    await message.answer(
        "Рассылка отменена.",
        reply_markup=AdminKeyboard.build()
    )

@broadcast_router.message(F.text, StateFilter(BroadcastStates.waiting_broadcase_name))
async def process_broadcast_name(message: Message, state: FSMContext):
    await state.update_data(broadcast_name=message.text)
    await message.answer(
        "Введите текст рассылки"
    )
    await state.set_state(BroadcastStates.waiting_for_text)

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


@broadcast_router.callback_query(PaginatedCheckboxCallback.filter(F.context == 'broadcast_specific'), StateFilter(BroadcastStates.waiting_for_targets))
async def process_targets(callback: CallbackQuery, callback_data: PaginatedCheckboxCallback, state: FSMContext, session_without_commit, i18n):
    """
    Обработка чекбокс-пагинации для выбора конкретных пользователей.
    Выбранные id хранятся в FSM state под ключом 'broadcast_specific_selected'.
    """
    await callback.answer()  # быстро закроем loading
    STORAGE_KEY = "broadcast_specific_selected"

    # загрузим текущее состояние выбранных id из state
    data = await state.get_data()
    sel_list = data.get(STORAGE_KEY, [])
    sel_set = set(sel_list)

    # подгружаем всех пользователей для построения клавиатуры
    users = await UserDAO(session_without_commit).find_all()

    # действия: toggle / prev / next / done
    action = callback_data.action
    item_id = int(callback_data.item_id or 0)
    page = int(callback_data.page or 0)

    if action == "toggle":
        if item_id in sel_set:
            sel_set.remove(item_id)
        else:
            sel_set.add(item_id)
        # сохраняем обновлённый набор в state
        await state.update_data({STORAGE_KEY: list(sel_set)})
        # перестроим клавиатуру текущей страницы
        kb = get_paginated_checkbox_keyboard(
            items=users,
            context="broadcast_specific",
            get_display_text=lambda u: f"{u.admin_insert_name or u.username or u.id}",
            get_item_id=lambda u: u.id,
            selected_ids=sel_set,
            page=page,
            items_per_page=5,
        )
        await callback.message.edit_text("Выберите пользователей:", reply_markup=kb)
        return

    if action in ("prev", "next"):
        # просто перестроим клавиатуру на нужной странице
        kb = get_paginated_checkbox_keyboard(
            items=users,
            context="broadcast_specific",
            get_display_text=lambda u: f"{u.admin_insert_name or u.username or u.id}",
            get_item_id=lambda u: u.id,
            selected_ids=sel_set,
            page=page,
            items_per_page=5,
        )
        await callback.message.edit_text("Выберите пользователей:", reply_markup=kb)
        return

    if action == "done":
        if not sel_set:
            await callback.message.answer("Не выбрано ни одного пользователя.")
            return
        await callback.message.delete()
        # сохранить итоговый список как целевые пользователи и продолжить поток ввода текста
        await state.update_data(target_user_ids=list(sel_set))
        info = f"Выбрано {len(sel_set)} пользователей:"
        for us in sel_set:
            user = await UserDAO(session_without_commit).find_one_or_none_by_id(us)
            info += f"\n- {user.admin_insert_name or user.username or user.id}"
        await callback.message.answer(info + "\n\nПридумайте название рассылки:", reply_markup=get_cancel_kb(i18n))
        await state.set_state(BroadcastStates.waiting_broadcase_name)
        return


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
        )
    )
    builder.add(
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
    user_data = await state.get_data()
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
    broadcast_name = user_data.get('broadcast_name')
    user_dao = UserDAO(session_without_commit)
    match group:
        case "specific":
            target_user_ids = user_data.get("target_user_ids", [])
        case 'all_users':
            target_user_ids = [user.id for user in await user_dao.find_all()]
        case 'with_purchases':
            target_user_ids = [user.id for user in await user_dao.get_users_with_payments()]
        case 'without_purchases':
            target_user_ids = [user.id for user in await user_dao.get_users_without_payments()]
        case 'user_group':
            user_group_id = user_data.get("user_group_id")
            group_dao = UserGroupDAO(session_without_commit)
            target_user_ids = [user.id for user in await group_dao.get_users_in_group(user_group_id)]
    # сохраняем рассылку в БД
    broadcast_dao = BroadcastDAO(session_without_commit)
    broadcast = await broadcast_dao.add(
        SBroadcast(
            text=text,
            name=broadcast_name,
            media_id=media_id,
            media_type=media_type,
            group_id=user_data.get("user_group_id"),
            group=group,
            run_time=run_time,
            status=BroadcastStatus.SCHEDULED,
            created_by=message.from_user.id
        )
    )
    await broadcast_dao.add_recipients_to_broadcast(broadcast.id, target_user_ids)
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

        broadcast = await broadcast_dao.find_one_or_none_by_id(broadcast_id)
        if not broadcast or broadcast.status != BroadcastStatus.SCHEDULED:
            return

        # Сохраняем все нужные поля локально, чтобы не вызывать lazy-load после await
        b_id = broadcast.id
        b_text = broadcast.text
        b_media_id = broadcast.media_id
        b_media_type = broadcast.media_type
        b_created_by = broadcast.created_by
        b_name = broadcast.name
        user_ids = await broadcast_dao.get_recipients_for_broadcast(broadcast_id=b_id)

        successful, failed = await broadcast_message(
            user_ids=user_ids,
            text=b_text,
            media_id=b_media_id,
            media_type=b_media_type,
        )

        # обновляем статус, используя локальную переменную id (не access через detached объект)
        await broadcast_dao.update_status(b_id, BroadcastStatus.SENT)
        try:
            await bot.send_message(
                b_created_by,
                f"Рассылка <b>{b_name}</b> завершена. Успешно: {successful}, Неудачно: {failed}",
            )
        except Exception as e:
            pass
        logger.info(f"Рассылка {b_name} завершена. Успешно: {successful}, Неудачно: {failed}")


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
    b_name = user_data["broadcast_name"]
    user_dao = UserDAO(session_without_commit)
    match group:
        case "specific":
            user_ids = user_data.get("target_user_ids", [])
        case 'all_users':
            user_ids = [user.id for user in await user_dao.find_all()]
        case 'with_purchases':
            user_ids = [user.id for user in await user_dao.get_users_with_payments()]
        case 'without_purchases':
            user_ids = [user.id for user in await user_dao.get_users_without_payments()]
        case 'user_group':
            user_group_id = user_data.get("user_group_id")
            group_dao = UserGroupDAO(session_without_commit)
            user_ids = [user.id for user in await group_dao.get_users_in_group(user_group_id)]
    
    successful, failed = await broadcast_message(
        user_ids=user_ids,
        text=text,
        media_id=media_id,
        media_type=media_type
    )
    
    await callback.message.answer(f"Рассылка <b>{b_name}</b>завершена! Успешно: {successful}, Неудачно: {failed}", reply_markup=AdminKeyboard.build())
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
    from loguru import logger
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
        logger.exception(f"Failed to resume scheduled broadcasts: {e}")


