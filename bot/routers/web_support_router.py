"""Веб-чат поддержки: виджет пользователя и inbox для админов."""

from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from loguru import logger

from bot.common.service.hint_s3_service import HintS3Storage
from bot.common.service.hint_viewer_web_service import (
    COOKIE_NAME,
    attach_device_cookie,
    device_id_from_request,
    resolve_web_session,
    web_cabinet_page_vars,
)
from bot.common.service.web_support_service import (
    add_message,
    admin_unread_count,
    check_rate_limit,
    get_attachment,
    get_or_create_thread,
    get_thread_by_id,
    get_thread_by_user,
    list_inbox,
    mark_read,
    sanitize_source_path,
    serialize_message,
    serialize_thread_messages,
    serialize_thread_meta,
    user_unread,
    INBOX_PAGE_SIZE,
    MAX_FILES,
)
from bot.common.utils.static_assets import get_static_asset_version
from bot.db.database import async_session_maker
from bot.db.models import WebSupportAuthorRole, WebUser

web_support_api_router = APIRouter()
templates = Jinja2Templates(directory="bot/templates")
templates.env.globals["cache_timestamp"] = get_static_asset_version()


def _login_redirect(next_path: str = "/web/support") -> RedirectResponse:
    return RedirectResponse(
        url=f"/web/hints/login?next={next_path}",
        status_code=303,
    )


async def _require_session(request: Request) -> tuple[str, dict[str, Any]]:
    token = request.cookies.get(COOKIE_NAME)
    session = await resolve_web_session(request)
    if not token or not session:
        raise HTTPException(status_code=401, detail="Нужна авторизация")
    return token, session


async def _require_admin(request: Request) -> tuple[str, dict[str, Any]]:
    token, session = await _require_session(request)
    if not session.get("is_admin"):
        raise HTTPException(status_code=403, detail="Нужны права администратора")
    return token, session


def _user_id(session: dict[str, Any]) -> int:
    return int(session["user_id"])


def _disposition(filename: str) -> str:
    raw = (filename or "file").replace("\\", "/").split("/")[-1].strip() or "file"
    ascii_name = "".join(c if c.isascii() and c not in '"\\' else "_" for c in raw)[:180]
    encoded = quote(raw, safe="")
    return f'attachment; filename="{ascii_name or "file"}"; filename*=UTF-8\'\'{encoded}'


@web_support_api_router.get("/web/support", response_class=HTMLResponse)
async def web_support_inbox_page(request: Request):
    session = await resolve_web_session(request)
    if not session:
        return _login_redirect("/web/support")
    if not session.get("is_admin"):
        return RedirectResponse(url="/web/hints", status_code=303)
    response = templates.TemplateResponse(
        "web_support_inbox.html",
        {
            "request": request,
            **web_cabinet_page_vars("hints"),
            "cache_timestamp": get_static_asset_version(),
            "is_admin": True,
            "hide_support_widget": True,
            "page_title": "Поддержка",
            "web_service": "support",
        },
    )
    attach_device_cookie(response, device_id_from_request(request))
    return response


@web_support_api_router.get("/web/support/api/unread")
async def web_support_unread(request: Request):
    _token, session = await _require_session(request)
    async with async_session_maker() as db:
        if session.get("is_admin"):
            count = await admin_unread_count(db)
        else:
            count = await user_unread(db, _user_id(session))
    return {"ok": True, "unread": count, "admin": bool(session.get("is_admin"))}


@web_support_api_router.get("/web/support/api/thread")
async def web_support_own_thread(
    request: Request,
    after_id: int = Query(0),
    mark: int = Query(0),
):
    _token, session = await _require_session(request)
    uid = _user_id(session)
    async with async_session_maker() as db:
        thread = await get_thread_by_user(db, uid)
        if not thread:
            return {"ok": True, "thread": None, "messages": [], "unread": 0}
        login_row = await db.get(WebUser, uid)
        if mark:
            await mark_read(db, thread, is_admin=False)
        messages = await serialize_thread_messages(db, thread, after_id=after_id)
        meta = serialize_thread_meta(
            thread,
            login=getattr(login_row, "login", None),
            is_admin=False,
        )
    return {"ok": True, "thread": meta, "messages": messages}


