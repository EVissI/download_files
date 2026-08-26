"""Веб-кабинеты карточек, пипсов и анализа матча (сессия WebUser, без Telegram)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from bot.common.service.hint_viewer_web_service import (
    COOKIE_NAME,
    get_session,
    web_user_is_admin,
)
from bot.db.models import ContentCardPool

content_cards_web_api_router = APIRouter()


def _login_redirect(next_path: str) -> RedirectResponse:
    return RedirectResponse(
        url=f"/web/hints/login?next={next_path}",
        status_code=303,
    )


async def _require_web_page(request: Request, next_path: str) -> dict[str, Any] | RedirectResponse:
    token = request.cookies.get(COOKIE_NAME)
    session = await get_session(token)
    if not session:
        return _login_redirect(next_path)
    return session


@content_cards_web_api_router.get("/web/cards", response_class=HTMLResponse)
async def web_cards_cabinet(request: Request):
    session = await _require_web_page(request, "/web/cards")
    if isinstance(session, RedirectResponse):
        return session
    from bot.api import _render_content_cards_cabinet_page

    is_admin = await web_user_is_admin(session.get("user_id"))
    return await _render_content_cards_cabinet_page(
        request,
        ContentCardPool.CARDS,
        web_standalone=True,
        is_admin=is_admin,
        cabinet_base_path="/web/cards",
    )


@content_cards_web_api_router.get("/web/pip-count", response_class=HTMLResponse)
async def web_pip_count_cabinet(request: Request):
    session = await _require_web_page(request, "/web/pip-count")
    if isinstance(session, RedirectResponse):
        return session
    from bot.api import _render_content_cards_cabinet_page

    is_admin = await web_user_is_admin(session.get("user_id"))
    return await _render_content_cards_cabinet_page(
        request,
        ContentCardPool.PIP_COUNT,
        web_standalone=True,
        is_admin=is_admin,
        cabinet_base_path="/web/pip-count",
    )


@content_cards_web_api_router.get("/web/match-analysis", response_class=HTMLResponse)
async def web_match_analysis_cabinet(request: Request):
    session = await _require_web_page(request, "/web/match-analysis")
    if isinstance(session, RedirectResponse):
        return session
    from bot.routers.match_analysis_router import render_match_analysis_cabinet_page

    is_admin = await web_user_is_admin(session.get("user_id"))
    return await render_match_analysis_cabinet_page(
        request,
        web_standalone=True,
        is_admin=is_admin,
        cabinet_base_path="/web/match-analysis",
    )
