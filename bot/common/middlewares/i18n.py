import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User
from fluentogram import TranslatorHub
from loguru import logger

from bot.db.dao import UserDAO


class TranslatorRunnerMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:

        user: User = data.get('event_from_user')
        session = data.get('session_without_commit')
        user_info = await UserDAO(session).find_one_or_none_by_id(user.id)
        if user_info is None:
            return await handler(event, data)
        if user_info.lang_code is None:
            user_info.lang_code = 'en'
            await UserDAO(session).update(
                user_info.id, {'lang_code': user_info.lang_code}
            )
            await session.commit()
        hub: TranslatorHub = data.get('_translator_hub')
        data['i18n'] = hub.get_translator_by_locale(locale=user_info.lang_code if user_info else 'en')
        logger.info(data['i18n'])
        return await handler(event, data)