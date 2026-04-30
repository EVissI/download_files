from datetime import datetime, timezone

from aiogram.types import InlineKeyboardMarkup, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder
from loguru import logger
from sqlalchemy import select

from bot.common.utils.notify import notify_user
from bot.config import settings
from bot.db.database import async_session_maker
from bot.db.models import ContentCard, ContentCardIssueSchedule, User, UserContentCard


def _cards_cabinet_webapp_markup() -> InlineKeyboardMarkup:
    cabinet_url = f"{settings.MINI_APP_URL.rstrip('/')}/cards-cabinet"
    kb = InlineKeyboardBuilder()
    kb.button(text="Открыть кабинет", web_app=WebAppInfo(url=cabinet_url))
    kb.adjust(1)
    return kb.as_markup()


async def run_content_card_issue_schedule(schedule_id: int) -> None:
    """
    Выдаёт карточки по расписанию:
    - конкретному пользователю target_user_id;
    - cards_per_run карточек;
    - по возрастанию ID, пропуская уже выданные.
    """
    async with async_session_maker() as session:
        try:
            schedule = await session.get(ContentCardIssueSchedule, schedule_id)
            if not schedule:
                logger.warning("Card issue schedule %s not found", schedule_id)
                return
            if not schedule.is_active:
                logger.info("Card issue schedule %s is inactive, skip", schedule_id)
                return

            user_exists = await session.scalar(
                select(User.id).where(User.id == schedule.target_user_id).limit(1)
            )
            if user_exists is None:
                logger.warning(
                    "Card issue schedule %s target user %s not found",
                    schedule_id,
                    schedule.target_user_id,
                )
                return

            all_card_ids_result = await session.execute(
                select(ContentCard.id).order_by(ContentCard.id.asc())
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
                    UserContentCard.user_id == schedule.target_user_id
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

            to_issue_ids = available_card_ids[: max(1, int(schedule.cards_per_run))]
            for card_id in to_issue_ids:
                session.add(
                    UserContentCard(
                        user_id=schedule.target_user_id,
                        content_card_id=card_id,
                    )
                )

            issued_count = len(to_issue_ids)
            schedule.last_run_at = datetime.now(timezone.utc)
            await session.commit()

            await notify_user(
                schedule.target_user_id,
                (
                    f"Вам зачислено {issued_count} карточек.\n"
                    "Посмотрите их в личном кабинете."
                ),
                _cards_cabinet_webapp_markup(),
            )
            logger.info(
                "Card issue schedule %s granted %s cards to user %s",
                schedule_id,
                issued_count,
                schedule.target_user_id,
            )
        except Exception as exc:
            await session.rollback()
            logger.exception(
                "Card issue schedule %s failed: %s",
                schedule_id,
                exc,
            )
