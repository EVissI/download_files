"""Сессии и история веб-версии hint viewer (аккаунты WebUser, без Telegram)."""

from __future__ import annotations

import json
import secrets
from typing import Any
from urllib.parse import quote

from loguru import logger

from bot.common.utils.password import passwords_match
from bot.db.redis import redis_client

COOKIE_NAME = "hint_web_session"
SESSION_TTL_SEC = 7 * 24 * 3600
JOBS_TTL_SEC = 7 * 24 * 3600
SESSION_KEY = "hint_web:session:{token}"
JOBS_KEY = "hint_web:jobs:{token}"


def web_hint_open_links(
    game_id: str | None,
    red_player: str | None = None,
    black_player: str | None = None,
) -> list[dict[str, str]]:
    """Те же режимы просмотра, что кнопки WebApp в Telegram: error=0..3."""
    if not game_id:
        return []
    gid = quote(str(game_id), safe="")
    red = (red_player or "").strip() or "Red"
    black = (black_player or "").strip() or "Black"
    base = f"/web/hints/view?game_id={gid}"
    return [
        {"label": "Все ходы", "url": f"{base}&error=0"},
        {"label": "Ошибки обоих", "url": f"{base}&error=1"},
        {"label": f"Ошибки {red}", "url": f"{base}&error=2"},
        {"label": f"Ошибки {black}", "url": f"{base}&error=3"},
    ]


async def authenticate_web_user(login: str, password: str):
    from types import SimpleNamespace

    from bot.db.database import async_session_maker
    from bot.db.dao import WebUserDAO

    normalized = (login or "").strip()
    raw = (password or "").strip()
    if not normalized or not raw:
        return None, "invalid"
    async with async_session_maker() as session:
        user = await WebUserDAO(session).get_by_login(normalized)
        if not user:
            logger.info("Web login failed: unknown login")
            return None, "invalid"
        if not passwords_match(user.password_hash, user.password_encrypted, raw):
            logger.info("Web login failed: bad password for login={}", user.login)
            return None, "invalid"
        if user.is_expired():
            logger.info("Web login failed: expired login={}", user.login)
            return None, "expired"
        return SimpleNamespace(
            id=int(user.id),
            login=user.login,
            is_admin=bool(user.is_admin),
        ), None


async def create_session(user) -> dict[str, Any]:
    token = secrets.token_urlsafe(32)
    payload = {
        "ok": True,
        "user_id": int(user.id),
        "web_uid": -int(user.id),
        "is_admin": bool(getattr(user, "is_admin", False)),
    }
    await redis_client.set(
        SESSION_KEY.format(token=token), json.dumps(payload), expire=SESSION_TTL_SEC
    )
    return {"token": token, **payload}


async def get_session(token: str | None) -> dict[str, Any] | None:
    if not token:
        return None
    raw = await redis_client.get(SESSION_KEY.format(token=token))
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not data.get("ok") or not data.get("user_id"):
        return None
    if not await web_user_account_active(data.get("user_id")):
        await destroy_session(token)
        return None
    return data


async def web_user_account_active(user_id: int | None) -> bool:
    if not user_id:
        return False
    from sqlalchemy import select

    from bot.db.database import async_session_maker
    from bot.db.models import WebUser, web_user_expires_at_passed

    async with async_session_maker() as session:
        result = await session.execute(
            select(WebUser.id, WebUser.expires_at).where(WebUser.id == int(user_id))
        )
        row = result.one_or_none()
        if row is None:
            return False
        return not web_user_expires_at_passed(row.expires_at)


async def web_user_is_admin(user_id: int | None) -> bool:
    if not user_id:
        return False
    from sqlalchemy import select

    from bot.db.database import async_session_maker
    from bot.db.models import WebUser

    async with async_session_maker() as session:
        result = await session.execute(
            select(WebUser.is_admin).where(WebUser.id == int(user_id))
        )
        return bool(result.scalar_one_or_none())


async def destroy_session(token: str | None) -> None:
    if not token:
        return
    await redis_client.delete(SESSION_KEY.format(token=token))
    await redis_client.delete(JOBS_KEY.format(token=token))


