from aiogram import Router, F, Bot
from aiogram.types import Message, InlineKeyboardButton, CallbackQuery
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters.callback_data import CallbackData
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest, TelegramRetryAfter
from loguru import logger
import asyncio

from bot.common.general_states import GeneralStates
from bot.common.kbds.markup.admin_panel import AdminKeyboard
from bot.common.kbds.markup.cancel import get_cancel_kb
from bot.config import bot
from bot.db.dao import UserDAO

from bot.common.utils.i18n import get_all_locales_for_key
from bot.config import translator_hub
from typing import TYPE_CHECKING
from fluentogram import TranslatorRunner

if TYPE_CHECKING:
    from locales.stub import TranslatorRunner


# Инициализация роутера
broadcast_router = Router()

# CallbackData для обработки подтверждения и кнопки "Без медиа"
class BroadcastCallback(CallbackData, prefix="broadcast"):
    action: str  # confirm, cancel или no_media

# Определение состояний для FSM
class BroadcastStates(StatesGroup):
    waiting_for_text = State()
    waiting_for_media = State()
    waiting_for_confirmation = State()

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
async def start_broadcast(message: Message, state: FSMContext, i18n):
    sent_message = await message.answer("Введите текст для рассылки:",reply_markup=get_cancel_kb(i18n))
    await state.update_data(sent_message_id=sent_message.message_id)
    await state.set_state(BroadcastStates.waiting_for_text)

@broadcast_router.message(F.text == get_all_locales_for_key(translator_hub,'keyboard-reply-cancel'), StateFilter(BroadcastStates))
async def cancel_broadcast(message: Message, state: FSMContext, i18n: TranslatorRunner):
    await state.clear()
    await state.set_state(GeneralStates.admin_panel)
    await message.answer(
        message.text,
        reply_markup=AdminKeyboard.build()
    )
# Получение текста рассылки
@broadcast_router.message(F.text, StateFilter(BroadcastStates.waiting_for_text))
async def process_broadcast_text(message: Message, state: FSMContext):
    user_data = await state.get_data()
    sent_message_id = user_data.get("sent_message_id")
    
    # Удаление предыдущего сообщения
    if sent_message_id:
        try:
            await bot.delete_message(chat_id=message.chat.id, message_id=sent_message_id)
        except Exception as e:
            logger.warning(f"Не удалось удалить сообщение {sent_message_id}: {e}")
    
    await state.update_data(broadcast_text=message.text)
    
    # Создание инлайн-кнопки "Без медиа"
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(
            text="Без медиа",
            callback_data=BroadcastCallback(action="no_media").pack()
        )
    )
    
    sent_message = await message.answer(
        "Отправьте медиа (фото или видео) или нажмите кнопку 'Без медиа':",
        reply_markup=builder.as_markup()
    )
    await state.update_data(sent_message_id=sent_message.message_id)
    await state.set_state(BroadcastStates.waiting_for_media)

# Получение медиа или обработка кнопки "Без медиа"
@broadcast_router.message(StateFilter(BroadcastStates.waiting_for_media), F.photo | F.video)
@broadcast_router.callback_query(StateFilter(BroadcastStates.waiting_for_media), BroadcastCallback.filter(F.action == "no_media"))
async def process_broadcast_media(event: Message | CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    sent_message_id = user_data.get("sent_message_id")
    
    # Определение объекта сообщения
    message = event if isinstance(event, Message) else event.message
    
    # Удаление предыдущего сообщения
    if sent_message_id:
        try:
            await bot.delete_message(chat_id=message.chat.id, message_id=sent_message_id)
        except Exception as e:
            logger.warning(f"Не удалось удалить сообщение {sent_message_id}: {e}")
    
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
    
    await state.update_data(sent_message_id=sent_message.message_id)
    await state.set_state(BroadcastStates.waiting_for_confirmation)

# Обработка подтверждения через инлайн-кнопки
@broadcast_router.callback_query(BroadcastStates.waiting_for_confirmation, BroadcastCallback.filter())
async def process_broadcast_confirmation(callback: CallbackQuery, callback_data: BroadcastCallback, state: FSMContext, session_without_commit):
    user_data = await state.get_data()
    sent_message_id = user_data.get("sent_message_id")
    
    # Удаление сообщения с превью
    if sent_message_id:
        try:
            await bot.delete_message(chat_id=callback.message.chat.id, message_id=sent_message_id)
        except Exception as e:
            logger.warning(f"Не удалось удалить сообщение {sent_message_id}: {e}")
    
    if callback_data.action == "cancel":
        await callback.message.answer("Рассылка отменена.")
        await state.clear()
        return
    
    text = user_data["broadcast_text"]
    media_id = user_data.get("media_id")
    media_type = user_data.get("media_type")
    
    user_ids = [user.id for user in await UserDAO(session_without_commit).find_all()]
    
    await callback.message.answer("Начинаю рассылку...")
    successful, failed = await broadcast_message(
        user_ids=user_ids,
        text=text,
        media_id=media_id,
        media_type=media_type
    )
    
    await callback.message.answer(f"Рассылка завершена! Успешно: {successful}, Неудачно: {failed}")
    await state.clear()
    await state.set_state(GeneralStates.admin_panel)