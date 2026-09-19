"""
Статьи публичной части (/web/articles): лента и отдельная страница статьи.

Статья пишется админом прямо на странице, тем же режимом редактирования, что
и лендинг, поэтому хранится в landing_texts обычными ключами - только под
страницей «articles» (см. landing_text_service.page_of_key):

  art-index            список id статей, новые сверху (style_json["ids"])
  meta-art-<id>        {"published": bool, "date": "YYYY-MM-DD"}
  art-<id>-title       заголовок
  art-<id>-lead        подводка: под заголовком и в карточке ленты
  img-art-<id>-cover   обложка
  body-art-<id>        состав текста: абзацы, подзаголовки, картинки
  art-<id>-<часть>     тексты и картинки частей
"""

from __future__ import annotations

import re
import secrets
from datetime import date
from typing import Any

from bot.common.service.landing_text_service import (
    ARTICLES_PAGE,
    BG_KEY_PREFIX,
    BODY_KEY_PREFIX,
    HREF_KEY_PREFIX,
    IMAGE_KEY_PREFIX,
    META_KEY_PREFIX,
    _delete_key,
    _read_style,
    _upsert,
    invalidate_cache,
)
from bot.db.database import async_session_maker
from bot.db.models import LandingText

ARTICLE_ID_RE = re.compile(r"^a[0-9a-f]{8}$")
INDEX_KEY = "art-index"
MAX_ARTICLES = 300
ARTICLES_PATH = "/web/articles"

DEFAULT_TITLE = "Новая статья"
DEFAULT_LEAD = "Пара предложений о том, чему посвящена статья. Их видно в ленте."
# У новой статьи один пустой абзац: с него админ и начинает писать.
DEFAULT_BODY = [{"id": "000000", "t": "p"}]

_MONTHS = (
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
)


def valid_article_id(article_id: Any) -> bool:
    return isinstance(article_id, str) and bool(ARTICLE_ID_RE.match(article_id))


def owner_of(article_id: str) -> str:
    return f"art-{article_id}"


def title_key(article_id: str) -> str:
    return f"art-{article_id}-title"


def lead_key(article_id: str) -> str:
    return f"art-{article_id}-lead"


def cover_key(article_id: str) -> str:
    return f"art-{article_id}-cover"


def article_url(article_id: str) -> str:
    return f"{ARTICLES_PATH}/{article_id}"


def _meta_key(article_id: str) -> str:
    return f"{META_KEY_PREFIX}art-{article_id}"


def index_of(overrides: dict[str, dict[str, Any]]) -> list[str]:
    ids = ((overrides.get(INDEX_KEY) or {}).get("style") or {}).get("ids")
    return [item for item in ids if valid_article_id(item)] if isinstance(ids, list) else []


def meta_of(overrides: dict[str, dict[str, Any]], article_id: str) -> dict[str, Any]:
    meta = (overrides.get(_meta_key(article_id)) or {}).get("style")
    return meta if isinstance(meta, dict) else {}


def format_date(raw: Any) -> str:
    """2026-09-20 → «20 сентября 2026»."""
    try:
        day = date.fromisoformat(str(raw))
    except ValueError:
        return ""
    return f"{day.day} {_MONTHS[day.month - 1]} {day.year}"


def _text(overrides: dict[str, dict[str, Any]], key: str, default: str) -> str:
    return (overrides.get(key) or {}).get("text") or default


def article_card(overrides: dict[str, dict[str, Any]], article_id: str) -> dict[str, Any]:
    """Всё, что нужно карточке ленты и шапке статьи."""
    meta = meta_of(overrides, article_id)
    cover = (overrides.get(f"{IMAGE_KEY_PREFIX}{cover_key(article_id)}") or {}).get("text")
    return {
        "id": article_id,
        "url": article_url(article_id),
        "title": _text(overrides, title_key(article_id), DEFAULT_TITLE),
        "lead": _text(overrides, lead_key(article_id), DEFAULT_LEAD),
        "cover": cover or "",
        "published": bool(meta.get("published")),
        "date": format_date(meta.get("date")),
    }


def list_cards(
    overrides: dict[str, dict[str, Any]], *, include_drafts: bool
) -> list[dict[str, Any]]:
    cards = [article_card(overrides, article_id) for article_id in index_of(overrides)]
    return cards if include_drafts else [card for card in cards if card["published"]]


async def _read_index(session) -> list[str]:
    ids = (await _read_style(session, INDEX_KEY)).get("ids")
    return [item for item in ids if valid_article_id(item)] if isinstance(ids, list) else []


async def create_article(user_id: int | None) -> str:
    """Новая статья - черновик в начале ленты."""
    article_id = "a" + secrets.token_hex(4)
    async with async_session_maker() as session:
        ids = await _read_index(session)
        if len(ids) >= MAX_ARTICLES:
            raise ValueError("Слишком много статей")
        await _upsert(
            session,
            _meta_key(article_id),
            None,
            {"published": False, "date": date.today().isoformat()},
            user_id,
        )
        await _upsert(session, INDEX_KEY, None, {"ids": [article_id] + ids}, user_id)
        await session.commit()
    await invalidate_cache()
    return article_id


async def set_published(article_id: str, published: bool, user_id: int | None) -> bool:
    """
    Публикует статью или возвращает в черновики. Дата - день первой
    публикации: так её и видят читатели, а не день, когда начали писать.
    """
    async with async_session_maker() as session:
        if article_id not in await _read_index(session):
            return False
        meta = await _read_style(session, _meta_key(article_id))
        if published and not meta.get("was_published"):
            meta["date"] = date.today().isoformat()
            meta["was_published"] = True
        meta["published"] = bool(published)
        await _upsert(session, _meta_key(article_id), None, meta, user_id)
        await session.commit()
    await invalidate_cache()
    return True


async def delete_article(article_id: str, user_id: int | None) -> bool:
    """Статья уходит целиком: из ленты и со всеми своими текстами и картинками."""
    owner = owner_of(article_id)
    async with async_session_maker() as session:
        ids = await _read_index(session)
        if article_id not in ids:
            return False
        await _upsert(
            session,
            INDEX_KEY,
            None,
            {"ids": [item for item in ids if item != article_id]},
            user_id,
        )
        await _delete_key(session, _meta_key(article_id))
        await session.execute(
            LandingText.__table__.delete().where(
                (LandingText.page == ARTICLES_PAGE)
                & (
                    LandingText.key.like(f"{owner}-%")
                    | LandingText.key.like(f"{IMAGE_KEY_PREFIX}{owner}-%")
                    | LandingText.key.like(f"{HREF_KEY_PREFIX}{owner}-%")
                    | (LandingText.key == f"{BODY_KEY_PREFIX}{owner}")
                    | (LandingText.key == f"{BG_KEY_PREFIX}{owner}")
                )
            )
        )
        await session.commit()
    await invalidate_cache()
    return True
