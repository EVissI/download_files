"""
Публичный лендинг веб-сервисов на /web (единственная страница без авторизации)
плюс режим редактирования текстов для админов.

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
    colors_css,
    get_overrides,
    save_image,
    valid_image_key,
    reset_all,
    save_items,
    style_to_css,
)
from bot.common.service.landing_text_service import IMAGE_KEY_PREFIX
from bot.common.utils.static_assets import get_static_asset_version

web_landing_api_router = APIRouter()

templates = Jinja2Templates(directory="bot/templates")

LANDING_PATH = "/web"


class LandingSaveItem(BaseModel):
    key: str = Field(max_length=80)
    text: str = Field(default="", max_length=4000)
    style: dict[str, Any] | None = None


class LandingSaveBody(BaseModel):
    items: list[LandingSaveItem] = Field(default_factory=list)


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

    def lp_defaults() -> Markup:
        # "</" экранируем, иначе текст с тегом закроет <script> раньше времени
        raw = json.dumps(defaults, ensure_ascii=False).replace("</", "<\\/")
        return Markup(raw)

    return lp_attr, lp_text, lp_defaults, lp_img


async def _is_landing_admin(request: Request) -> bool:
    session = getattr(request.state, "web_session", None)
    if session is None:
        session = await resolve_web_session(request)
    return bool((session or {}).get("is_admin"))


@web_landing_api_router.get("/web", response_class=HTMLResponse)
async def web_landing(request: Request):
    """
    Лендинг доступен всем. Сессию не требуем, но если она есть — кнопки входа
    ведут сразу в кабинет, а админу подключается режим редактирования.
    Сессия уже разобрана web_grant_user_middleware, повторно в Redis не ходим.
    """
    session = getattr(request.state, "web_session", None)
    authorized = bool(session)
    is_admin = bool((session or {}).get("is_admin"))

    overrides = await get_overrides()
    lp_attr, lp_text, lp_defaults, lp_img = _build_helpers(overrides)
    # Цвета зависят от темы, поэтому идут правилами в <style>, а не инлайном.
    # Markup обязателен: внутри <style> HTML-сущности не декодируются, и
    # экранированные кавычки сломали бы селекторы. Содержимое безопасно —
    # ключи и цвета проходят валидацию в colors_css.
    color_css = Markup(colors_css(overrides))

    return templates.TemplateResponse(
        "landing.html",
        {
            "request": request,
            "login_url": "/web/hints" if authorized else "/login",
            "login_label": "В кабинет" if authorized else "Авторизоваться",
            "cache_timestamp": get_static_asset_version(),
            "can_edit": is_admin,
            "lp_attr": lp_attr,
            "lp_text": lp_text,
            "lp_defaults": lp_defaults,
            "lp_img": lp_img,
            "lp_color_css": color_css,
        },
    )


@web_landing_api_router.post("/web/landing/api/save")
async def web_landing_save(request: Request, body: LandingSaveBody):
    if not await _is_landing_admin(request):
        raise HTTPException(status_code=403, detail="forbidden")

    session = getattr(request.state, "web_session", None) or {}
    user_id = session.get("user_id")
    saved = await save_items(
        [item.model_dump() for item in body.items],
        int(user_id) if user_id else None,
    )
    logger.info("landing texts saved: {} ключей, web_user={}", saved, user_id)
    return JSONResponse({"status": "ok", "saved": saved})


@web_landing_api_router.post("/web/landing/api/reset")
async def web_landing_reset(request: Request):
    if not await _is_landing_admin(request):
        raise HTTPException(status_code=403, detail="forbidden")
    removed = await reset_all()
    logger.info("landing texts reset: {} строк", removed)
    return JSONResponse({"status": "ok", "removed": removed})


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
