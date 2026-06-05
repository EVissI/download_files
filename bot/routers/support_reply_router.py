from html import escape

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from loguru import logger

from bot.config import bot

FOLDER_ADMIN_REPLY_PREFIX = "folder_admin_reply:"


class SupportReplyStates(StatesGroup):
    waiting_reply = State()
    waiting_admin_reply = State()


support_reply_router = Router()


@support_reply_router.callback_query(F.data.startswith("support_reply:"))
async def support_reply_start(callback: CallbackQuery, state: FSMContext):
    """
    Хендлер для кнопки 'Ответить' в сообщении техподдержки.
    Переводит оператора в состояние ожидания текста ответа и сохраняет user_id.
    """
    await callback.answer()
    user_id = int(callback.data.split(":", 1)[1])

    await state.set_state(SupportReplyStates.waiting_reply)
    await state.update_data(reply_user_id=user_id)

    await callback.message.answer(
        f"Напишите ответ пользователю {user_id}. Сообщение будет отправлено от бота."
    )


@support_reply_router.message(StateFilter(SupportReplyStates.waiting_reply))
async def support_reply_send(message: Message, state: FSMContext):
    """
    Получает текст ответа от оператора и отправляет его пользователю из состояния FSM.
    """
    data = await state.get_data()
    reply_user_id = data.get("reply_user_id")

    if not reply_user_id:
        await message.answer("Не удалось определить пользователя для ответа.")
        await state.clear()
        return

    await bot.send_message(
        chat_id=int(reply_user_id),
        text=f"✉️ Ответ от техподдержки:\n\n{message.text}",
    )

    await message.answer("Ответ отправлен пользователю.")
    await state.clear()


@support_reply_router.callback_query(F.data.startswith(FOLDER_ADMIN_REPLY_PREFIX))
async def folder_admin_reply_start(callback: CallbackQuery, state: FSMContext):
    """
    Ответ пользователю, активировавшему папку: после отправки обновляет исходное уведомление.
    """
    await callback.answer()
    user_id = int(callback.data.split(":", 1)[1])
    source_chat_id = callback.message.chat.id if callback.message else None
    source_message_id = callback.message.message_id if callback.message else None
    source_text = ""
    if callback.message:
        source_text = callback.message.html_text or callback.message.text or ""

    await state.set_state(SupportReplyStates.waiting_admin_reply)
    await state.update_data(
        reply_user_id=user_id,
        photo_file_id=None,
        reply_source_chat_id=source_chat_id,
        reply_source_message_id=source_message_id,
        reply_source_message_text=source_text,
        update_source_message=True,
    )

    await callback.message.answer(
        f"Напишите ответ пользователю {user_id} в этом чате. "
        "Следующее сообщение будет отправлено ему от бота, "
        "а уведомление об активации папки обновится."
    )


@support_reply_router.callback_query(F.data.startswith("admin_reply:"))
async def admin_reply_start(callback: CallbackQuery, state: FSMContext):
    """
    Хендлер для кнопки 'Ответить' в сообщении из send_to_admin.
    Переводит оператора в состояние ожидания текста ответа и сохраняет user_id и photo_file_id.
    """
    await callback.answer()
    user_id = int(callback.data.split(":", 1)[1])

    # Сохраняем file_id фото из сообщения админу
    photo_file_id = None
    if callback.message.photo:
        # Берем самое большое фото (последний элемент в списке)
        photo_file_id = callback.message.photo[-1].file_id

    source_chat_id = callback.message.chat.id if callback.message else None

    await state.set_state(SupportReplyStates.waiting_admin_reply)
    await state.update_data(
        reply_user_id=user_id,
        photo_file_id=photo_file_id,
        reply_source_chat_id=source_chat_id,
        reply_source_message_id=None,
        reply_source_message_text=None,
        update_source_message=False,
    )

    await callback.message.answer(
        f"Напишите ответ пользователю {user_id} в этом чате. "
        "Следующее сообщение будет отправлено ему от бота."
    )


@support_reply_router.message(StateFilter(SupportReplyStates.waiting_admin_reply))
async def admin_reply_send(message: Message, state: FSMContext):
    """
    Получает текст ответа от оператора и отправляет его пользователю из состояния FSM.
    Прикрепляет фото из исходного сообщения.
    """
    data = await state.get_data()
    reply_user_id = data.get("reply_user_id")
    photo_file_id = data.get("photo_file_id")
    reply_source_chat_id = data.get("reply_source_chat_id")

    if not reply_user_id:
        await message.answer("Не удалось определить пользователя для ответа.")
        await state.clear()
        return

    if reply_source_chat_id is not None and message.chat.id != int(reply_source_chat_id):
        return

    if not message.text or not str(message.text).strip():
        await message.answer("Отправьте текстовое сообщение для ответа пользователю.")
        return

    reply_text = f"Ответ от эксперта:\n\n{message.text}"

    # Отправляем с фото, если оно есть
    if photo_file_id:
        await bot.send_photo(
            chat_id=int(reply_user_id),
            photo=photo_file_id,
            caption=reply_text,
        )
    else:
        await bot.send_message(
            chat_id=int(reply_user_id),
            text=reply_text,
        )

    if data.get("update_source_message"):
        source_message_id = data.get("reply_source_message_id")
        source_chat_id = data.get("reply_source_chat_id")
        source_text = str(data.get("reply_source_message_text") or "")
        if source_message_id and source_chat_id:
            updated_text = (
                f"{source_text}\n\n"
                f"<b>Ответ:</b>\n{escape(message.text.strip())}"
            )
            try:
                await bot.edit_message_text(
                    chat_id=int(source_chat_id),
                    message_id=int(source_message_id),
                    text=updated_text,
                    parse_mode="HTML",
                    reply_markup=None,
                )
            except Exception as e:
                logger.warning("folder admin reply source message update failed: {}", e)

    await message.answer("Ответ отправлен пользователю.")
    await state.clear()
