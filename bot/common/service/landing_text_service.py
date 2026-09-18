"""
Тексты и стили лендинга: чтение с кэшем в Redis, запись из режима редактирования.

Значения по умолчанию живут в шаблоне, в БД попадают только правки админа.
Обычная загрузка страницы стоит одного GET в Redis; в Postgres идём лишь при
холодном кэше и после сохранения.
"""

from __future__ import annotations

import json
import re
from typing import Any

from loguru import logger
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from bot.db.database import async_session_maker
from bot.db.models import LandingText
from bot.db.redis import redis_client

PAGE = "landing"
CACHE_KEY = "landing:texts:v1"
CACHE_TTL_SEC = 3600

KEY_MAX_LEN = 80  # ширина landing_texts.key
KEY_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,79}$")
MAX_TEXT_LEN = 2000
MAX_KEYS_PER_SAVE = 200
# Картинки лежат в тех же строках, что и тексты, но под своим префиксом -
# чтобы не путались с ключами текстовых узлов.
IMAGE_KEY_PREFIX = "img-"
# Адреса ссылок - там же, своим префиксом.
HREF_KEY_PREFIX = "href-"
MAX_HREF_LEN = 500
# Что разрешено в href: свои страницы, обычные сайты и мессенджеры.
# javascript:, data: и прочее сюда не проходит.
_HREF_RE = re.compile(
    r"""^(?:https?://[^\s<>"']+|/[^\s<>"']*|\#[A-Za-z0-9_-]*"""
    r"""|mailto:[^\s<>"']+|tel:[+0-9][0-9 ()-]*|tg://[^\s<>"']+)$"""
)

# Границы стилей. Намеренно узкие: размер - множитель к тому, что задано в CSS,
# поэтому адаптивные clamp() продолжают работать и вёрстка не разъезжается.
SIZE_MIN, SIZE_MAX = 0.8, 1.4
STROKE_MAX_PX = 3
_COLOR_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")

_SCRIPT_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.S | re.I)
_TAG_RE = re.compile(r"<[^>]*>")
_WS_RE = re.compile(r"[ \t ]+")


def valid_key(key: Any) -> bool:
    return isinstance(key, str) and bool(KEY_RE.match(key))


def clean_href(raw: Any) -> str:
    """Адрес ссылки. Пустая строка - значит вернуть тот, что в шаблоне."""
    if raw is None:
        return ""
    value = "".join(str(raw).split())[:MAX_HREF_LEN]
    if not value:
        return ""
    return value if _HREF_RE.match(value) else ""


def clean_text(raw: Any) -> str:
    """Из contenteditable может прилететь разметка - оставляем только текст."""
    if raw is None:
        return ""
    text = str(raw)
    text = _SCRIPT_RE.sub(" ", text)
    text = text.replace("<br>", "\n").replace("<br/>", "\n").replace("</div>", "\n")
    text = _TAG_RE.sub("", text)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<")
    text = text.replace("&gt;", ">").replace("&quot;", '"').replace("&#39;", "'")
    text = _WS_RE.sub(" ", text)
    return text.strip()[:MAX_TEXT_LEN]


def _clean_color_map(raw: Any) -> dict[str, str] | None:
    """
    Приводит цвет к виду {"dark": "#…", "light": "#…"}.
    Голая строка - формат прежних записей; применяем её к обеим темам, чтобы
    внешний вид уже сохранённых правок не изменился.
    """
    if isinstance(raw, str) and _COLOR_RE.match(raw.strip()):
        value = raw.strip().lower()
        return {"dark": value, "light": value}
    if isinstance(raw, dict):
        out: dict[str, str] = {}
        for theme in ("dark", "light"):
            value = raw.get(theme)
            if isinstance(value, str) and _COLOR_RE.match(value.strip()):
                out[theme] = value.strip().lower()
        return out or None
    return None


def clean_style(raw: Any) -> dict[str, Any] | None:
    """Пропускаем только разрешённые поля в разрешённых границах."""
    if not isinstance(raw, dict):
        return None
    out: dict[str, Any] = {}

    size = raw.get("size")
    if isinstance(size, (int, float)):
        size = round(float(size), 2)
        if abs(size - 1.0) > 0.001:
            out["size"] = min(SIZE_MAX, max(SIZE_MIN, size))

    if raw.get("bold") is True:
        out["bold"] = True

    color = _clean_color_map(raw.get("color"))
    if color:
        out["color"] = color

    stroke = raw.get("stroke")
    if isinstance(stroke, dict):
        width = stroke.get("width")
        s_color = stroke.get("color")
        if (
            isinstance(width, (int, float))
            and width > 0
            and isinstance(s_color, str)
            and _COLOR_RE.match(s_color.strip())
        ):
            out["stroke"] = {
                "width": min(STROKE_MAX_PX, max(1, int(round(float(width))))),
                "color": s_color.strip().lower(),
            }

    return out or None


