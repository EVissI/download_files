from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from loguru import logger
from bot.db.dao import UserDAO
from bot.db.models import User

from bot.common.utils.i18n import get_all_locales_for_key
from bot.common.kbds.markup.admin_panel import AdminKeyboard
from bot.common.general_states import GeneralStates
from bot.common.kbds.inline.user_settings import (
    get_user_settings_kb,
    UserSettingsCallback
)
from bot.common.kbds.markup.cancel import get_cancel_kb

from bot.config import translator_hub

class UpdateNicknameState(StatesGroup):
    nickname = State()

user_list_update_username_router = Router()

@user_list_update_username_router.callback_query(UserSettingsCallback.filter(F.action == "set_username"))
async def prompt_nickname_update(callback: CallbackQuery,callback_data:UserSettingsCallback, state: FSMContext, i18n):
    await callback.message.delete()
    await state.set_state(UpdateNicknameState.nickname)
    await state.update_data(user_id=callback_data.user_id)
    await callback.message.answer(
        "Введите никнейм",
        reply_markup=get_cancel_kb(i18n)
    )

@user_list_update_username_router.message(F.text.in_(get_all_locales_for_key(translator_hub, "auto-batch-stop")),
                                        StateFilter(UpdateNicknameState.nickname))
async def cancel_nickname_update(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(GeneralStates.admin_panel)
    await message.answer(
        message.text,
        reply_markup=AdminKeyboard.build()
    )

@user_list_update_username_router.message(StateFilter(UpdateNicknameState.nickname), F.text)
async def update_nickname(message: Message, state: FSMContext, session_without_commit):
    try:
        nickname = message.text.strip()
        if not nickname:
            return await message.answer("Никнейм не может быть пустым. Попробуйте снова.")
        data = await state.get_data()
        user_id = data.get("user_id")
        user_dao = UserDAO(session_without_commit)
        updated_user = await user_dao.update_admin_insert_name(user_id, nickname)
        await state.clear()
        await state.set_state(GeneralStates.admin_panel)
        await message.answer(
            f"ID: {updated_user.id}\n"
            f"Username: @{updated_user.username or 'нет'}\n"
            f"Имя: {updated_user.first_name or 'нет'}\n"
            f"Фамилия: {updated_user.last_name or 'нет'}\n"
            f"Роль: {updated_user.role}\n"
            f"Язык: {updated_user.lang_code or 'не установлен'}\n"
            f"Поставленное имя: {updated_user.admin_insert_name or 'не установлен'}",
            reply_markup=get_user_settings_kb(user_id)
        )
    except Exception as e:
        logger.error(f"Ошибка при обновлении никнейма: {e}")
        await message.answer("Произошла ошибка при обновлении никнейма. Попробуйте снова.")