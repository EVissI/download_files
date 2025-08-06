from aiogram import Router, F, Bot
from aiogram.types import Message, FSInputFile, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types.callback_query import CallbackQuery
from aiogram.filters.callback_data import CallbackData
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest, TelegramRetryAfter
from loguru import logger
import asyncio

from bot.common.kbds.markup.admin_panel import AdminKeyboard
from bot.config import bot
from bot.db.dao import UserDAO

# Инициализация роутера
broadcast_router = Router()

# CallbackData для обработки подтверждения
class BroadcastCallback(CallbackData, prefix="broadcast"):
    action: str  # confirm или cancel

# Определение состояний для FSM
class BroadcastStates(StatesGroup):
    waiting_for_text = State()
    waiting_for_media = State()
    waiting_for_confirmation = State()

# Функция отправки сообщения пользователю
async def notify_user(user_id: int, text: str, media_path: str = None, media_type: str = None):
    """
    Отправляет сообщение пользователю с опциональным медиа.
    
    Args:
        user_id: ID пользователя
        text: Текст сообщения
        media_path: Путь к медиафайлу (опционально)
        media_type: Тип медиа ('photo' или 'video', опционально)
    """
    try:
        if media_path and media_type:
            if media_type == "photo":
                await bot.send_photo(
                    chat_id=user_id,
                    photo=FSInputFile(media_path),
                    caption=text
                )
            elif media_type == "video":
                await bot.send_video(
                    chat_id=user_id,
                    video=FSInputFile(media_path),
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
        return await notify_user(user_id, text, media_path, media_type)
    except Exception as e:
        logger.error(f"Неожиданная ошибка при отправке сообщения пользователю {user_id}: {e}")
        return False

# Функция рассылки
async def broadcast_message(user_ids: list[int], text: str, media_path: str = None, media_type: str = None):
    """
    Выполняет рассылку сообщений.
    
    Args:
        user_ids: Список ID пользователей
        text: Текст сообщения
        media_path: Путь к медиафайлу (опционально)
        media_type: Тип медиа ('photo' или 'video', опционально)
    """
    if not user_ids:
        logger.info("Список пользователей для рассылки пуст.")
        return 0, 0

    successful = 0
    failed = 0
    
    for user_id in user_ids:
        if await notify_user(user_id, text, media_path, media_type):
            successful += 1
        else:
            failed += 1
        await asyncio.sleep(0.1)  # Задержка для предотвращения флуда
    
    logger.info(f"Рассылка завершена. Успешно: {successful}, Неудачно: {failed}")
    return successful, failed

# Команда для старта рассылки
@broadcast_router.message(F.text == AdminKeyboard.get_kb_text().get('notify'))
async def start_broadcast(message: Message, state: FSMContext):   
    await message.answer("Введите текст для рассылки:")
    await state.set_state(BroadcastStates.waiting_for_text)

# Получение текста рассылки
@broadcast_router.message(BroadcastStates.waiting_for_text)
async def process_broadcast_text(message: Message, state: FSMContext):
    await state.update_data(broadcast_text=message.text)
    await message.answer("Отправьте медиа (фото или видео) или напишите '<code>без медиа</code>' для продолжения:")
    await state.set_state(BroadcastStates.waiting_for_media)

# Получение медиа или пропуск
@broadcast_router.message(BroadcastStates.waiting_for_media)
async def process_broadcast_media(message: Message, state: FSMContext):
    user_data = await state.get_data()
    media_id = None
    media_type = None
    
    if message.text and message.text.lower() == "без медиа":
        pass
    elif message.photo:
        media_type = "photo"
        media_id = message.photo[-1].file_id
    elif message.video:
        media_type = "video"
        media_id = message.video.file_id
    else:
        await message.answer("Пожалуйста, отправьте фото, видео или напишите 'без медиа'.")
        return
    
    await state.update_data(media_id=media_id, media_type=media_type)
    
    # Формирование превью
    preview_text = f"Превью рассылки:\n\nТекст: {user_data['broadcast_text']}"
    if media_id:
        preview_text += f"\nМедиа: {media_type}"
    
    # Создание инлайн-кнопок
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
            await message.answer_photo(
                photo=media_id,
                caption=preview_text,
                reply_markup=builder.as_markup()
            )
        elif media_type == "video":
            await message.answer_video(
                video=media_id,
                caption=preview_text,
                reply_markup=builder.as_markup()
            )
    else:
        await message.answer(
            text=preview_text,
            reply_markup=builder.as_markup()
        )
    
    await state.set_state(BroadcastStates.waiting_for_confirmation)

# Обработка подтверждения через инлайн-кнопки
@broadcast_router.callback_query(BroadcastStates.waiting_for_confirmation, BroadcastCallback.filter())
async def process_broadcast_confirmation(callback: CallbackQuery, callback_data: BroadcastCallback, state: FSMContext, session_without_commit):
    if callback_data.action == "cancel":
        await callback.message.answer("Рассылка отменена.")
        await state.clear()
        await callback.message.delete()
        return
    
    user_data = await state.get_data()
    text = user_data["broadcast_text"]
    media_path = user_data.get("media_path")
    media_type = user_data.get("media_type")
    
    user_ids = [user.id for user in await UserDAO(session_without_commit).find_all()]
    
    await callback.message.answer("Начинаю рассылку...")
    successful, failed = await broadcast_message(
        user_ids=user_ids,
        text=text,
        media_path=media_path,
        media_type=media_type
    )
    
    await callback.message.answer(f"Рассылка завершена! Успешно: {successful}, Неудачно: {failed}")
    await state.clear()
    await callback.message.delete()