def style_to_css(style: dict[str, Any] | None) -> str:
    """
    Инлайновый style: размер (в em - относительно значения из CSS), жирность
    и обводка. Цвета здесь намеренно нет: он зависит от темы и живёт в
    отдельных правилах, см. colors_css.
    """
    if not style:
        return ""
    parts: list[str] = []
    size = style.get("size")
    if isinstance(size, (int, float)) and abs(float(size) - 1.0) > 0.001:
        parts.append(f"font-size:{float(size):.2f}em")
    if style.get("bold"):
        parts.append("font-weight:700")
    stroke = style.get("stroke")
    if isinstance(stroke, dict):
        parts.append(
            f"-webkit-text-stroke:{stroke['width']}px {stroke['color']};"
            f"paint-order:stroke fill"
        )
    return ";".join(parts)


def colors_css(overrides: dict[str, dict[str, Any]] | None) -> str:
    """
    Правила цвета для всех переопределённых ключей.

    Специфичность `.lbg [data-lp="…"]` (два класса) намеренно выше базовых
    `.lbg a` и `.lbg .lbg-btn--primary`, иначе цвет ссылок и кнопок не
    применился бы. Светлая тема - отдельным, более точным селектором.
    """
    rules: list[str] = []
    for key, entry in (overrides or {}).items():
        if not valid_key(key):
            continue
        color = ((entry or {}).get("style") or {}).get("color")
        if not isinstance(color, dict):
            continue
        dark = color.get("dark")
        light = color.get("light")
        if dark:
            rules.append('.lbg [data-lp="%s"]{color:%s}' % (key, dark))
        if light:
            rules.append(
                'html[data-theme="light"] .lbg [data-lp="%s"]{color:%s}' % (key, light)
            )
    return "".join(rules)


async def _load_from_db() -> dict[str, dict[str, Any]]:
    async with async_session_maker() as session:
        rows = await session.scalars(
            select(LandingText).where(LandingText.page == PAGE)
        )
        return {
            row.key: {"text": row.text, "style": row.style_json}
            for row in rows.all()
        }


async def get_overrides() -> dict[str, dict[str, Any]]:
    """Все правки страницы. Обычно - один GET в Redis."""
    try:
        cached = await redis_client.get(CACHE_KEY)
        if cached is not None:
            return json.loads(cached)
    except Exception:
        logger.exception("landing texts cache read failed")

    data = await _load_from_db()
    try:
        await redis_client.set(
            CACHE_KEY, json.dumps(data, ensure_ascii=False), expire=CACHE_TTL_SEC
        )
    except Exception:
        logger.exception("landing texts cache write failed")
    return data


async def invalidate_cache() -> None:
    try:
        await redis_client.delete(CACHE_KEY)
    except Exception:
        logger.exception("landing texts cache drop failed")


async def save_items(items: list[dict[str, Any]], user_id: int | None) -> int:
    """
    Сохраняет правки пачкой. Пустой текст без стилей = возврат к шаблону
    (строка удаляется). Возвращает число обработанных ключей.
    """
    if not isinstance(items, list):
        return 0

    saved = 0
    async with async_session_maker() as session:
        for item in items[:MAX_KEYS_PER_SAVE]:
            if not isinstance(item, dict):
                continue
            key = item.get("key")
            if not valid_key(key):
                continue
            text = clean_text(item.get("text"))
            style = clean_style(item.get("style"))

            # Ссылка живёт отдельной строкой: у одного узла могут отличаться
            # текст и адрес, а сброс текста не должен ронять адрес.
            if "href" in item:
                await _write_href(session, key, clean_href(item.get("href")), user_id)

            if not text and not style:
                await session.execute(
                    LandingText.__table__.delete().where(
                        (LandingText.page == PAGE) & (LandingText.key == key)
                    )
                )
                saved += 1
                continue

            stmt = insert(LandingText).values(
                page=PAGE,
                key=key,
                text=text or None,
                style_json=style,
                updated_by=user_id,
            )
            await session.execute(
                stmt.on_conflict_do_update(
                    index_elements=[LandingText.page, LandingText.key],
                    set_={
                        "text": stmt.excluded.text,
                        "style_json": stmt.excluded.style_json,
                        "updated_by": stmt.excluded.updated_by,
                    },
                )
            )
            saved += 1
        await session.commit()

    await invalidate_cache()
    return saved


