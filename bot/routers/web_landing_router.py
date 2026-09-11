"""Публичный лендинг веб-сервисов на /web (единственная страница без авторизации)."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from bot.common.utils.static_assets import get_static_asset_version

web_landing_api_router = APIRouter()

templates = Jinja2Templates(directory="bot/templates")

LANDING_PATH = "/web"


@web_landing_api_router.get("/web", response_class=HTMLResponse)
async def web_landing(request: Request):
    """
    Лендинг доступен всем. Сессию не требуем, но если она есть — кнопки входа
    ведут сразу в кабинет. Сессия уже разобрана web_grant_user_middleware,
    повторно в Redis не ходим.
    """
    authorized = bool(getattr(request.state, "web_session", None))
    return templates.TemplateResponse(
        "landing.html",
        {
            "request": request,
            "login_url": "/web/hints" if authorized else "/login",
            "login_label": "В кабинет" if authorized else "Авторизоваться",
            "cache_timestamp": get_static_asset_version(),
        },
    )