async def append_session_job(token: str, job: dict[str, Any]) -> None:
    key = JOBS_KEY.format(token=token)
    raw = await redis_client.get(key)
    items: list[dict[str, Any]] = []
    if raw:
        try:
            items = json.loads(raw)
        except json.JSONDecodeError:
            items = []
    items.insert(0, job)
    items = items[:80]
    await redis_client.set(key, json.dumps(items, ensure_ascii=False), expire=JOBS_TTL_SEC)


async def list_session_jobs(token: str) -> list[dict[str, Any]]:
    raw = await redis_client.get(JOBS_KEY.format(token=token))
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


async def replace_session_jobs(token: str, jobs: list[dict[str, Any]]) -> None:
    key = JOBS_KEY.format(token=token)
    await redis_client.set(
        key, json.dumps(jobs, ensure_ascii=False), expire=JOBS_TTL_SEC
    )


async def record_history(**kwargs: Any) -> None:
    try:
        from bot.db.database import async_session_maker
        from bot.db.dao import HintViewerWebUploadDAO

        async with async_session_maker() as session:
            dao = HintViewerWebUploadDAO(session)
            await dao.create_upload(**kwargs)
            await session.commit()
    except Exception as e:
        logger.exception("hint viewer web history write failed: {}", e)


HISTORY_PAGE_SIZE = 10


def _history_item(row) -> dict[str, Any]:
    game_id = row.game_id
    links = (
        web_hint_open_links(game_id, row.red_player, row.black_player)
        if row.status == "done" and game_id
        else []
    )
    return {
        "id": row.id,
        "original_filename": row.original_filename,
        "red_player": row.red_player,
        "black_player": row.black_player,
        "status": row.status,
        "error_message": row.error_message,
        "game_id": game_id,
        "view_url": links[0]["url"] if links else None,
        "open_links": links,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "finished_at": row.finished_at.isoformat() if row.finished_at else None,
    }


async def list_history_for_user(
    user_id: int, page: int = 1, page_size: int = HISTORY_PAGE_SIZE
) -> dict[str, Any]:
    empty = {
        "items": [],
        "page": 1,
        "pages": 1,
        "page_size": page_size,
        "total": 0,
    }
    if not user_id:
        return empty
    from bot.db.database import async_session_maker
    from bot.db.dao import HintViewerWebUploadDAO

    size = max(1, min(int(page_size or HISTORY_PAGE_SIZE), 50))
    async with async_session_maker() as session:
        dao = HintViewerWebUploadDAO(session)
        total = await dao.count_for_user(user_id)
        pages = max(1, (total + size - 1) // size) if total else 1
        current = max(1, int(page or 1))
        if current > pages:
            current = pages
        offset = (current - 1) * size
        rows = await dao.list_for_user(user_id, limit=size, offset=offset)
        return {
            "items": [_history_item(row) for row in rows],
            "page": current,
            "pages": pages,
            "page_size": size,
            "total": total,
        }


async def sync_history_from_job(job: dict[str, Any]) -> None:
    job_id = job.get("job_id")
    if not job_id:
        return
    status = job.get("status")
    if status not in {"done", "error", "processing"}:
        return
    try:
        from bot.db.database import async_session_maker
        from bot.db.dao import HintViewerWebUploadDAO

        finished = status in {"done", "error"}
        async with async_session_maker() as session:
            dao = HintViewerWebUploadDAO(session)
            if job.get("kind") == "batch":
                for entry in job.get("files") or []:
                    file_status = entry.get("status") or status
                    file_finished = file_status in {"done", "error"}
                    await dao.update_status_for_job(
                        job_id,
                        file_status if file_status in {"done", "error", "processing", "queued"} else status,
                        original_filename=entry.get("filename"),
                        game_id=entry.get("game_id"),
                        error_message=entry.get("error"),
                        finished=file_finished,
                    )
            else:
                await dao.update_status_for_job(
                    job_id,
                    status,
                    original_filename=job.get("filename"),
                    game_id=job.get("game_id"),
                    error_message=job.get("error"),
                    finished=finished,
                )
            await session.commit()
    except Exception as e:
        logger.exception("hint viewer web history sync failed: {}", e)
