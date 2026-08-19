"""Синхронная проверка и выдача промокодов из FAB (без commit)."""

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from bot.db.models import (
    ContentCard,
    ContentCardPool,
    MatchAnalysis,
    Promocode,
    PromocodeType,
    User,
    UserContentCard,
    UserMatchAnalysis,
    UserPromocode,
    UserPromocodeService,
)

PROMO_UNAVAILABLE_REASONS = {
    "not_found": "Промокод не найден",
    "inactive": "Неактивен",
    "limit_reached": "Лимит активаций исчерпан",
    "already_used": "Уже активирован",
    "cards_quantity_invalid": "Не указано количество карточек",
    "cards_not_configured": "Нет карточек/анализов для выдачи",
    "no_new_cards": "Нет новых карточек/анализов для пользователя",
}

DEFAULT_PROMO_NOTIFY_TEXT = (
    "Вам начислен промокод: *{codes}*\n\n"
    "Он уже доступен в профиле."
)


def _normalize_pool(raw) -> ContentCardPool:
    if isinstance(raw, ContentCardPool):
        return raw
    value = str(raw or ContentCardPool.CARDS.value).strip().lower()
    try:
        return ContentCardPool(value)
    except ValueError:
        return ContentCardPool.CARDS


def _is_cards_promo(promo: Promocode) -> bool:
    ptype = promo.promocode_type
    if ptype == PromocodeType.CARDS:
        return True
    val = ptype.value if hasattr(ptype, "value") else str(ptype or "")
    return val.lower() == PromocodeType.CARDS.value


def _promo_type_label(promo: Promocode) -> str:
    return "Карточки" if _is_cards_promo(promo) else "Услуги"


def _promo_benefit(promo: Promocode) -> str:
    if _is_cards_promo(promo):
        qty = promo.cards_issue_quantity or 0
        return f"{UserPromocode._card_pool_label(promo.card_pool)}: {qty}"
    return promo.services_summary


def _promo_duration(promo: Promocode) -> str:
    if _is_cards_promo(promo) or promo.duration_days is None:
        return "∞"
    return f"{promo.duration_days} дн."


def _available_match_analysis_ids(session: Session, user_id: int) -> list[int]:
    all_ids = [
        row[0]
        for row in session.execute(
            select(MatchAnalysis.id)
            .where(MatchAnalysis.is_ready.is_(True))
            .order_by(MatchAnalysis.id.asc())
        ).all()
        if row[0] is not None
    ]
    existing = {
        row[0]
        for row in session.execute(
            select(UserMatchAnalysis.match_analysis_id).where(
                UserMatchAnalysis.user_id == user_id
            )
        ).all()
        if row[0] is not None
    }
    return [mid for mid in all_ids if mid not in existing]


def _available_content_card_ids(
    session: Session, user_id: int, pool: ContentCardPool
) -> list[int]:
    all_ids = [
        row[0]
        for row in session.execute(
            select(ContentCard.id)
            .where(
                ContentCard.is_ready.is_(True),
                ContentCard.card_pool == pool.value,
            )
            .order_by(ContentCard.id.asc())
        ).all()
        if row[0] is not None
    ]
    existing = {
        row[0]
        for row in session.execute(
            select(UserContentCard.content_card_id).where(
                UserContentCard.user_id == user_id
            )
        ).all()
        if row[0] is not None
    }
    return [cid for cid in all_ids if cid not in existing]


