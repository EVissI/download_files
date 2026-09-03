"""Веб-чат поддержки: виджет пользователя и inbox для админов."""

from __future__ import annotations

import asyncio
import base64
import binascii
import shutil
import tempfile
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
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
from bot.common.utils.http_security import cookies_should_be_secure
from bot.common.service.web_support_service import (
    add_message,
    admin_unread_count,
    admin_unread_payload,
    check_rate_limit,
    get_attachment,
    get_message,
    get_or_create_thread,
    get_thread_by_id,
    get_thread_by_user,
    list_inbox,
    mark_read,
    sanitize_source_path,
    serialize_thread_messages,
    serialize_thread_meta,
    user_unread,
    INBOX_PAGE_SIZE,
    MAX_FILES,
    ALLOWED_EXT,
    attachment_ok_for_hints,
    is_order_analysis_message,
    _ext,
    _safe_filename,
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
    attach_device_cookie(
        response,
        device_id_from_request(request),
        secure=cookies_should_be_secure(request),
    )
    return response


@web_support_api_router.get("/web/support/api/unread")
async def web_support_unread(request: Request):
    _token, session = await _require_session(request)
    async with async_session_maker() as db:
        if session.get("is_admin"):
            payload = await admin_unread_payload(db)
            return {"ok": True, "admin": True, **payload}
        count = await user_unread(db, _user_id(session))
    return {"ok": True, "unread": count, "admin": False}


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
        await db.commit()
    return {"ok": True, "thread": meta, "messages": messages}


@web_support_api_router.post("/web/support/api/thread/messages")
async def web_support_own_send(request: Request):
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
    text, source_path, uploads = await _load_send_payload(request)
    async with async_session_maker() as db:
        thread = await get_or_create_thread(db, uid)
        login_row = await db.get(WebUser, uid)
        try:
            payload = await add_message(
                db,
                thread=thread,
                author_user_id=uid,
                author_role=WebSupportAuthorRole.USER.value,
                author_login=getattr(login_row, "login", None),
                body=text,
                source_path=sanitize_source_path(source_path),
                files=uploads,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
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
        login = getattr(getattr(thread, "user", None), "login", None)
        if mark:
            await mark_read(db, thread, is_admin=True)
        messages = await serialize_thread_messages(
            db, thread, after_id=after_id, include_source=True
        )
        meta = serialize_thread_meta(
            thread,
            login=login,
            is_admin=True,
        )
        await db.commit()
    return {"ok": True, "thread": meta, "messages": messages}


@web_support_api_router.post("/web/support/api/threads/{thread_id}/messages")
async def web_support_admin_send(request: Request, thread_id: int):
    _token, session = await _require_admin(request)
    uid = _user_id(session)
    text, _source_path, uploads = await _load_send_payload(request)
    async with async_session_maker() as db:
        thread = await get_thread_by_id(db, thread_id)
        if not thread:
            raise HTTPException(status_code=404, detail="Диалог не найден")
        login_row = await db.get(WebUser, uid)
        try:
            payload = await add_message(
                db,
                thread=thread,
                author_user_id=uid,
                author_role=WebSupportAuthorRole.ADMIN.value,
                author_login=getattr(login_row, "login", None),
                body=text,
                source_path=None,
                files=uploads,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "message": payload}


@web_support_api_router.post(
    "/web/support/api/threads/{thread_id}/messages/{message_id}/send-to-hints"
)
async def web_support_send_message_to_hints(
    request: Request, thread_id: int, message_id: int
):
    token, session = await _require_admin(request)
    async with async_session_maker() as db:
        message = await get_message(db, message_id)
        if (
            not message
            or not message.thread
            or int(message.thread_id) != int(thread_id)
        ):
            raise HTTPException(status_code=404, detail="Сообщение не найдено")
        attachments = list(message.attachments or [])
        if not is_order_analysis_message(message, attachments):
            raise HTTPException(status_code=400, detail="Это не заявка на анализ")
        att = next(
            (
                item
                for item in attachments
                if attachment_ok_for_hints(item.original_filename)
            ),
            None,
        )
        if not att or not HintS3Storage.is_support_attachment_key(att.s3_key):
            raise HTTPException(status_code=404, detail="Файл не найден")
        s3_key = att.s3_key
        filename = att.original_filename
        attachment_id = att.id
    s3 = HintS3Storage.from_settings()
    try:
        file_bytes = await asyncio.to_thread(s3.download_bytes, s3_key)
    except Exception:
        logger.exception("support send-to-hints download failed id={}", attachment_id)
        raise HTTPException(status_code=404, detail="Файл не найден") from None
    if not file_bytes:
        raise HTTPException(status_code=404, detail="Файл не найден")

    from bot.routers.hint_viewer_web_router import (
        _enqueue_batch,
        _enqueue_single,
        collect_mat_files_from_bytes,
    )

    workdir = tempfile.mkdtemp(prefix="support_hints_")
    try:
        collected = collect_mat_files_from_bytes(filename, file_bytes, workdir)
        if not collected:
            raise HTTPException(
                status_code=400,
                detail="Вложение не содержит файл .mat",
            )
        web_uid = int(session.get("web_uid") or -int(session.get("user_id") or 1))
        user_id = session.get("user_id")
        user_id = int(user_id) if user_id else None
        if len(collected) == 1:
            local_mat, stored_name = collected[0]
            job = await _enqueue_single(
                local_mat=local_mat,
                filename=stored_name,
                web_uid=web_uid,
                session_token=token,
                user_id=user_id,
            )
        else:
            job = await _enqueue_batch(
                files=collected,
                web_uid=web_uid,
                session_token=token,
                user_id=user_id,
            )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(
            "support send-to-hints failed thread={} message={}", thread_id, message_id
        )
        raise HTTPException(
            status_code=500, detail="Не удалось отправить файл в Ошибки"
        ) from exc
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
    return JSONResponse({"ok": True, "redirect": "/web/hints", "job": job})


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
        s3_key = att.s3_key
        content_type = att.content_type or "application/octet-stream"
        filename = att.original_filename
        s3 = HintS3Storage.from_settings()
        try:
            data = await asyncio.to_thread(s3.download_bytes, s3_key)
        except Exception:
            logger.exception("support file download failed id={}", attachment_id)
            raise HTTPException(status_code=404, detail="Файл не найден") from None
    inline = content_type.startswith("image/")
    headers = {
        "Content-Disposition": (
            f'inline; filename="{_safe_ascii(filename)}"'
            if inline
            else _disposition(filename)
        )
    }
    return Response(
        content=data,
        media_type=content_type,
        headers=headers,
    )


def _safe_ascii(name: str) -> str:
    raw = (name or "file").replace("\\", "/").split("/")[-1].strip() or "file"
    cleaned = "".join(c if c.isascii() and c not in '"\\' else "_" for c in raw)
    return (cleaned or "file")[:180]


def _form_text(form, key: str) -> str:
    value = form.get(key)
    if value is None or isinstance(value, UploadFile):
        return ""
    return str(value)


def _form_strings(form, key: str) -> list[str]:
    if not hasattr(form, "getlist"):
        value = _form_text(form, key)
        return [value] if value else []
    return [
        str(value)
        for value in form.getlist(key)
        if not isinstance(value, UploadFile)
    ]


def _decode_b64(value: Any) -> bytes:
    if not isinstance(value, str) or not value.strip():
        return b""
    raw = value.strip()
    if "," in raw and raw.lower().startswith("data:"):
        raw = raw.split(",", 1)[1]
    try:
        return base64.b64decode(raw, validate=False)
    except (binascii.Error, ValueError):
        return b""


def _uploads_from_json(raw: Any) -> list[tuple[str, bytes, str | None]]:
    items = raw if isinstance(raw, list) else []
    uploads: list[tuple[str, bytes, str | None]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        stored = str(item.get("name") or "file")
        original = str(item.get("original_name") or stored)
        ctype = str(item.get("content_type") or "") or None
        data = _decode_b64(item.get("data"))
        if not data:
            logger.warning("support json upload skipped empty name={}", stored)
            continue
        uploads.append((_pick_upload_filename(original, stored), data, ctype))
        if len(uploads) > MAX_FILES:
            raise HTTPException(
                status_code=400,
                detail=f"Можно прикрепить не больше {MAX_FILES} файлов",
            )
    return uploads


async def _load_send_payload(
    request: Request,
) -> tuple[str, str, list[tuple[str, bytes, str | None]]]:
    ctype = (request.headers.get("content-type") or "").lower()
    if "application/json" in ctype:
        try:
            body = await request.json()
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Некорректный запрос") from exc
        if not isinstance(body, dict):
            raise HTTPException(status_code=400, detail="Некорректный запрос")
        text = str(body.get("text") or "")
        source_path = str(body.get("source_path") or "")
        return text, source_path, _uploads_from_json(body.get("files"))
    form = await _parse_form(request)
    text = _form_text(form, "text")
    source_path = _form_text(form, "source_path")
    uploads = await _read_form_uploads(form)
    if not uploads:
        uploads = _uploads_from_b64_fields(form)
    return text, source_path, uploads


def _uploads_from_b64_fields(form) -> list[tuple[str, bytes, str | None]]:
    payloads = _form_strings(form, "file_b64")
    if not payloads:
        return []
    names = _form_strings(form, "file_names")
    types = _form_strings(form, "file_types")
    uploads: list[tuple[str, bytes, str | None]] = []
    for idx, raw in enumerate(payloads):
        data = _decode_b64(raw)
        if not data:
            continue
        stored = f"file-{idx}"
        preferred = names[idx] if idx < len(names) else stored
        ctype = types[idx] if idx < len(types) else None
        uploads.append((_pick_upload_filename(preferred, stored), data, ctype or None))
        if len(uploads) > MAX_FILES:
            raise HTTPException(
                status_code=400,
                detail=f"Можно прикрепить не больше {MAX_FILES} файлов",
            )
    return uploads


async def _parse_form(request: Request):
    max_part = 16 * 1024 * 1024
    try:
        return await request.form(
            max_files=20,
            max_fields=40,
            max_part_size=max_part,
        )
    except TypeError:
        try:
            return await request.form(max_files=20, max_fields=40)
        except TypeError:
            return await request.form()


def _uploads_from_form(form) -> list[UploadFile]:
    items: list[UploadFile] = []
    seen: set[int] = set()
    values: list[Any] = []
    if hasattr(form, "getlist"):
        values.extend(list(form.getlist("files") or []))
        values.extend(list(form.getlist("file") or []))
    if hasattr(form, "multi_items"):
        values.extend(value for _key, value in form.multi_items())
    for value in values:
        if not isinstance(value, UploadFile):
            continue
        ident = id(value)
        if ident in seen:
            continue
        seen.add(ident)
        items.append(value)
    return items


def _pick_upload_filename(preferred: str | None, fallback: str) -> str:
    fallback = fallback or "file"
    preferred = (preferred or "").strip()
    if not preferred:
        return fallback
    pref_ext = _ext(_safe_filename(preferred))
    fall_ext = _ext(fallback)
    if pref_ext in ALLOWED_EXT:
        return preferred
    if not pref_ext and fall_ext:
        return preferred + fall_ext
    return fallback


async def _read_form_uploads(form) -> list[tuple[str, bytes, str | None]]:
    names = [
        str(value)
        for value in form.getlist("file_names")
        if not isinstance(value, UploadFile)
    ]
    uploads = await _read_uploads(_uploads_from_form(form))
    if not names:
        return uploads
    return [
        (_pick_upload_filename(names[idx] if idx < len(names) else None, name), data, ctype)
        for idx, (name, data, ctype) in enumerate(uploads)
    ]


async def _read_uploads(files) -> list[tuple[str, bytes, str | None]]:
    if files is None:
        items: list[Any] = []
    elif isinstance(files, UploadFile):
        items = [files]
    else:
        items = list(files)
    uploads: list[tuple[str, bytes, str | None]] = []
    for upload in items:
        if not isinstance(upload, UploadFile):
            continue
        filename = upload.filename or "file"
        try:
            await upload.seek(0)
        except Exception:
            pass
        data = await upload.read()
        if not data:
            logger.warning("support upload skipped empty filename={}", filename)
            continue
        uploads.append((filename, data, upload.content_type))
        if len(uploads) > MAX_FILES:
            raise HTTPException(
                status_code=400,
                detail=f"Можно прикрепить не больше {MAX_FILES} файлов",
            )
    return uploads
