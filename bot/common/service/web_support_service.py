"""Чат поддержки веб-кабинета: треды, сообщения, вложения."""

from __future__ import annotations

import mimetypes
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from loguru import logger
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from bot.common.service.hint_s3_service import HintS3Storage
from bot.db.models import (
    WebSupportAttachment,
    WebSupportAuthorRole,
    WebSupportMessage,
    WebSupportThread,
    WebUser,
)
from bot.db.redis import redis_client

MAX_BODY_LEN = 4000
MAX_FILES = 5
MAX_FILE_BYTES = 15 * 1024 * 1024
MAX_TOTAL_BYTES = 30 * 1024 * 1024
RATE_LIMIT_MAX = 20
RATE_LIMIT_WINDOW_SEC = 600
MESSAGE_LIMIT = 250
INBOX_PAGE_SIZE = 30

ALLOWED_EXT = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".bmp",
    ".pdf",
    ".txt",
    ".zip",
    ".mat",
    ".sgf",
    ".csv",
    ".doc",
    ".docx",
    ".xlsx",
}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
_SOURCE_RE = re.compile(r"^/web(/[A-Za-z0-9._~-]+)*$")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(ts: datetime | None) -> datetime | None:
    if ts is None:
        return None
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def sanitize_source_path(value: str | None) -> str | None:
    raw = (value or "").strip()
    if not raw:
        return None
    path = raw.split("?", 1)[0].split("#", 1)[0]
    if len(path) > 200 or not _SOURCE_RE.match(path):
        return None
    return path


def _safe_filename(name: str | None) -> str:
    base = (name or "file").replace("\\", "/").split("/")[-1].strip() or "file"
    cleaned = "".join(ch if ch.isascii() and ch not in '"\\' else "_" for ch in base)
    return (cleaned or "file")[:200]


def _ext(filename: str) -> str:
    lower = filename.lower()
    if "." not in lower:
        return ""
    return "." + lower.rsplit(".", 1)[-1]


def _preview(body: str, filenames: list[str]) -> str:
    text = " ".join((body or "").split())
    if text:
        return text[:240]
    if filenames:
        label = "Файл: " + filenames[0]
        extra = len(filenames) - 1
        if extra > 0:
            label += f" (+{extra})"
        return label[:240]
    return "Сообщение"


def _is_unread_for_admin(thread: WebSupportThread) -> bool:
    if thread.last_author_role != WebSupportAuthorRole.USER.value:
        return False
    if not thread.last_message_at:
        return False
    read_at = _aware(thread.admin_last_read_at)
    last_at = _aware(thread.last_message_at)
    return read_at is None or last_at > read_at


def _is_unread_for_user(thread: WebSupportThread) -> bool:
    if thread.last_author_role != WebSupportAuthorRole.ADMIN.value:
        return False
    if not thread.last_message_at:
        return False
    read_at = _aware(thread.user_last_read_at)
    last_at = _aware(thread.last_message_at)
    return read_at is None or last_at > read_at


def attachment_is_image(att: WebSupportAttachment) -> bool:
    ext = _ext(att.original_filename)
    ctype = (att.content_type or "").lower()
    return ext in IMAGE_EXT or ctype.startswith("image/")


def serialize_attachment(att: WebSupportAttachment) -> dict[str, Any]:
    return {
        "id": att.id,
        "filename": att.original_filename,
        "size": att.size_bytes,
        "content_type": att.content_type,
        "is_image": attachment_is_image(att),
        "url": f"/web/support/api/files/{att.id}",
    }


def serialize_message(
    message: WebSupportMessage,
    *,
    author_login: str | None,
) -> dict[str, Any]:
    created = _aware(getattr(message, "created_at", None))
    raw_attachments = message.__dict__.get("attachments") or []
    return {
        "id": message.id,
        "role": message.author_role,
        "author_login": author_login or "",
        "body": message.body or "",
        "created_at": created.isoformat() if created else None,
        "attachments": [serialize_attachment(att) for att in raw_attachments],
    }


async def check_rate_limit(user_id: int) -> tuple[bool, int]:
    key = f"rate_limit:web_support:{int(user_id)}"
    current = await redis_client.get(key)
    if current and int(current) >= RATE_LIMIT_MAX:
        ttl = await redis_client.ttl(key)
        return False, max(int(ttl or 0), 1)
    if not current:
        await redis_client.set(key, 1, expire=RATE_LIMIT_WINDOW_SEC)
    else:
        await redis_client.incr(key)
    return True, 0


async def get_thread_by_user(session, user_id: int) -> WebSupportThread | None:
    result = await session.execute(
        select(WebSupportThread).where(WebSupportThread.user_id == int(user_id))
    )
    return result.scalar_one_or_none()


