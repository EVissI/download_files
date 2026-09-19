"""
Публичные страницы веб-сервисов без авторизации: лендинг /web, вопросы
/web/faq и статьи /web/articles, - плюс режим редактирования для админов.

Тексты по умолчанию лежат в шаблоне; в БД попадает только то, что админ
изменил. Читаются правки через кэш в Redis, поэтому обычная загрузка страницы
не ходит в Postgres.
"""

from __future__ import annotations

import asyncio
import json
import mimetypes
import uuid
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.templating import Jinja2Templates
from loguru import logger
from markupsafe import Markup, escape
from pydantic import BaseModel, Field

from bot.common.service.hint_viewer_web_service import resolve_web_session
from bot.common.service.landing_text_service import (
    get_overrides,
    save_image,
    valid_image_key,
    reset_all,
    save_items,
    style_to_css,
)
from bot.common.service.landing_blocks import (
    MAX_BLOCKS_PER_SECTION,
    PAGE_SECTIONS,
    SECTIONS,
    build_blocks,
    new_block_id,
)
from bot.common.service.landing_articles import (
    DEFAULT_BODY,
    DEFAULT_LEAD,
    DEFAULT_TITLE,
    article_card,
    article_url,
    cover_key,
    create_article,
    delete_article,
    index_of,
    lead_key,
    list_cards,
    owner_of,
    set_published,
    title_key,
    valid_article_id,
)
from bot.common.service.landing_text_service import (
    ARTICLES_PAGE,
    HREF_KEY_PREFIX,
    IMAGE_KEY_PREFIX,
    LEGACY_PART_ID,
    PAGE_BG_PREFIX,
    bg_of,
    body_parts,
    drop_block_keys,
    get_layouts,
    get_page_order,
    page_css,
    part_key,
    presets_of,
    save_backgrounds,
    save_bodies,
    save_layout,
    save_page_order,
    save_presets,
)
from bot.common.utils.static_assets import get_static_asset_version

web_landing_api_router = APIRouter()

templates = Jinja2Templates(directory="bot/templates")

LANDING_PATH = "/web"


class LandingSaveItem(BaseModel):
    key: str = Field(max_length=80)
    text: str = Field(default="", max_length=4000)
    style: dict[str, Any] | None = None
    # None - адрес не трогаем; строка (в том числе пустая) - записать или
    # вернуть шаблонный
    href: str | None = Field(default=None, max_length=500)


class LandingBlockBody(BaseModel):
    section: str = Field(max_length=20)
    action: str = Field(max_length=10)
    block_id: str = Field(default="", max_length=40)
    # для action=move: полный новый порядок id блоков секции
    order: list[str] = Field(default_factory=list, max_length=60)


class LandingBgItem(BaseModel):
    target: str = Field(max_length=75)
    # None или пустой - вернуть фон по умолчанию
    bg: dict[str, Any] | None = None


class LandingBodyItem(BaseModel):
    owner: str = Field(max_length=75)
    # [{id, t}] в порядке показа; проверяет clean_parts
    parts: list[dict[str, Any]] = Field(default_factory=list, max_length=200)


class LandingSaveBody(BaseModel):
    items: list[LandingSaveItem] = Field(default_factory=list)
    backgrounds: list[LandingBgItem] = Field(default_factory=list)
    bodies: list[LandingBodyItem] = Field(default_factory=list)


class LandingArticleBody(BaseModel):
    action: str = Field(max_length=12)
    id: str = Field(default="", max_length=20)
    published: bool = False


class LandingOrderBody(BaseModel):
    order: list[str] = Field(default_factory=list, max_length=20)


class LandingPresetsBody(BaseModel):
    items: list[dict[str, Any]] = Field(default_factory=list, max_length=60)


