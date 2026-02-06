from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from bot.config import bot


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

    await state.set_state(SupportReplyStates.waiting_admin_reply)
    await state.update_data(
        reply_user_id=user_id,
        photo_file_id=photo_file_id
    )

    await callback.message.answer(
        f"Напишите ответ пользователю {user_id}. Сообщение будет отправлено от бота."
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

    if not reply_user_id:
        await message.answer("Не удалось определить пользователя для ответа.")
        await state.clear()
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

    await message.answer("Ответ отправлен пользователю.")
    await state.clear()