async def get_thread_by_id(session, thread_id: int) -> WebSupportThread | None:
    result = await session.execute(
        select(WebSupportThread)
        .options(selectinload(WebSupportThread.user))
        .where(WebSupportThread.id == int(thread_id))
    )
    return result.scalar_one_or_none()


async def get_or_create_thread(session, user_id: int) -> WebSupportThread:
    thread = await get_thread_by_user(session, user_id)
    if thread:
        return thread
    thread = WebSupportThread(user_id=int(user_id))
    session.add(thread)
    try:
        await session.flush()
        return thread
    except IntegrityError:
        await session.rollback()
        existing = await get_thread_by_user(session, user_id)
        if existing:
            return existing
        raise


async def _author_logins(session, messages: list[WebSupportMessage]) -> dict[int, str]:
    ids = {int(m.author_user_id) for m in messages if m.author_user_id}
    if not ids:
        return {}
    result = await session.execute(
        select(WebUser.id, WebUser.login).where(WebUser.id.in_(ids))
    )
    return {int(uid): login for uid, login in result.all()}


async def load_messages(
    session,
    thread_id: int,
    *,
    after_id: int = 0,
) -> list[WebSupportMessage]:
    query = (
        select(WebSupportMessage)
        .options(selectinload(WebSupportMessage.attachments))
        .where(WebSupportMessage.thread_id == int(thread_id))
    )
    if after_id:
        query = query.where(WebSupportMessage.id > int(after_id)).order_by(
            WebSupportMessage.id.asc()
        )
        result = await session.execute(query)
        return list(result.scalars().all())
    result = await session.execute(
        query.order_by(WebSupportMessage.id.desc()).limit(MESSAGE_LIMIT)
    )
    return list(reversed(result.scalars().all()))


async def serialize_thread_messages(
    session,
    thread: WebSupportThread,
    *,
    after_id: int = 0,
) -> list[dict[str, Any]]:
    messages = await load_messages(session, thread.id, after_id=after_id)
    logins = await _author_logins(session, messages)
    return [
        serialize_message(msg, author_login=logins.get(int(msg.author_user_id)))
        for msg in messages
    ]


def serialize_thread_meta(
    thread: WebSupportThread,
    *,
    login: str | None,
    is_admin: bool,
) -> dict[str, Any]:
    last_at = _aware(thread.last_message_at)
    return {
        "id": thread.id,
        "user_id": thread.user_id,
        "login": login or "",
        "last_preview": thread.last_preview or "",
        "last_author_role": thread.last_author_role,
        "last_message_at": last_at.isoformat() if last_at else None,
        "unread": _is_unread_for_admin(thread) if is_admin else _is_unread_for_user(thread),
    }


async def mark_read(session, thread: WebSupportThread, *, is_admin: bool) -> None:
    now = _now()
    if is_admin:
        thread.admin_last_read_at = now
    else:
        thread.user_last_read_at = now
    await session.flush()


def validate_upload(filename: str, size: int) -> str | None:
    name = _safe_filename(filename)
    ext = _ext(name)
    if ext not in ALLOWED_EXT:
        return f"Тип файла не поддерживается: {name}"
    if size <= 0:
        return f"Пустой файл: {name}"
    if size > MAX_FILE_BYTES:
        return f"Файл слишком большой (макс. 15 МБ): {name}"
    return None


async def add_message(
    session,
    *,
    thread: WebSupportThread,
    author_user_id: int,
    author_role: str,
    author_login: str | None,
    body: str,
    source_path: str | None,
    files: list[tuple[str, bytes, str | None]],
) -> dict[str, Any]:
    text = (body or "").strip()[:MAX_BODY_LEN]
    if not text and not files:
        raise ValueError("Нужен текст или файл")
    if len(files) > MAX_FILES:
        raise ValueError(f"Можно прикрепить не больше {MAX_FILES} файлов")
    total = sum(len(data) for _name, data, _ctype in files)
    if total > MAX_TOTAL_BYTES:
        raise ValueError("Суммарный размер вложений больше 30 МБ")

    prepared: list[tuple[str, str, str, bytes]] = []
    for raw_name, data, ctype in files:
        filename = _safe_filename(raw_name)
        err = validate_upload(filename, len(data))
        if err:
            raise ValueError(err)
        ext = _ext(filename)
        stored = f"{uuid.uuid4().hex}{ext}"
        guessed = ctype or mimetypes.guess_type(filename)[0] or "application/octet-stream"
        prepared.append((filename, stored, guessed, data))

    created_at = _now()
    message = WebSupportMessage(
        thread_id=thread.id,
        author_role=author_role,
        author_user_id=int(author_user_id),
        body=text,
        source_path=source_path,
    )
    session.add(message)
    await session.flush()

    s3 = HintS3Storage.from_settings()
    attachments: list[WebSupportAttachment] = []
    for filename, stored, content_type, data in prepared:
        key = s3.support_attachment_key(thread.id, stored)
        try:
            await _upload_bytes(s3, key, data, content_type)
        except Exception:
            logger.exception("support attachment upload failed key={}", key)
            await session.rollback()
            raise ValueError("Не удалось сохранить файл") from None
        att = WebSupportAttachment(
            message_id=message.id,
            original_filename=filename,
            stored_name=stored,
            s3_key=key,
            content_type=content_type[:120],
            size_bytes=len(data),
        )
        session.add(att)
        attachments.append(att)

    thread.last_message_at = created_at
    thread.last_author_role = author_role
    thread.last_preview = _preview(text, [item[0] for item in prepared])
    if author_role == WebSupportAuthorRole.ADMIN.value:
        thread.admin_last_read_at = created_at
    else:
        thread.user_last_read_at = created_at
    await session.flush()
    payload = {
        "id": message.id,
        "role": author_role,
        "author_login": author_login or "",
        "body": text,
        "created_at": created_at.isoformat(),
        "attachments": [serialize_attachment(att) for att in attachments],
    }
    await session.commit()
    return payload


