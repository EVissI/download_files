from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from bot.db.dao import UserDAO
from loguru import logger
from typing import TYPE_CHECKING
from fluentogram import TranslatorRunner
from bot.common.utils.i18n import get_all_locales_for_key
from bot.db.models import User

if TYPE_CHECKING:
    from locales.stub import TranslatorRunner

class ContactInfoCallback(CallbackData, prefix="general_unloading"):
    action: str
    user_id: int

async def build_contact_info_keyboard(
        session,
        user_id: int,
        i18n: TranslatorRunner
    ) -> InlineKeyboardMarkup:
        """Строит клавиатуру на основе данных из БД."""
        builder = InlineKeyboardBuilder()
        dao = UserDAO(session)  
        user = await dao.find_one_or_none_by_id(user_id)

        if user and not user.phone_number:
            builder.add(InlineKeyboardButton(
                text=i18n.user.static.share_phone(),
                callback_data=ContactInfoCallback(action="phone", user_id=user_id).pack()
            ))
        if user and not user.email:
            builder.add(InlineKeyboardButton(
                text=i18n.user.static.share_email(),
                callback_data=ContactInfoCallback(action="email", user_id=user_id).pack()
            ))

        builder.adjust(1)
        return builder.as_markup()