from datetime import datetime, timezone

from aiogram.types import InlineKeyboardMarkup, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder
from loguru import logger
from sqlalchemy import select

from bot.common.utils.notify import notify_user
from bot.config import settings
from bot.db.database import async_session_maker
from bot.db.models import (
    ContentCard,
    ContentCardIssueSchedule,
    ContentCardPool,
    User,
    UserContentCard,
)
from bot.flask_admin.match_analysis_grant import grant_match_analyses_async


def _normalize_pool(raw) -> ContentCardPool:
    if isinstance(raw, ContentCardPool):
        return raw
    value = str(raw or ContentCardPool.CARDS.value).strip().lower()
    if value == ContentCardPool.PIP_COUNT.value:
        return ContentCardPool.PIP_COUNT
    if value == ContentCardPool.MATCH_ANALYSIS.value:
        return ContentCardPool.MATCH_ANALYSIS
    return ContentCardPool.CARDS


def _cabinet_webapp_markup(card_pool: ContentCardPool) -> InlineKeyboardMarkup:
    if card_pool == ContentCardPool.PIP_COUNT:
        cabinet_url = f"{settings.MINI_APP_URL.rstrip('/')}/pip-count-cabinet"
        button_text = "Открыть кабинет пипсов"
    elif card_pool == ContentCardPool.MATCH_ANALYSIS:
        cabinet_url = f"{settings.MINI_APP_URL.rstrip('/')}/match-analysis-cabinet"
        button_text = "Открыть «Анализ матча»"
    else:
        cabinet_url = f"{settings.MINI_APP_URL.rstrip('/')}/cards-cabinet"
        button_text = "Открыть кабинет"
    kb = InlineKeyboardBuilder()
    kb.button(text=button_text, web_app=WebAppInfo(url=cabinet_url))
    kb.adjust(1)
    return kb.as_markup()


async def run_content_card_issue_schedule(schedule_id: int) -> None:
    """
    Выдаёт по расписанию:
    - cards / pip_count → UserContentCard из ContentCard;
    - match_analysis → UserMatchAnalysis из MatchAnalysis (is_ready).
    """
    async with async_session_maker() as session:
        try:
            schedule = await session.get(ContentCardIssueSchedule, schedule_id)
            if not schedule:
                logger.warning("Card issue schedule {} not found", schedule_id)
                return
            if not schedule.is_active:
                logger.info("Card issue schedule {} is inactive, skip", schedule_id)
                return
            target_user_id = int(schedule.target_user_id)
            cards_per_run = max(1, int(schedule.cards_per_run))
            card_pool = _normalize_pool(schedule.card_pool)

            user_exists = await session.scalar(
                select(User.id).where(User.id == target_user_id).limit(1)
            )
            if user_exists is None:
                logger.warning(
                    "Card issue schedule {} target user {} not found",
                    schedule_id,
                    target_user_id,
                )
                return

            if card_pool == ContentCardPool.MATCH_ANALYSIS:
                issued_count = await grant_match_analyses_async(
                    session,
                    user_id=target_user_id,
                    quantity=cards_per_run,
                    commit=False,
                )
                schedule.last_run_at = datetime.now(timezone.utc)
                await session.commit()
                if issued_count <= 0:
                    return
                await notify_user(
                    target_user_id,
                    (
                        f"Вам зачислено {issued_count} анализов матча.\n"
                        "Посмотрите их в кабинете «Анализ матча»."
                    ),
                    _cabinet_webapp_markup(card_pool),
                )
                logger.info(
                    "Card issue schedule {} granted {} match analyses to user {}",
                    schedule_id,
                    issued_count,
                    target_user_id,
                )
                return

            all_card_ids_result = await session.execute(
                select(ContentCard.id)
                .where(
                    ContentCard.card_pool == card_pool.value,
                    ContentCard.is_ready.is_(True),
                )
                .order_by(ContentCard.id.asc())
            )
            all_card_ids = [
                int(card_id)
                for card_id in all_card_ids_result.scalars().all()
                if card_id is not None
            ]
            if not all_card_ids:
                schedule.last_run_at = datetime.now(timezone.utc)
                await session.commit()
                return

            existing_card_ids_result = await session.execute(
                select(UserContentCard.content_card_id).where(
                    UserContentCard.user_id == target_user_id
                )
            )
            existing_card_ids = {
                int(card_id)
                for card_id in existing_card_ids_result.scalars().all()
                if card_id is not None
            }

            available_card_ids = [
                card_id for card_id in all_card_ids if card_id not in existing_card_ids
            ]
            if not available_card_ids:
                schedule.last_run_at = datetime.now(timezone.utc)
                await session.commit()
                return

            to_issue_ids = available_card_ids[:cards_per_run]
            for card_id in to_issue_ids:
                session.add(
                    UserContentCard(
                        user_id=target_user_id,
                        content_card_id=card_id,
                    )
                )

            issued_count = len(to_issue_ids)
            schedule.last_run_at = datetime.now(timezone.utc)
            await session.commit()

            pool_label = (
                "карточек (пипсы)"
                if card_pool == ContentCardPool.PIP_COUNT
                else "карточек"
            )
            await notify_user(
                target_user_id,
                (
                    f"Вам зачислено {issued_count} {pool_label}.\n"
                    "Посмотрите их в личном кабинете."
                ),
                _cabinet_webapp_markup(card_pool),
            )
            logger.info(
                "Card issue schedule {} granted {} {} cards to user {}",
                schedule_id,
                issued_count,
                card_pool.value,
                target_user_id,
            )
        except Exception as exc:
            await session.rollback()
            logger.exception(
                "Card issue schedule {} failed: {}",
                schedule_id,
                exc,
            )