async def _delete_key(session, key: str) -> None:
    await session.execute(
        LandingText.__table__.delete().where(
            (LandingText.page == PAGE) & (LandingText.key == key)
        )
    )


async def _upsert(session, key: str, text: str | None, style, user_id) -> None:
    stmt = insert(LandingText).values(
        page=PAGE, key=key, text=text, style_json=style, updated_by=user_id
    )
    await session.execute(
        stmt.on_conflict_do_update(
            index_elements=[LandingText.page, LandingText.key],
            set_={
                "text": stmt.excluded.text,
                "style_json": stmt.excluded.style_json,
                "updated_by": stmt.excluded.updated_by,
            },
        )
    )


async def _write_href(session, key: str, href: str, user_id: int | None) -> None:
    full = f"{HREF_KEY_PREFIX}{key}"
    if len(full) > KEY_MAX_LEN:
        return
    if not href:
        await _delete_key(session, full)
        return
    await _upsert(session, full, href, None, user_id)


async def get_layouts(
    overrides: dict[str, dict[str, Any]] | None = None,
) -> dict[str, list[str] | None]:
    """
    Раскладка каждой секции: None - состав по умолчанию.

    Правки можно передать уже прочитанными - страница читает их один раз и
    не ходит в Redis повторно.
    """
    from bot.common.service.landing_blocks import SECTIONS, clean_layout, layout_key

    if overrides is None:
        overrides = await get_overrides()
    out: dict[str, list[str] | None] = {}
    for section in SECTIONS:
        entry = overrides.get(layout_key(section)) or {}
        raw = (entry.get("style") or {}).get("blocks")
        out[section] = clean_layout(section, raw)
    return out


async def save_layout(section: str, blocks: list[str], user_id: int | None) -> None:
    """Запоминает состав и порядок блоков секции."""
    from bot.common.service.landing_blocks import SECTIONS, clean_layout, layout_key

    if section not in SECTIONS:
        return
    cleaned = clean_layout(section, blocks) or []
    async with async_session_maker() as session:
        await _upsert(
            session, layout_key(section), None, {"blocks": cleaned}, user_id
        )
        await session.commit()
    await invalidate_cache()


async def drop_block_keys(section: str, block_id: str) -> None:
    """Убирает тексты, ссылки и картинку удалённого своего блока."""
    from bot.common.service.landing_blocks import CUSTOM_ID_RE

    if not CUSTOM_ID_RE.match(block_id or ""):
        return
    prefix = f"{section}-{block_id}"
    async with async_session_maker() as session:
        await session.execute(
            LandingText.__table__.delete().where(
                (LandingText.page == PAGE)
                & (
                    LandingText.key.like(f"{prefix}%")
                    | LandingText.key.like(f"{HREF_KEY_PREFIX}{prefix}%")
                    | LandingText.key.like(f"{IMAGE_KEY_PREFIX}{prefix}%")
                )
            )
        )
        await session.commit()
    await invalidate_cache()


async def reset_all() -> int:
    async with async_session_maker() as session:
        result = await session.execute(
            LandingText.__table__.delete().where(LandingText.page == PAGE)
        )
        await session.commit()
    await invalidate_cache()
    return result.rowcount or 0


def valid_image_key(key: Any) -> bool:
    """Ключ картинки хранится с префиксом, поэтому запас под него нужен сразу."""
    return valid_key(key) and len(key) + len(IMAGE_KEY_PREFIX) <= KEY_MAX_LEN


async def save_image(key: str, url: str, user_id: int | None) -> None:
    """Запоминает адрес картинки, загруженной админом вместо штатной."""
    if not valid_image_key(key) or not url:
        return
    async with async_session_maker() as session:
        stmt = insert(LandingText).values(
            page=PAGE,
            key=f"{IMAGE_KEY_PREFIX}{key}",
            text=url,
            style_json=None,
            updated_by=user_id,
        )
        await session.execute(
            stmt.on_conflict_do_update(
                index_elements=[LandingText.page, LandingText.key],
                set_={"text": stmt.excluded.text, "updated_by": stmt.excluded.updated_by},
            )
        )
        await session.commit()
    await invalidate_cache()
