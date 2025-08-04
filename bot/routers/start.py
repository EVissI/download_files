from aiogram import Router,F
from aiogram.types import Message
from aiogram.filters import CommandStart
from sqlalchemy.ext.asyncio import AsyncSession
from bot.common.kbds.markup.main_kb import MainKeyboard
from bot.common.texts import get_text
from bot.db.dao import UserDAO
from bot.db.models import User
from bot.db.schemas import SUser
from bot.config import settings
from bot.config import translator_hub
from typing import TYPE_CHECKING
from fluentogram import TranslatorRunner
if TYPE_CHECKING:
    from locales.stub import TranslatorRunner

start_router = Router()

@start_router.message(CommandStart())
async def start_command(message: Message, session_with_commit: AsyncSession):
    user_data = message.from_user
    user_id = user_data.id
    user_info:User = await UserDAO(session_with_commit).find_one_or_none_by_id(user_id)
    if user_info and user_data.id in settings.ROOT_ADMIN_IDS and user_info.role != User.Role.ADMIN.value:
        user_info.role = User.Role.ADMIN.value
        await UserDAO(session_with_commit).update(user_info.id, SUser.model_validate(user_info.to_dict()))
        i18n: TranslatorRunner = translator_hub.get_translator_by_locale(
        user_info.lang_code if user_info.lang_code else 'en'
        )
        await message.answer(
            i18n.user.static.hello(), reply_markup=MainKeyboard.build(user_info.role, i18n)
        )
        
        return
    if user_info is None:
        role = User.Role.USER.value
        if user_info in settings.ROOT_ADMIN_IDS:
            role = User.Role.ADMIN.value
        user_schema = SUser(id=user_id, 
                            first_name=user_data.first_name,
                            last_name=user_data.last_name, 
                            username=user_data.username,
                            role=role)

        user_info = await UserDAO(session_with_commit).add(user_schema)
        i18n: TranslatorRunner = translator_hub.get_translator_by_locale(
        user_info.lang_code if user_info.lang_code else 'en'
        )
        await message.answer(
            i18n.user.static.hello(),reply_markup=MainKeyboard.build(user_info.role, i18n)
        )
        await message.answer(
            '🎁 You have access to the promo code <code>NEW</code>!\nYou can activate it in <b>Profile</b> → <b>Activate promo code.</b>'
        )
        return
    i18n: TranslatorRunner = translator_hub.get_translator_by_locale(
        user_info.lang_code if user_info.lang_code else 'en'
        )
    await message.answer(
        i18n.user.static.hello(), reply_markup=MainKeyboard.build(user_info.role, i18n)
    )