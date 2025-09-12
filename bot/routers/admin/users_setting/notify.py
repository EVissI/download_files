from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from bot.db.dao import UserDAO
from bot.db.models import User
from loguru import logger
from bot.common.utils.i18n import get_all_locales_for_key
from bot.common.kbds.markup.admin_panel import AdminKeyboard

from bot.common.kbds.inline.user_settings import UserSettingsCallback
from bot.common.kbds.markup.cancel import get_cancel_kb
from bot.common.general_states import GeneralStates
from bot.config import translator_hub

class NotifyUserState(StatesGroup):
    notify_message = State()

user_setting_notify_router = Router()

@user_setting_notify_router.callback_query(UserSettingsCallback.filter(F.action == "notify"))
async def prompt_notify_user(callback: CallbackQuery, callback_data: UserSettingsCallback, state:FSMContext, i18n):
    await callback.message.delete()
    await state.set_state(NotifyUserState.notify_message)
    await state.update_data(user_id=callback_data.user_id)
    await callback.message.answer(
        "Введите сообщение для пользователя:",
        reply_markup=get_cancel_kb(i18n)
    )

@user_setting_notify_router.message(F.text.in_(get_all_locales_for_key(translator_hub, "auto-batch-stop")),
                                 StateFilter(NotifyUserState.notify_message))
async def cancel_notify_user(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(GeneralStates.admin_panel)
    await message.answer(
        message.text,
        reply_markup=AdminKeyboard.build()
    )

@user_setting_notify_router.message(StateFilter(NotifyUserState.notify_message), F.text)
async def send_notify_user(message: Message, state: FSMContext, session_without_commit):
    try:
        notify_text = message.text.strip()
        if not notify_text:
            return await message.answer("Сообщение не может быть пустым. Попробуйте снова.",
                                        reply_markup=AdminKeyboard.build())
        data = await state.get_data()
        user_id = data.get("user_id")
        user_dao = UserDAO(session_without_commit)
        user: User = await user_dao.find_one_or_none_by_id(user_id)
        if not user:
            await state.clear()
            await state.set_state(GeneralStates.admin_panel)
            return await message.answer("Пользователь не найден.", reply_markup=AdminKeyboard.build())
        # send message to user
        try:
            await message.bot.send_message(
                chat_id=user.id,
                text=notify_text
            )
            await message.answer("Сообщение успешно отправлено пользователю.",
                                 reply_markup=AdminKeyboard.build())
        except Exception as e:
            logger.error(f"Error sending message to user {user.id}: {e}")
            await message.answer("Не удалось отправить сообщение пользователю. Возможно, он заблокировал бота.",
                                 reply_markup=AdminKeyboard.build())
        await state.clear()
        await state.set_state(GeneralStates.admin_panel)
    except Exception as e:
        logger.error(f"Error in notify user flow: {e}")
        await state.clear()
        await state.set_state(GeneralStates.admin_panel)
        await message.answer(
            "Произошла ошибка.",
            reply_markup=AdminKeyboard.build()
        )