def _build_helpers(overrides: dict[str, dict[str, Any]]):
    """
    Три функции для шаблона:
      lp_attr('hero.title')  → data-lp="hero.title" style="…"
      lp_text('hero.title', 'Текст по умолчанию') → актуальный текст
      lp_defaults()          → JSON с исходниками подменённых ключей

    Исходники нужны кнопке «Сброс» в редакторе: страница уже отдана с
    подменённым текстом, и вернуть шаблонный вариант браузеру больше неоткуда.
    Собираются по ходу рендера, поэтому lp_defaults() вызывается в конце body.
    """
    defaults: dict[str, str] = {}
    href_defaults: dict[str, str] = {}

    def lp_attr(key: str) -> Markup:
        entry = overrides.get(key) or {}
        style = entry.get("style")
        css = style_to_css(style)
        attr = f'data-lp="{escape(key)}"'
        if css:
            attr += f' style="{escape(css)}"'
        if style:
            # редактор читает текущее состояние отсюда, без отдельного запроса
            attr += f' data-lp-style="{escape(json.dumps(style, ensure_ascii=False))}"'
        return Markup(attr)

    def lp_text(key: str, default: str = "") -> str:
        text = (overrides.get(key) or {}).get("text")
        if not text:
            return default
        defaults[key] = default
        return text

    def lp_img(key: str, default_src: str) -> str:
        """Адрес картинки: загруженная админом либо та, что в репозитории."""
        entry = overrides.get(f"{IMAGE_KEY_PREFIX}{key}") or {}
        return entry.get("text") or default_src

    def lp_href(key: str, default_href: str) -> str:
        """Адрес ссылки: заданный админом либо тот, что в шаблоне."""
        entry = overrides.get(f"{HREF_KEY_PREFIX}{key}") or {}
        value = (entry.get("text") or "").strip()
        if value:
            href_defaults[key] = default_href
            return value
        return default_href

    def lp_defaults() -> Markup:
        # "</" экранируем, иначе текст с тегом закроет <script> раньше времени
        raw = json.dumps(defaults, ensure_ascii=False).replace("</", "<\\/")
        return Markup(raw)

    def lp_href_defaults() -> Markup:
        raw = json.dumps(href_defaults, ensure_ascii=False).replace("</", "<\\/")
        return Markup(raw)

    return lp_attr, lp_text, lp_defaults, lp_img, lp_href, lp_href_defaults


def _no_html(*_args: Any) -> Markup:
    """Для обычных посетителей управляющих кнопок в разметке просто нет."""
    return Markup("")


def _block_remove_html(block: dict[str, Any]) -> Markup:
    """
    Панель блока в режиме правки: перетащить, сдвинуть, убрать. Стрелки
    нужны не только для клавиатуры - перетаскивание на телефонах не работает.
    """
    block_id = escape(block.get("id") or "")
    return Markup(
        '<span class="lbg-block-tools" data-lp-tools="%(id)s">'
        '<button type="button" class="lbg-block-drag" data-lp-block-drag="%(id)s"'
        ' title="Перетащить" aria-label="Перетащить блок">⠿</button>'
        '<button type="button" data-lp-block-up="%(id)s"'
        ' title="Сдвинуть раньше" aria-label="Сдвинуть раньше">↑</button>'
        '<button type="button" data-lp-block-down="%(id)s"'
        ' title="Сдвинуть позже" aria-label="Сдвинуть позже">↓</button>'
        '<button type="button" class="lbg-block-del" data-lp-block-del="%(id)s"'
        ' title="Убрать блок" aria-label="Убрать блок">×</button>'
        "</span>" % {"id": block_id}
    )


def _section_tools_html(name: str) -> Markup:
    """Стрелки для перестановки целой секции лендинга."""
    return Markup(
        '<span class="lbg-section-tools" data-lp-section-tools="%(n)s">'
        '<span class="lbg-section-tools__label">Секция</span>'
        '<button type="button" data-lp-section-up="%(n)s"'
        ' title="Поднять секцию" aria-label="Поднять секцию">↑</button>'
        '<button type="button" data-lp-section-down="%(n)s"'
        ' title="Опустить секцию" aria-label="Опустить секцию">↓</button>'
        "</span>" % {"n": escape(name)}
    )


def _bg_helpers(overrides: dict[str, dict[str, Any]]):
    """
    lp_bg(target)  - атрибуты цели фона: data-lp-bg и текущие цвета для
                     редактора;
    lp_page(name)  - то же для <body>: страница целиком.
    """

    def _attrs(target: str) -> str:
        bg = bg_of(overrides, target)
        if not bg:
            return ""
        return f' data-lp-bg-style="{escape(json.dumps(bg, ensure_ascii=False))}"'

    def lp_bg(target: str) -> Markup:
        return Markup(f'data-lp-bg="{escape(target)}"' + _attrs(target))

    def lp_page(name: str) -> Markup:
        target = f"{PAGE_BG_PREFIX}{name}"
        return Markup(
            f'data-lp-page="{escape(name)}" data-lp-page-bg="{escape(target)}"'
            + _attrs(target)
        )

    return lp_bg, lp_page


