"""Админы кабинетов карточек / анализа матча: ROOT_ADMIN_IDS и веб-пользователи с is_admin."""

from __future__ import annotations

from fastapi import HTTPException
from loguru import logger
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from bot.config import settings
from bot.db.models import (
    ContentCard,
    MatchAnalysis,
    User,
    UserContentCard,
    UserContentCardStatus,
    UserMatchAnalysis,
    WebUser,
)


def is_cabinet_admin(user_id: int | None) -> bool:
    try:
        uid = int(user_id)
    except (TypeError, ValueError):
        return False
    if uid in (settings.ROOT_ADMIN_IDS or []):
        return True
    from bot.common.service.web_grant_user import get_web_grant_is_admin, get_web_grant_uid

    return get_web_grant_uid() == uid and bool(get_web_grant_is_admin())


def require_cabinet_admin(user_id: int | None) -> int:
    uid = int(user_id or 0)
    if not is_cabinet_admin(uid):
        raise HTTPException(
            status_code=403,
            detail="Действие доступно только администраторам",
        )
    return uid


async def require_screenshot_font_scale_admin(request, init_data: str | None = None) -> None:
    """ROOT_ADMIN через Telegram WebApp или веб-сессия с is_admin."""
    raw = str(init_data or "").strip()
    if raw:
        from bot.common.utils.tg_auth import verify_telegram_webapp_data

        user_data = verify_telegram_webapp_data(raw)
        if not user_data:
            raise HTTPException(status_code=401, detail="Invalid Telegram data")
        user_id = (user_data.get("user") or {}).get("id")
        if not user_id:
            raise HTTPException(status_code=400, detail="Invalid user data")
        if user_id not in (settings.ROOT_ADMIN_IDS or []):
            raise HTTPException(status_code=403, detail="Forbidden")
        return

    from bot.common.service.hint_viewer_web_service import resolve_web_session

    session = await resolve_web_session(request)
    if session and session.get("is_admin"):
        return
    if session:
        raise HTTPException(status_code=403, detail="Forbidden")
    raise HTTPException(status_code=401, detail="Missing initData")


_INSERT_MISSING_CARDS_SQL = text(
    """
    INSERT INTO user_content_cards (user_id, content_card_id)
    SELECT :uid, c.id
    FROM content_cards c
    WHERE NOT EXISTS (
        SELECT 1 FROM user_content_cards u
        WHERE u.user_id = :uid AND u.content_card_id = c.id
    )
    """
)
_INSERT_MISSING_MA_SQL = text(
    """
    INSERT INTO user_match_analyses (user_id, match_analysis_id)
    SELECT :uid, m.id
    FROM match_analyses m
    WHERE NOT EXISTS (
        SELECT 1 FROM user_match_analyses u
        WHERE u.user_id = :uid AND u.match_analysis_id = m.id
    )
    """
)


def _rowcount(result) -> int:
    n = getattr(result, "rowcount", None)
    return int(n) if n and n > 0 else 0


def _grants_already_complete_sync(session: Session, user_id: int) -> bool:
    card_total = session.scalar(select(func.count()).select_from(ContentCard)) or 0
    card_have = (
        session.scalar(
            select(func.count())
            .select_from(UserContentCard)
            .where(UserContentCard.user_id == user_id)
        )
        or 0
    )
    if int(card_have) < int(card_total):
        return False
    ma_total = session.scalar(select(func.count()).select_from(MatchAnalysis)) or 0
    ma_have = (
        session.scalar(
            select(func.count())
            .select_from(UserMatchAnalysis)
            .where(UserMatchAnalysis.user_id == user_id)
        )
        or 0
    )
    return int(ma_have) >= int(ma_total)


async def _grants_already_complete_async(session: AsyncSession, user_id: int) -> bool:
    card_total = await session.scalar(select(func.count()).select_from(ContentCard)) or 0
    card_have = (
        await session.scalar(
            select(func.count())
            .select_from(UserContentCard)
            .where(UserContentCard.user_id == user_id)
        )
        or 0
    )
    if int(card_have) < int(card_total):
        return False
    ma_total = await session.scalar(select(func.count()).select_from(MatchAnalysis)) or 0
    ma_have = (
        await session.scalar(
            select(func.count())
            .select_from(UserMatchAnalysis)
            .where(UserMatchAnalysis.user_id == user_id)
        )
        or 0
    )
    return int(ma_have) >= int(ma_total)


def _add_missing_grants_sync(session: Session, user_id: int) -> int:
    if session.get(User, user_id) is None:
        return 0
    if _grants_already_complete_sync(session, user_id):
        return 0
    params = {"uid": int(user_id)}
    issued = _rowcount(session.execute(_INSERT_MISSING_CARDS_SQL, params))
    issued += _rowcount(session.execute(_INSERT_MISSING_MA_SQL, params))
    return issued


