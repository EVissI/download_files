"""Теневой User для веб-аккаунтов: id = -web_user.id, карточки и анализы выдаются на него."""

from __future__ import annotations

from contextvars import ContextVar, Token

from loguru import logger
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from bot.db.models import User, WebUser

web_grant_uid_ctx: ContextVar[int | None] = ContextVar("web_grant_uid", default=None)


def web_grant_user_id(web_user_id: int) -> int:
    return -int(web_user_id)


def get_web_grant_uid() -> int | None:
    return web_grant_uid_ctx.get()


def set_web_grant_uid(uid: int | None) -> Token:
    return web_grant_uid_ctx.set(uid)


def reset_web_grant_uid(token: Token) -> None:
    web_grant_uid_ctx.reset(token)


def _shadow_username(login: str | None, web_user_id: int) -> str:
    raw = (login or "").strip() or f"id{int(web_user_id)}"
    return f"web:{raw}"[:80]


def ensure_web_grant_user_sync(
    session: Session,
    web_user_id: int,
    login: str | None = None,
) -> int:
    grant_id = web_grant_user_id(web_user_id)
    username = _shadow_username(login, web_user_id)
    user = session.get(User, grant_id)
    if user is not None:
        if login and user.username != username:
            user.username = username
            user.first_name = (login or "").strip() or user.first_name
        return grant_id
    if not login:
        wu = session.get(WebUser, int(web_user_id))
        login = wu.login if wu is not None else None
        username = _shadow_username(login, web_user_id)
    session.add(
        User(
            id=grant_id,
            username=username,
            first_name=(login or "").strip() or None,
            lang_code="ru",
            role=User.Role.USER.value,
        )
    )
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        existing = session.get(User, grant_id)
        if existing is None:
            raise
    return grant_id


async def ensure_web_grant_user_async(
    web_user_id: int,
    login: str | None = None,
) -> int:
    from bot.db.database import async_session_maker

    grant_id = web_grant_user_id(web_user_id)
    async with async_session_maker() as session:
        existing = await session.get(User, grant_id)
        if existing is not None:
            if login:
                username = _shadow_username(login, web_user_id)
                if existing.username != username:
                    existing.username = username
                    existing.first_name = (login or "").strip() or existing.first_name
                    await session.commit()
            return grant_id
        if not login:
            wu = await session.get(WebUser, int(web_user_id))
            login = wu.login if wu is not None else None
        session.add(
            User(
                id=grant_id,
                username=_shadow_username(login, web_user_id),
                first_name=(login or "").strip() or None,
                lang_code="ru",
                role=User.Role.USER.value,
            )
        )
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            existing = await session.get(User, grant_id)
            if existing is None:
                logger.exception(
                    "web grant user create failed web_user_id={}", web_user_id
                )
                raise
    return grant_id