def _presets_json(overrides: dict[str, dict[str, Any]]) -> Markup:
    raw = json.dumps(presets_of(overrides), ensure_ascii=False).replace("</", "<\\/")
    return Markup(raw)


def _block_add_html(section: str) -> Markup:
    return Markup(
        '<button type="button" class="lbg-block-add" data-lp-block-add="%s">'
        "+ Добавить блок</button>" % escape(section)
    )


async def _is_landing_admin(request: Request) -> bool:
    session = getattr(request.state, "web_session", None)
    if session is None:
        session = await resolve_web_session(request)
    return bool((session or {}).get("is_admin"))


def _user_id(request: Request) -> int | None:
    session = getattr(request.state, "web_session", None) or {}
    user_id = session.get("user_id")
    return int(user_id) if user_id else None


def _session_flags(request: Request) -> tuple[bool, bool]:
    """
    (вошёл ли, админ ли). Сессия уже разобрана web_grant_user_middleware,
    повторно в Redis не ходим.
    """
    session = getattr(request.state, "web_session", None)
    return bool(session), bool((session or {}).get("is_admin"))


def _body_helper(overrides: dict[str, dict[str, Any]]):
    """
    lp_body(owner, legacy, default) - части текста для шаблона:
    [{id, t, key, default}]. legacy - прежний единственный абзац ответа FAQ,
    его текст остаётся под старым ключом; default - состав, пока админ
    ничего не менял.
    """

    def lp_body(
        owner: str,
        legacy: dict[str, str] | None = None,
        default: list[dict[str, str]] | None = None,
    ) -> list[dict[str, str]]:
        parts = body_parts(overrides, owner) or list(
            default or [{"id": LEGACY_PART_ID, "t": "p"}]
        )
        out: list[dict[str, str]] = []
        for part in parts:
            if part["id"] == LEGACY_PART_ID:
                if not legacy:
                    continue
                key, text_default = legacy["key"], legacy["default"]
            else:
                key, text_default = part_key(owner, part["id"]), ""
            out.append(
                {"id": part["id"], "t": part["t"], "key": key, "default": text_default}
            )
        return out

    return lp_body


def _page_context(
    request: Request,
    overrides: dict[str, dict[str, Any]],
    *,
    authorized: bool,
    is_admin: bool,
    **extra: Any,
) -> dict[str, Any]:
    """Общее для всех публичных страниц: вход, помощники шаблона, режим правки."""
    (
        lp_attr,
        lp_text,
        lp_defaults,
        lp_img,
        lp_href,
        lp_href_defaults,
    ) = _build_helpers(overrides)
    lp_bg, lp_page = _bg_helpers(overrides)
    context: dict[str, Any] = {
        "request": request,
        "login_url": "/web/hints" if authorized else "/login",
        "login_label": "В кабинет" if authorized else "Авторизоваться",
        "cache_timestamp": get_static_asset_version(),
        "can_edit": is_admin,
        "lp_attr": lp_attr,
        "lp_text": lp_text,
        "lp_defaults": lp_defaults,
        "lp_img": lp_img,
        "lp_href": lp_href,
        "lp_href_defaults": lp_href_defaults,
        "lp_block_remove": _block_remove_html if is_admin else _no_html,
        "lp_block_add": _block_add_html if is_admin else _no_html,
        "lp_section_tools": _no_html,
        "lp_bg": lp_bg,
        "lp_page": lp_page,
        "lp_body": _body_helper(overrides),
        "lp_presets": lambda: _presets_json(overrides),
        # Цвета зависят от темы, поэтому идут правилами в <style>, а не
        # инлайном. Markup обязателен: внутри <style> HTML-сущности не
        # декодируются, и экранированные кавычки сломали бы селекторы.
        # Содержимое безопасно - ключи и цвета проходят валидацию в page_css.
        "lp_color_css": Markup(page_css(overrides)),
    }
    context.update(extra)
    return context


