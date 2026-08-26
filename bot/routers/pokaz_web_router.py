"""Веб-версия редактора позиций (pokaz) без Telegram."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from loguru import logger

from bot.common.func.pokaz_func import get_hints_for_xgid
from bot.common.service.hint_viewer_web_service import (
    COOKIE_NAME,
    get_session,
    web_user_is_admin,
)
from bot.common.service.webapp_settings_service import (
    get_pokaz_screenshot_font_scale_percent,
)
from bot.common.utils.static_assets import get_static_asset_version

pokaz_web_api_router = APIRouter()
templates = Jinja2Templates(directory="bot/templates")
templates.env.globals["cache_timestamp"] = get_static_asset_version()


def _login_redirect() -> RedirectResponse:
    return RedirectResponse(url="/web/hints/login?next=/web/pokaz", status_code=303)


async def _require_session(request: Request) -> tuple[str, dict[str, Any]]:
    token = request.cookies.get(COOKIE_NAME)
    session = await get_session(token)
    if not token or not session:
        raise HTTPException(status_code=401, detail="Нужна авторизация")
    return token, session


@pokaz_web_api_router.get("/web/pokaz", response_class=HTMLResponse)
async def web_pokaz_editor(request: Request, xgid: str | None = None, lang: str | None = None):
    token = request.cookies.get(COOKIE_NAME)
    session = await get_session(token)
    if not session:
        return _login_redirect()

    from bot.api import _get_pokaz_translations

    lang = lang if lang in ("ru", "en") else "ru"
    is_admin = await web_user_is_admin(session.get("user_id"))
    font_scale = await get_pokaz_screenshot_font_scale_percent()
    response = templates.TemplateResponse(
        "pokaz.html",
        {
            "request": request,
            "chat_id": None,
            "xgid": xgid,
            "lang": lang,
            "i18n": _get_pokaz_translations(lang),
            "cache_timestamp": get_static_asset_version(),
            "webapp_fullscreen_enabled": False,
            "pokaz_screenshot_font_scale_percent": font_scale,
            "web_standalone_mode": True,
            "web_service": "pokaz",
            "is_admin": is_admin,
        },
    )
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@pokaz_web_api_router.get("/web/pokaz/api/hints")
async def web_pokaz_hints(request: Request, xgid: str):
    await _require_session(request)
    if not (xgid or "").strip():
        raise HTTPException(status_code=400, detail="Нужен параметр xgid")
    try:
        hints = await asyncio.to_thread(get_hints_for_xgid, xgid.strip())
        return {"hints": hints or []}
    except Exception as e:
        logger.exception("web pokaz hints failed: {}", e)
        raise HTTPException(status_code=500, detail="Не удалось получить подсказки")
