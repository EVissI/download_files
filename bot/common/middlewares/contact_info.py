from datetime import datetime, timezone
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from bot.common.kbds.inline.contact_info import build_contact_info_keyboard
from bot.db.dao import UserDAO
from loguru import logger
from typing import TYPE_CHECKING
from fluentogram import TranslatorRunner
from bot.common.utils.i18n import get_all_locales_for_key
from bot.db.models import User

if TYPE_CHECKING:
    from locales.stub import TranslatorRunner

class ContactInfoMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message | CallbackQuery, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        session = data.get("session_without_commit")
        i18n: TranslatorRunner = data.get("i18n", None)
        user_id = event.from_user.id
        dao = UserDAO(session)
        user = await dao.find_one_or_none_by_id(user_id)

        if not user:
            return await handler(event, data)

        phone_missing = not user.phone_number
        email_missing = not user.email

        if phone_missing or email_missing:
            keyboard = await build_contact_info_keyboard(
                session,
                user_id,
                i18n
            )
            await event.answer(
                i18n.user.static.missing_contact_info(),
                reply_markup=keyboard
            )
            return
        return await handler(event, data)
    