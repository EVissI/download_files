from datetime import datetime, timezone
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery

from bot.common.kbds.inline.activate_promo import get_activate_promo_keyboard
from bot.db.dao import UserDAO

from typing import TYPE_CHECKING
from fluentogram import TranslatorRunner
from bot.common.utils.i18n import get_all_locales_for_key
if TYPE_CHECKING:
    from locales.stub import TranslatorRunner


class SubscriptionMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message | CallbackQuery, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        session = data.get("session_without_commit") or data.get("session_with_commit")
        i18n: TranslatorRunner = data.get("i18n", None)
        user_id = event.from_user.id

        user = await UserDAO(session).find_one_or_none_by_id(user_id)
        now = datetime.now(timezone.utc)
        if not user or not user.end_sub_time or user.end_sub_time < now:
            await event.answer(i18n.user.static.has_no_sub(), get_activate_promo_keyboard())
            return
        return await handler(event, data)