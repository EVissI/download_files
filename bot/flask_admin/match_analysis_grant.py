"""Синхронная/async выдача анализов матча пользователю."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from bot.db.models import MatchAnalysis, UserContentCardStatus, UserMatchAnalysis


def grant_match_analyses_sync(
    session: Session,
    *,
    user_id: int,
    quantity: int,
) -> int:
    """
    Выдать до quantity анализов матча пользователю user_id.
    Берутся ready-анализы по возрастанию id, уже выданные пропускаются.
    """
    cards_quantity = max(0, int(quantity))
    if cards_quantity <= 0:
        return 0

    all_ids_result = session.execute(
        select(MatchAnalysis.id)
        .where(MatchAnalysis.is_ready.is_(True))
        .order_by(MatchAnalysis.id.asc())
    )
    all_ids = [row[0] for row in all_ids_result.all() if row[0] is not None]
    if not all_ids:
        return 0

    existing_result = session.execute(
        select(UserMatchAnalysis.match_analysis_id).where(
            UserMatchAnalysis.user_id == user_id
        )
    )
    existing_ids = {row[0] for row in existing_result.all() if row[0] is not None}

    available_ids = [mid for mid in all_ids if mid not in existing_ids]
    if not available_ids:
        return 0

    to_issue_ids = available_ids[:cards_quantity]
    for mid in to_issue_ids:
        session.add(
            UserMatchAnalysis(
                user_id=user_id,
                match_analysis_id=mid,
                card_status=UserContentCardStatus.UNVIEWED,
            )
        )
    session.commit()
    return len(to_issue_ids)


async def grant_match_analyses_async(
    session: AsyncSession,
    *,
    user_id: int,
    quantity: int,
    commit: bool = False,
) -> int:
    """Async-вариант выдачи анализов (для promo / schedule). Не коммитит по умолчанию."""
    cards_quantity = max(0, int(quantity))
    if cards_quantity <= 0:
        return 0

    all_ids_result = await session.execute(
        select(MatchAnalysis.id)
        .where(MatchAnalysis.is_ready.is_(True))
        .order_by(MatchAnalysis.id.asc())
    )
    all_ids = [
        int(mid) for mid in all_ids_result.scalars().all() if mid is not None
    ]
    if not all_ids:
        return 0

    existing_result = await session.execute(
        select(UserMatchAnalysis.match_analysis_id).where(
            UserMatchAnalysis.user_id == user_id
        )
    )
    existing_ids = {
        int(mid) for mid in existing_result.scalars().all() if mid is not None
    }

    available_ids = [mid for mid in all_ids if mid not in existing_ids]
    if not available_ids:
        return 0

    to_issue_ids = available_ids[:cards_quantity]
    for mid in to_issue_ids:
        session.add(
            UserMatchAnalysis(
                user_id=user_id,
                match_analysis_id=mid,
                card_status=UserContentCardStatus.UNVIEWED,
            )
        )
    if commit:
        await session.commit()
    else:
        await session.flush()
    return len(to_issue_ids)
