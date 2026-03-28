from typing import Any, Dict, Optional, Union

from aiogram.filters import BaseFilter
from aiogram.types import TelegramObject
from loguru import logger

from bot.db.database import async_session_maker
from bot.db.dao import UserDAO
from bot.db.models import User as UserModel


class UserInfo(BaseFilter):
    """
    Подгружает user_info. По возможности использует session_without_commit из middleware,
    чтобы не открывать отдельное соединение на каждый update (иначе при пачке файлов
    исчерпывается QueuePool).
    """

    async def __call__(
        self,
        event: TelegramObject,
        **kwargs: Any,
    ) -> Union[bool, Dict[str, UserModel]]:
        user = getattr(event, "from_user", None)
        if user is None:
            return False

        session = kwargs.get("session_without_commit")

        async def _load(s) -> Optional[UserModel]:
            return await UserDAO(s).find_one_or_none_by_id(user.id)

        if session is not None:
            user_info = await _load(session)
        else:
            async with async_session_maker() as s:
                user_info = await _load(s)

        if user_info:
            return {"user_info": user_info}
        logger.error(f"Пользователь {user.id} не найден")
        return False