async def _upload_bytes(
    s3: HintS3Storage, key: str, data: bytes, content_type: str
) -> None:
    import asyncio

    await asyncio.to_thread(s3.upload_bytes, key, data, content_type)


async def get_attachment(session, attachment_id: int) -> WebSupportAttachment | None:
    result = await session.execute(
        select(WebSupportAttachment)
        .options(
            selectinload(WebSupportAttachment.message).selectinload(
                WebSupportMessage.thread
            )
        )
        .where(WebSupportAttachment.id == int(attachment_id))
    )
    return result.scalar_one_or_none()


async def user_unread(session, user_id: int) -> int:
    thread = await get_thread_by_user(session, user_id)
    if not thread:
        return 0
    return 1 if _is_unread_for_user(thread) else 0


async def admin_unread_count(session) -> int:
    result = await session.execute(
        select(func.count())
        .select_from(WebSupportThread)
        .where(
            WebSupportThread.last_author_role == WebSupportAuthorRole.USER.value,
            or_(
                WebSupportThread.admin_last_read_at.is_(None),
                WebSupportThread.last_message_at > WebSupportThread.admin_last_read_at,
            ),
        )
    )
    return int(result.scalar_one() or 0)


async def admin_unread_payload(session) -> dict[str, Any]:
    unread = await admin_unread_count(session)
    result = await session.execute(
        select(
            WebSupportMessage.id,
            WebSupportMessage.body,
            WebSupportThread.id,
            WebUser.login,
        )
        .join(WebSupportThread, WebSupportThread.id == WebSupportMessage.thread_id)
        .join(WebUser, WebUser.id == WebSupportThread.user_id)
        .where(WebSupportMessage.author_role == WebSupportAuthorRole.USER.value)
        .order_by(WebSupportMessage.id.desc())
        .limit(1)
    )
    row = result.first()
    preview = ""
    latest_id = 0
    thread_id = 0
    login = ""
    if row:
        latest_id = int(row[0] or 0)
        preview = " ".join((row[1] or "").split())[:120]
        thread_id = int(row[2] or 0)
        login = row[3] or ""
        if not preview:
            preview = "Новое сообщение"
    return {
        "unread": unread,
        "latest_message_id": latest_id,
        "latest_thread_id": thread_id,
        "latest_login": login,
        "latest_preview": preview,
    }


async def list_inbox(
    session,
    *,
    query: str = "",
    page: int = 1,
) -> tuple[list[dict[str, Any]], int]:
    page = max(1, int(page or 1))
    unread_expr = case(
        (
            and_(
                WebSupportThread.last_author_role == WebSupportAuthorRole.USER.value,
                or_(
                    WebSupportThread.admin_last_read_at.is_(None),
                    WebSupportThread.last_message_at > WebSupportThread.admin_last_read_at,
                ),
            ),
            1,
        ),
        else_=0,
    )
    stmt = (
        select(WebSupportThread, WebUser.login)
        .join(WebUser, WebUser.id == WebSupportThread.user_id)
        .where(WebSupportThread.last_message_at.is_not(None))
    )
    q = (query or "").strip()
    if q:
        stmt = stmt.where(WebUser.login.ilike(f"%{q}%"))
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = int((await session.execute(count_stmt)).scalar_one() or 0)
    result = await session.execute(
        stmt.order_by(unread_expr.desc(), WebSupportThread.last_message_at.desc())
        .offset((page - 1) * INBOX_PAGE_SIZE)
        .limit(INBOX_PAGE_SIZE)
    )
    items = []
    for thread, login in result.all():
        items.append(serialize_thread_meta(thread, login=login, is_admin=True))
    return items, total
