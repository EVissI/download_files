import json

from html import escape

from typing import Any



from aiogram import Router, F

from aiogram.filters import BaseFilter, StateFilter

from aiogram.fsm.context import FSMContext

from aiogram.fsm.state import State, StatesGroup

from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from loguru import logger



from bot.config import bot, settings

from bot.db.redis import redis_client



FOLDER_ADMIN_REPLY_PREFIX = "folder_admin_reply:"

FOLDER_REPLY_START_PREFIX = "folderreply_"

FOLDER_ADMIN_REPLY_CTX_PREFIX = "folder_admin_reply_ctx:"

FOLDER_ADMIN_REPLY_PENDING_PREFIX = "folder_admin_reply_pending:"

FOLDER_ADMIN_REPLY_CTX_TTL = 86400

FOLDER_ADMIN_REPLY_PENDING_TTL = 3600





class SupportReplyStates(StatesGroup):

    waiting_reply = State()

    waiting_admin_reply = State()





class FolderAdminReplyPendingFilter(BaseFilter):

    async def __call__(self, message: Message) -> bool:

        user = message.from_user

        if not user:

            return False

        key = f"{FOLDER_ADMIN_REPLY_PENDING_PREFIX}{user.id}"

        return bool(await redis_client.get(key))





support_reply_router = Router()





def build_folder_admin_reply_markup(reply_token: str, bot_username: str) -> InlineKeyboardMarkup:

    username = str(bot_username or "").lstrip("@")

    start_payload = f"{FOLDER_REPLY_START_PREFIX}{reply_token}"

    url = f"https://t.me/{username}?start={start_payload}" if username else ""

    if url:

        button = InlineKeyboardButton(text="Ответить", url=url)

    else:

        button = InlineKeyboardButton(

            text="Ответить",

            callback_data=f"{FOLDER_ADMIN_REPLY_PREFIX}{reply_token}",

        )

    return InlineKeyboardMarkup(inline_keyboard=[[button]])





async def save_folder_admin_reply_context(token: str, payload: dict[str, Any]) -> None:

    await redis_client.set(

        f"{FOLDER_ADMIN_REPLY_CTX_PREFIX}{token}",

        json.dumps(payload),

        expire=FOLDER_ADMIN_REPLY_CTX_TTL,

    )





async def _load_folder_admin_reply_context(token: str) -> dict[str, Any] | None:

    raw = await redis_client.get(f"{FOLDER_ADMIN_REPLY_CTX_PREFIX}{token}")

    if not raw:

        return None

    try:

        data = json.loads(raw)

    except (TypeError, ValueError):

        return None

    return data if isinstance(data, dict) else None





async def _save_folder_admin_reply_pending(admin_id: int, payload: dict[str, Any]) -> None:

    await redis_client.set(

        f"{FOLDER_ADMIN_REPLY_PENDING_PREFIX}{admin_id}",

        json.dumps(payload),

        expire=FOLDER_ADMIN_REPLY_PENDING_TTL,

    )





async def _pop_folder_admin_reply_pending(admin_id: int) -> dict[str, Any] | None:

    key = f"{FOLDER_ADMIN_REPLY_PENDING_PREFIX}{admin_id}"

    raw = await redis_client.get(key)

    if not raw:

        return None

    await redis_client.delete(key)

    try:

        data = json.loads(raw)

    except (TypeError, ValueError):

        return None

    return data if isinstance(data, dict) else None





async def handle_folder_reply_deeplink(message: Message, start_payload: str) -> bool:

    """Открытие лички с ботом по кнопке «Ответить» из уведомления о папке."""

    if not start_payload.startswith(FOLDER_REPLY_START_PREFIX):

        return False



    user = message.from_user

    if not user:

        return True



    if user.id not in settings.ROOT_ADMIN_IDS:

        await message.answer("Недостаточно прав для ответа пользователю.")

        return True



    token = start_payload[len(FOLDER_REPLY_START_PREFIX) :].strip()

    if not token:

        await message.answer("Некорректная ссылка для ответа.")

        return True



    ctx = await _load_folder_admin_reply_context(token)

    if not ctx:

        await message.answer("Ссылка для ответа недействительна или устарела.")

        return True



    target_user_id = int(ctx.get("target_user_id") or 0)

    if target_user_id < 1:

        await message.answer("Не удалось определить пользователя для ответа.")

        return True



    await _save_folder_admin_reply_pending(user.id, ctx)

    await message.answer(

        f"Введите ответ пользователю {target_user_id}.\n"

        "Следующее сообщение в этом чате будет отправлено ему от бота."

    )

    return True





async def _complete_folder_admin_reply(admin_message: Message, ctx: dict[str, Any]) -> None:

    target_user_id = int(ctx.get("target_user_id") or 0)

    if target_user_id < 1:

        await admin_message.answer("Не удалось определить пользователя для ответа.")

        return



    if not admin_message.text or not str(admin_message.text).strip():

        await admin_message.answer("Отправьте текстовое сообщение для ответа пользователю.")

        return



    reply_body = str(admin_message.text).strip()

    await bot.send_message(

        chat_id=target_user_id,

        text=f"Ответ от эксперта:\n\n{reply_body}",

    )



    source_chat_id = ctx.get("source_chat_id")

    source_message_id = ctx.get("source_message_id")

    source_text = str(ctx.get("source_text") or "")

    if source_message_id and source_chat_id:

        updated_text = (

            f"{source_text}\n\n"

            f"<b>Ответ:</b>\n{escape(reply_body)}"

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



    await admin_message.answer("Ответ отправлен пользователю.")





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





@support_reply_router.message(

    F.chat.type == "private",

    F.text,

    FolderAdminReplyPendingFilter(),

)

async def private_folder_admin_reply_send(message: Message):

    """Ответ админа из лички после перехода по кнопке «Ответить»."""

    user = message.from_user

    if not user:

        return



    ctx = await _pop_folder_admin_reply_pending(user.id)

    if not ctx:

        return



    await _complete_folder_admin_reply(message, ctx)





@support_reply_router.callback_query(F.data.startswith("admin_reply:"))

async def admin_reply_start(callback: CallbackQuery, state: FSMContext):

    """

    Хендлер для кнопки 'Ответить' в сообщении из send_to_admin.

    Переводит оператора в состояние ожидания текста ответа и сохраняет user_id и photo_file_id.

    """

    await callback.answer()

    user_id = int(callback.data.split(":", 1)[1])



    photo_file_id = None

    if callback.message.photo:

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