def grant_all_cabinet_content_sync(
    session: Session, user_id: int, *, commit: bool = True
) -> int:
    issued = _add_missing_grants_sync(session, int(user_id))
    if commit and issued:
        session.commit()
    return issued


async def _add_missing_grants_async(session: AsyncSession, user_id: int) -> int:
    if await session.get(User, user_id) is None:
        return 0
    if await _grants_already_complete_async(session, user_id):
        return 0
    params = {"uid": int(user_id)}
    issued = _rowcount(await session.execute(_INSERT_MISSING_CARDS_SQL, params))
    issued += _rowcount(await session.execute(_INSERT_MISSING_MA_SQL, params))
    return issued


async def grant_all_cabinet_content_async(user_id: int) -> int:
    from bot.db.database import async_session_maker

    async with async_session_maker() as session:
        issued = await _add_missing_grants_async(session, int(user_id))
        if issued:
            await session.commit()
        return issued


async def cabinet_admin_user_ids(session: AsyncSession) -> list[int]:
    ids: list[int] = [int(x) for x in (settings.ROOT_ADMIN_IDS or [])]
    rows = await session.execute(select(WebUser.id).where(WebUser.is_admin.is_(True)))
    from bot.common.service.web_grant_user import web_grant_user_id

    for web_id in rows.scalars().all():
        ids.append(web_grant_user_id(int(web_id)))
    seen: set[int] = set()
    out: list[int] = []
    for uid in ids:
        if uid in seen:
            continue
        seen.add(uid)
        out.append(uid)
    return out


async def grant_card_to_cabinet_admins(session: AsyncSession, content_card_id: int) -> None:
    for uid in await cabinet_admin_user_ids(session):
        if await session.get(User, uid) is None:
            continue
        exists = (
            await session.execute(
                select(UserContentCard.id).where(
                    UserContentCard.user_id == uid,
                    UserContentCard.content_card_id == content_card_id,
                )
            )
        ).scalar_one_or_none()
        if exists:
            continue
        session.add(UserContentCard(user_id=uid, content_card_id=content_card_id))


async def grant_match_analysis_to_cabinet_admins(
    session: AsyncSession, match_analysis_id: int
) -> None:
    for uid in await cabinet_admin_user_ids(session):
        if await session.get(User, uid) is None:
            continue
        exists = (
            await session.execute(
                select(UserMatchAnalysis.id).where(
                    UserMatchAnalysis.user_id == uid,
                    UserMatchAnalysis.match_analysis_id == match_analysis_id,
                )
            )
        ).scalar_one_or_none()
        if exists:
            continue
        session.add(
            UserMatchAnalysis(
                user_id=uid,
                match_analysis_id=match_analysis_id,
                card_status=UserContentCardStatus.UNVIEWED,
            )
        )


def web_cabinet_title_for_pool(pool) -> str:
    """Название раздела для писем и сообщений: «Карточки», «Подсчёт пипсов»…"""
    from bot.db.models import ContentCardPool

    if pool == ContentCardPool.PIP_COUNT or str(pool) == ContentCardPool.PIP_COUNT.value:
        return "Подсчёт пипсов"
    if (
        pool == ContentCardPool.MATCH_ANALYSIS
        or str(pool) == ContentCardPool.MATCH_ANALYSIS.value
    ):
        return "Анализ матча"
    return "Карточки"


def web_cabinet_source_path_for_pool(pool) -> str:
    from bot.db.models import ContentCardPool

    if pool == ContentCardPool.PIP_COUNT or str(pool) == ContentCardPool.PIP_COUNT.value:
        return "/web/pip-count"
    if (
        pool == ContentCardPool.MATCH_ANALYSIS
        or str(pool) == ContentCardPool.MATCH_ANALYSIS.value
    ):
        return "/web/match-analysis"
    return "/web/cards"


async def notify_cabinet_assignment(
    target_user_id: int,
    *,
    text: str,
    source_path: str,
    author_user_id: int = 0,
    telegram_markup=None,
) -> tuple[bool, str | None]:
    """Telegram-уведомление или сообщение в веб-чат для теневого User."""
    uid = int(target_user_id)
    if uid == 0:
        return False, "Некорректный пользователь"
    try:
        if uid < 0:
            from bot.common.service.web_support_service import notify_web_grant_user

            await notify_web_grant_user(
                uid,
                text=text,
                source_path=source_path,
                author_user_id=author_user_id,
            )
        else:
            from bot.config import bot

            await bot.send_message(chat_id=uid, text=text, reply_markup=telegram_markup)
        return True, None
    except Exception as e:
        logger.warning("cabinet assign notify failed uid={}: {}", uid, e)
        return False, str(e)