def validate_promocode_for_user(
    session: Session, promocode: Promocode, user_id: int
) -> tuple[bool, str]:
    if not promocode:
        return False, "not_found"
    if not promocode.is_active:
        return False, "inactive"
    if promocode.max_usage is not None and promocode.activate_count is not None:
        if promocode.activate_count >= promocode.max_usage:
            return False, "limit_reached"

    already = session.execute(
        select(UserPromocode.id).where(
            UserPromocode.user_id == user_id,
            UserPromocode.promocode_id == promocode.id,
        )
    ).first()
    if already:
        return False, "already_used"

    if _is_cards_promo(promocode):
        cards_to_issue = max(0, promocode.cards_issue_quantity or 0)
        if cards_to_issue <= 0:
            return False, "cards_quantity_invalid"
        pool = _normalize_pool(promocode.card_pool)
        if pool == ContentCardPool.MATCH_ANALYSIS:
            available = _available_match_analysis_ids(session, user_id)
            if not session.execute(
                select(MatchAnalysis.id).where(MatchAnalysis.is_ready.is_(True)).limit(1)
            ).first():
                return False, "cards_not_configured"
            if not available:
                return False, "no_new_cards"
        else:
            available = _available_content_card_ids(session, user_id, pool)
            if not session.execute(
                select(ContentCard.id)
                .where(
                    ContentCard.is_ready.is_(True),
                    ContentCard.card_pool == pool.value,
                )
                .limit(1)
            ).first():
                return False, "cards_not_configured"
            if not available:
                return False, "no_new_cards"

    return True, "ok"


def assign_promocode_to_user(
    session: Session, promocode: Promocode, user_id: int
) -> tuple[bool, str]:
    """
    Выдаёт промокод пользователю (баланс услуг или карточки/анализы).
    Не коммитит сессию.
    """
    ok, reason = validate_promocode_for_user(session, promocode, user_id)
    if not ok:
        return False, reason

    user = session.get(User, user_id)
    if not user:
        return False, "not_found"

    user_promo = UserPromocode(user_id=user_id, promocode_id=promocode.id)
    session.add(user_promo)

    if _is_cards_promo(promocode):
        cards_to_issue = max(0, promocode.cards_issue_quantity or 0)
        pool = _normalize_pool(promocode.card_pool)
        issued_now = 0
        if cards_to_issue > 0 and pool == ContentCardPool.MATCH_ANALYSIS:
            for mid in _available_match_analysis_ids(session, user_id)[:cards_to_issue]:
                session.add(UserMatchAnalysis(user_id=user_id, match_analysis_id=mid))
                issued_now += 1
        elif cards_to_issue > 0:
            for card_id in _available_content_card_ids(session, user_id, pool)[
                :cards_to_issue
            ]:
                session.add(
                    UserContentCard(
                        user_id=user_id,
                        content_card_id=card_id,
                        source_user_promocode=user_promo,
                    )
                )
                issued_now += 1
        user_promo.issued_cards_count = issued_now
    else:
        for service in promocode.services or []:
            session.add(
                UserPromocodeService(
                    user_promocode=user_promo,
                    service_type=service.service_type,
                    remaining_quantity=service.quantity,
                )
            )

    promocode.activate_count = (promocode.activate_count or 0) + 1
    session.flush()
    return True, "ok"


def list_promocodes_for_user(session: Session, user_id: int) -> list[dict]:
    promocodes = (
        session.execute(
            select(Promocode)
            .options(selectinload(Promocode.services))
            .order_by(Promocode.code.asc())
        )
        .scalars()
        .all()
    )
    items = []
    for promo in promocodes:
        available, reason = validate_promocode_for_user(session, promo, user_id)
        items.append(
            {
                "id": promo.id,
                "code": promo.code,
                "type": "cards" if _is_cards_promo(promo) else "regular",
                "type_label": _promo_type_label(promo),
                "benefit": _promo_benefit(promo),
                "duration": _promo_duration(promo),
                "is_active": bool(promo.is_active),
                "available": available,
                "reason": None if available else PROMO_UNAVAILABLE_REASONS.get(
                    reason, reason
                ),
            }
        )
    return items


def render_promo_notify_text(template: str, codes: list[str]) -> str:
    text = (template or DEFAULT_PROMO_NOTIFY_TEXT).strip()
    if not text:
        text = DEFAULT_PROMO_NOTIFY_TEXT
    joined = ", ".join(codes)
    return text.replace("{codes}", joined).replace("{code}", joined)