@web_support_api_router.post("/web/support/api/thread/messages")
async def web_support_own_send(
    request: Request,
    text: str = Form(""),
    source_path: str = Form(""),
    files: list[UploadFile] | None = File(None),
):
    _token, session = await _require_session(request)
    uid = _user_id(session)
    allowed, wait_sec = await check_rate_limit(uid)
    if not allowed:
        minutes = wait_sec // 60
        seconds = wait_sec % 60
        wait_text = (
            f"{minutes} мин {seconds} сек" if minutes > 0 else f"{seconds} сек"
        )
        raise HTTPException(
            status_code=429,
            detail={"message": "Слишком много сообщений", "wait_text": wait_text},
        )
    uploads = await _read_uploads(files)
    async with async_session_maker() as db:
        thread = await get_or_create_thread(db, uid)
        try:
            message = await add_message(
                db,
                thread=thread,
                author_user_id=uid,
                author_role=WebSupportAuthorRole.USER.value,
                body=text,
                source_path=sanitize_source_path(source_path),
                files=uploads,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        login_row = await db.get(WebUser, uid)
        payload = serialize_message(
            message, author_login=getattr(login_row, "login", None)
        )
    return {"ok": True, "message": payload}


@web_support_api_router.get("/web/support/api/inbox")
async def web_support_inbox(
    request: Request,
    q: str = Query(""),
    page: int = Query(1),
):
    await _require_admin(request)
    async with async_session_maker() as db:
        items, total = await list_inbox(db, query=q, page=page)
        unread = await admin_unread_count(db)
    pages = max(1, (total + INBOX_PAGE_SIZE - 1) // INBOX_PAGE_SIZE)
    return {
        "ok": True,
        "items": items,
        "total": total,
        "page": max(1, page),
        "pages": pages,
        "unread": unread,
    }


@web_support_api_router.get("/web/support/api/threads/{thread_id}")
async def web_support_thread_detail(
    request: Request,
    thread_id: int,
    after_id: int = Query(0),
    mark: int = Query(0),
):
    await _require_admin(request)
    async with async_session_maker() as db:
        thread = await get_thread_by_id(db, thread_id)
        if not thread:
            raise HTTPException(status_code=404, detail="Диалог не найден")
        login = getattr(thread.user, "login", None)
        if mark:
            await mark_read(db, thread, is_admin=True)
        messages = await serialize_thread_messages(db, thread, after_id=after_id)
        meta = serialize_thread_meta(
            thread,
            login=login,
            is_admin=True,
        )
    return {"ok": True, "thread": meta, "messages": messages}


@web_support_api_router.post("/web/support/api/threads/{thread_id}/messages")
async def web_support_admin_send(
    request: Request,
    thread_id: int,
    text: str = Form(""),
    files: list[UploadFile] | None = File(None),
):
    _token, session = await _require_admin(request)
    uid = _user_id(session)
    uploads = await _read_uploads(files)
    async with async_session_maker() as db:
        thread = await get_thread_by_id(db, thread_id)
        if not thread:
            raise HTTPException(status_code=404, detail="Диалог не найден")
        try:
            message = await add_message(
                db,
                thread=thread,
                author_user_id=uid,
                author_role=WebSupportAuthorRole.ADMIN.value,
                body=text,
                source_path=None,
                files=uploads,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        login_row = await db.get(WebUser, uid)
        payload = serialize_message(
            message, author_login=getattr(login_row, "login", None)
        )
    return {"ok": True, "message": payload}


@web_support_api_router.get("/web/support/api/files/{attachment_id}")
async def web_support_file(request: Request, attachment_id: int):
    _token, session = await _require_session(request)
    async with async_session_maker() as db:
        att = await get_attachment(db, attachment_id)
        if not att or not att.message or not att.message.thread:
            raise HTTPException(status_code=404, detail="Файл не найден")
        thread = att.message.thread
        is_owner = int(thread.user_id) == _user_id(session)
        if not is_owner and not session.get("is_admin"):
            raise HTTPException(status_code=403, detail="Нет доступа")
        if not HintS3Storage.is_support_attachment_key(att.s3_key):
            raise HTTPException(status_code=404, detail="Файл не найден")
        s3 = HintS3Storage.from_settings()
        try:
            data = await asyncio.to_thread(s3.download_bytes, att.s3_key)
        except Exception:
            logger.exception("support file download failed id={}", attachment_id)
            raise HTTPException(status_code=404, detail="Файл не найден") from None
    inline = att.content_type.startswith("image/")
    headers = {
        "Content-Disposition": (
            f'inline; filename="{_safe_ascii(att.original_filename)}"'
            if inline
            else _disposition(att.original_filename)
        )
    }
    return Response(
        content=data,
        media_type=att.content_type or "application/octet-stream",
        headers=headers,
    )


def _safe_ascii(name: str) -> str:
    raw = (name or "file").replace("\\", "/").split("/")[-1].strip() or "file"
    cleaned = "".join(c if c.isascii() and c not in '"\\' else "_" for c in raw)
    return (cleaned or "file")[:180]


async def _read_uploads(files: list[UploadFile] | None) -> list[tuple[str, bytes, str | None]]:
    uploads: list[tuple[str, bytes, str | None]] = []
    for upload in files or []:
        if not upload or not upload.filename:
            continue
        data = await upload.read()
        if not data:
            continue
        uploads.append((upload.filename, data, upload.content_type))
        if len(uploads) > MAX_FILES:
            raise HTTPException(
                status_code=400,
                detail=f"Можно прикрепить не больше {MAX_FILES} файлов",
            )
    return uploads