async def _published_articles() -> list[dict[str, Any]]:
    return list_cards(await get_overrides(ARTICLES_PAGE), include_drafts=False)


@web_landing_api_router.get("/web", response_class=HTMLResponse)
async def web_landing(request: Request):
    """
    Лендинг доступен всем. Сессию не требуем, но если она есть - кнопки входа
    ведут сразу в кабинет, а админу подключается режим редактирования.
    """
    authorized, is_admin = _session_flags(request)
    overrides = await get_overrides()
    layouts = await get_layouts(overrides)
    blocks = {
        section: build_blocks(section, layouts.get(section)) for section in SECTIONS
    }
    articles = await _published_articles()
    return templates.TemplateResponse(
        "landing.html",
        _page_context(
            request,
            overrides,
            authorized=authorized,
            is_admin=is_admin,
            lp_section_tools=_section_tools_html if is_admin else _no_html,
            page_sections=await get_page_order(overrides),
            blocks=blocks,
            # пустую ленту посетителям не показываем, админ видит блок всегда
            show_articles=is_admin or bool(articles),
        ),
    )


@web_landing_api_router.get("/web/faq", response_class=HTMLResponse)
async def web_faq(request: Request):
    """
    Вопросы и ответы. Отдельная страница, чтобы лендинг не рос: на нём стоит
    только ссылка сюда. Наполняет её админ тем же режимом редактирования.
    """
    authorized, is_admin = _session_flags(request)
    overrides = await get_overrides()
    layouts = await get_layouts(overrides)
    articles = await _published_articles()
    return templates.TemplateResponse(
        "landing_faq.html",
        _page_context(
            request,
            overrides,
            authorized=authorized,
            is_admin=is_admin,
            blocks={"faq": build_blocks("faq", layouts.get("faq"))},
            show_articles=is_admin or bool(articles),
        ),
    )


@web_landing_api_router.get("/web/articles", response_class=HTMLResponse)
async def web_articles(request: Request):
    """Лента статей. Черновики видит только админ."""
    authorized, is_admin = _session_flags(request)
    overrides = await get_overrides()
    articles = await get_overrides(ARTICLES_PAGE)
    return templates.TemplateResponse(
        "landing_articles.html",
        _page_context(
            request,
            overrides,
            authorized=authorized,
            is_admin=is_admin,
            cards=list_cards(articles, include_drafts=is_admin),
            show_articles=True,
        ),
    )


@web_landing_api_router.get("/web/articles/{article_id}", response_class=HTMLResponse)
async def web_article(request: Request, article_id: str):
    """Статья. Черновик для всех, кроме админа, - как будто её нет."""
    authorized, is_admin = _session_flags(request)
    if not valid_article_id(article_id):
        raise HTTPException(status_code=404, detail="Статья не найдена")
    articles = await get_overrides(ARTICLES_PAGE)
    if article_id not in index_of(articles):
        raise HTTPException(status_code=404, detail="Статья не найдена")
    card = article_card(articles, article_id)
    if not card["published"] and not is_admin:
        raise HTTPException(status_code=404, detail="Статья не найдена")

    more = [
        item
        for item in list_cards(articles, include_drafts=False)
        if item["id"] != article_id
    ][:3]
    # Тексты статьи - из своей страницы-хранилища, а шапка, подвал и
    # пресеты - общие с лендингом. Ключи не пересекаются.
    overrides = {**(await get_overrides()), **articles}
    return templates.TemplateResponse(
        "landing_article.html",
        _page_context(
            request,
            overrides,
            authorized=authorized,
            is_admin=is_admin,
            article=card,
            keys={
                "owner": owner_of(article_id),
                "title": title_key(article_id),
                "lead": lead_key(article_id),
                "cover": cover_key(article_id),
            },
            default_title=DEFAULT_TITLE,
            default_lead=DEFAULT_LEAD,
            default_body=DEFAULT_BODY,
            more=more,
            show_articles=True,
        ),
    )


