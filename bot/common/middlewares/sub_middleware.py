from datetime import datetime, timezone
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from bot.db.models import PromocodeServiceQuantity, ServiceType

from bot.common.kbds.inline.activate_promo import get_activate_promo_keyboard
from bot.db.dao import UserDAO
from loguru import logger
from typing import TYPE_CHECKING
from fluentogram import TranslatorRunner
from bot.common.utils.i18n import get_all_locales_for_key
if TYPE_CHECKING:
    from locales.stub import TranslatorRunner


class MatchMiddleware(BaseMiddleware):
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
        balance = await dao.get_total_analiz_balance(user_id, service_type=ServiceType.MATCH)
        if balance is None:
            return await handler(event, data)
        if not user or balance == 0:
            await event.answer(i18n.user.static.has_no_sub(), reply_markup=get_activate_promo_keyboard(i18n))
            return
        return await handler(event, data)

class AnalizMiddleware(BaseMiddleware):
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
        balance = await dao.get_total_analiz_balance(user_id, service_type=ServiceType.MONEYGAME)
        if balance is None:
            return await handler(event, data)
        if not user or balance == 0:
            await event.answer(i18n.user.static.has_no_sub(), reply_markup=get_activate_promo_keyboard(i18n))
            return
        return await handler(event, data)
    
class ShortBoardMiddleware(BaseMiddleware):
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
        balance = await dao.get_total_analiz_balance(user_id, service_type=ServiceType.SHORT_BOARD)
        if balance is None:
            return await handler(event, data)
        if not user or balance == 0:
            await event.answer(i18n.user.static.has_no_sub(), reply_markup=get_activate_promo_keyboard(i18n))
            return
        return await handler(event, data)

class HintsMiddleware(BaseMiddleware):
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
        balance = await dao.get_total_analiz_balance(user_id, service_type=ServiceType.HINTS)
        if balance is None:
            return await handler(event, data)
        if not user or balance == 0:
            await event.answer(i18n.user.static.has_no_sub(), reply_markup=get_activate_promo_keyboard(i18n))
            return
        return await handler(event, data)