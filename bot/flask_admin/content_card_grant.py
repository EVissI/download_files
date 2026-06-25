"""Синхронная выдача карточек из FAB (по пулу cards / pip_count)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from bot.db.models import ContentCard, ContentCardPool, UserContentCard


def grant_content_cards_from_pool_sync(
    session: Session,
    *,
    user_id: int,
    quantity: int,
    card_pool: ContentCardPool,
) -> int:
    """
  Выдать до quantity карточек пользователю user_id из указанного пула.
  Карточки берутся по возрастанию id, уже выданные пропускаются.
  """
    cards_quantity = max(0, int(quantity))
    if cards_quantity <= 0:
        return 0

    all_card_ids_result = session.execute(
        select(ContentCard.id)
        .where(ContentCard.card_pool == card_pool.value)
        .order_by(ContentCard.id.asc())
    )
    all_card_ids = [row[0] for row in all_card_ids_result.all() if row[0] is not None]
    if not all_card_ids:
        return 0

    existing_card_ids_result = session.execute(
        select(UserContentCard.content_card_id).where(UserContentCard.user_id == user_id)
    )
    existing_card_ids = {
        row[0] for row in existing_card_ids_result.all() if row[0] is not None
    }

    available_card_ids = [
        card_id for card_id in all_card_ids if card_id not in existing_card_ids
    ]
    if not available_card_ids:
        return 0

    to_issue_ids = available_card_ids[:cards_quantity]
    for card_id in to_issue_ids:
        session.add(UserContentCard(user_id=user_id, content_card_id=card_id))
    session.commit()
    return len(to_issue_ids)