@web_landing_api_router.post("/web/landing/api/articles")
async def web_landing_articles_api(request: Request, body: LandingArticleBody):
    """Создать, опубликовать (снять с публикации) или удалить статью."""
    if not await _is_landing_admin(request):
        raise HTTPException(status_code=403, detail="forbidden")
    user_id = _user_id(request)
    action = (body.action or "").strip()

    if action == "create":
        try:
            article_id = await create_article(user_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        logger.info("landing article created: {}", article_id)
        return JSONResponse(
            {"ok": True, "id": article_id, "url": article_url(article_id)}
        )

    article_id = (body.id or "").strip()
    if not valid_article_id(article_id):
        raise HTTPException(status_code=400, detail="Некорректная статья")
    if action == "publish":
        done = await set_published(article_id, body.published, user_id)
    elif action == "delete":
        done = await delete_article(article_id, user_id)
    else:
        raise HTTPException(status_code=400, detail="Неизвестное действие")
    if not done:
        raise HTTPException(status_code=404, detail="Статья не найдена")
    logger.info("landing article {}: {} ({})", action, article_id, body.published)
    return JSONResponse({"ok": True})


@web_landing_api_router.post("/web/landing/api/save")
async def web_landing_save(request: Request, body: LandingSaveBody):
    if not await _is_landing_admin(request):
        raise HTTPException(status_code=403, detail="forbidden")

    session = getattr(request.state, "web_session", None) or {}
    user_id = session.get("user_id")
    uid = int(user_id) if user_id else None
    saved = await save_items([item.model_dump() for item in body.items], uid)
    saved_bg = await save_backgrounds(
        [item.model_dump() for item in body.backgrounds], uid
    )
    # состав - после текстов: так части, убранные из текста, гарантированно
    # уходят вместе со своими только что записанными правками
    saved_bodies = await save_bodies([item.model_dump() for item in body.bodies], uid)
    logger.info(
        "landing saved: {} ключей, {} фонов, {} текстов из частей, web_user={}",
        saved,
        saved_bg,
        saved_bodies,
        user_id,
    )
    return JSONResponse(
        {
            "status": "ok",
            "saved": saved,
            "backgrounds": saved_bg,
            "bodies": saved_bodies,
        }
    )


@web_landing_api_router.post("/web/landing/api/reset")
async def web_landing_reset(request: Request):
    if not await _is_landing_admin(request):
        raise HTTPException(status_code=403, detail="forbidden")
    removed = await reset_all()
    logger.info("landing texts reset: {} строк", removed)
    return JSONResponse({"status": "ok", "removed": removed})


@web_landing_api_router.post("/web/landing/api/blocks")
async def web_landing_blocks(request: Request, body: LandingBlockBody):
    """
    Добавляет или убирает блок секции. Меняется только раскладка: тексты
    штатных блоков остаются в БД, поэтому убранный блок можно вернуть
    «Сбросом» без потери правок.
    """
    if not await _is_landing_admin(request):
        raise HTTPException(status_code=403, detail="forbidden")
    section = (body.section or "").strip()
    if section not in SECTIONS:
        raise HTTPException(status_code=400, detail="Неизвестная секция")

    session = getattr(request.state, "web_session", None) or {}
    user_id = session.get("user_id")
    user_id = int(user_id) if user_id else None

    layouts = await get_layouts()
    current = layouts.get(section)
    if current is None:
        current = [block["id"] for block in build_blocks(section, None)]

    action = (body.action or "").strip()
    block_id = (body.block_id or "").strip()
    if action == "add":
        if len(current) >= MAX_BLOCKS_PER_SECTION:
            raise HTTPException(status_code=400, detail="Слишком много блоков")
        block_id = new_block_id()
        current = current + [block_id]
    elif action == "remove":
        if block_id not in current:
            raise HTTPException(status_code=404, detail="Блок не найден")
        current = [item for item in current if item != block_id]
    elif action == "move":
        # принимаем только перестановку текущего состава: добавлять и убирать
        # блоки через move нельзя, иначе раскладку легко испортить
        order = [str(item or "").strip() for item in body.order]
        if len(order) != len(current) or set(order) != set(current):
            raise HTTPException(
                status_code=409,
                detail="Состав секции изменился, обновите страницу",
            )
        current = order
    else:
        raise HTTPException(status_code=400, detail="Неизвестное действие")

    await save_layout(section, current, user_id)
    if action == "remove":
        # свой блок уносим целиком: возвращать его неоткуда
        await drop_block_keys(section, block_id)
    logger.info("landing block {}: {} / {}", action, section, block_id)
    return JSONResponse({"ok": True, "block_id": block_id, "blocks": current})


@web_landing_api_router.post("/web/landing/api/sections")
async def web_landing_sections(request: Request, body: LandingOrderBody):
    """Новый порядок переставляемых секций лендинга."""
    if not await _is_landing_admin(request):
        raise HTTPException(status_code=403, detail="forbidden")
    order = [str(item or "").strip() for item in body.order]
    if sorted(order) != sorted(PAGE_SECTIONS):
        raise HTTPException(status_code=400, detail="Некорректный порядок секций")
    session = getattr(request.state, "web_session", None) or {}
    user_id = session.get("user_id")
    saved = await save_page_order(order, int(user_id) if user_id else None)
    logger.info("landing sections order: {}", saved)
    return JSONResponse({"ok": True, "order": saved})


@web_landing_api_router.post("/web/landing/api/presets")
async def web_landing_presets(request: Request, body: LandingPresetsBody):
    """Сохраняет весь список пресетов стилей целиком."""
    if not await _is_landing_admin(request):
        raise HTTPException(status_code=403, detail="forbidden")
    session = getattr(request.state, "web_session", None) or {}
    user_id = session.get("user_id")
    presets = await save_presets(body.items, int(user_id) if user_id else None)
    return JSONResponse({"ok": True, "items": presets})


# Картинки лендинга: меняются админом в режиме редактирования, лежат в S3
# рядом с остальным пользовательским контентом, а не в репозитории.
LANDING_IMAGE_MAX_BYTES = 8 * 1024 * 1024
LANDING_IMAGE_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


@web_landing_api_router.post("/web/landing/api/upload-image")
async def web_landing_upload_image(
    request: Request,
    key: str = Form(...),
    file: UploadFile = File(...),
):
    if not await _is_landing_admin(request):
        raise HTTPException(status_code=403, detail="forbidden")
    if not valid_image_key(key):
        raise HTTPException(status_code=400, detail="Некорректный ключ")

    ext = LANDING_IMAGE_TYPES.get((file.content_type or "").lower())
    if not ext:
        raise HTTPException(
            status_code=400, detail="Поддерживаются PNG, JPEG, WEBP и GIF"
        )
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Пустой файл")
    if len(raw) > LANDING_IMAGE_MAX_BYTES:
        raise HTTPException(status_code=400, detail="Файл больше 8 МБ")

    from bot.common.service.hint_s3_service import HintS3Storage

    s3 = HintS3Storage.from_settings()
    # имя со случайной частью, иначе браузер отдаст прежнюю картинку из кэша
    s3_key = HintS3Storage.landing_media_key(f"{key}-{uuid.uuid4().hex[:8]}{ext}")
    await asyncio.to_thread(s3.upload_bytes, s3_key, raw, file.content_type)

    url = f"/web/landing/image?key={quote(s3_key, safe='')}"
    session = getattr(request.state, "web_session", None) or {}
    user_id = session.get("user_id")
    await save_image(key, url, int(user_id) if user_id else None)
    logger.info("landing image uploaded: {} -> {}", key, s3_key)
    return JSONResponse({"ok": True, "url": url})


@web_landing_api_router.get("/web/landing/image")
async def web_landing_image(key: str):
    """Отдаёт картинку лендинга. Ключ ограничен своим префиксом в S3."""
    from bot.common.service.hint_s3_service import HintS3Storage

    if not HintS3Storage.is_landing_media_key(key):
        raise HTTPException(status_code=400, detail="Некорректный key")
    s3 = HintS3Storage.from_settings()
    if not await asyncio.to_thread(s3.exists, key):
        raise HTTPException(status_code=404, detail="Файл не найден")
    blob = await asyncio.to_thread(s3.download_bytes, key)
    media_type = (
        mimetypes.guess_type(key.rsplit("/", 1)[-1])[0] or "application/octet-stream"
    )
    return Response(
        content=blob,
        media_type=media_type,
        # имя объекта уникально, поэтому кэшируем надолго
        headers={"Cache-Control": "public, max-age=604800, immutable"},
    )
