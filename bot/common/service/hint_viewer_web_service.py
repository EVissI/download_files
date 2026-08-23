"""Сессии и заготовка истории для веб-версии hint viewer (без Telegram)."""

from __future__ import annotations

import json
import secrets
from typing import Any

from loguru import logger

from bot.config import settings
from bot.db.redis import redis_client

COOKIE_NAME = "hint_web_session"
SESSION_TTL_SEC = 7 * 24 * 3600
JOBS_TTL_SEC = 7 * 24 * 3600
SESSION_KEY = "hint_web:session:{token}"
JOBS_KEY = "hint_web:jobs:{token}"


def is_web_password_configured() -> bool:
    return bool((settings.HINT_VIEWER_WEB_PASSWORD or "").strip())


def is_history_enabled() -> bool:
    """История загрузок заведена, но без аккаунтов не включается."""
    return bool(settings.HINT_VIEWER_WEB_HISTORY_ENABLED)


def password_matches(candidate: str) -> bool:
    expected = (settings.HINT_VIEWER_WEB_PASSWORD or "").strip()
    if not expected:
        return False
    return secrets.compare_digest(candidate or "", expected)


async def create_session() -> dict[str, Any]:
    token = secrets.token_urlsafe(32)
    web_uid = -secrets.randbelow(1_000_000_000) - 1
    payload = {"ok": True, "web_uid": web_uid}
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
    if not data.get("ok"):
        return None
    return data


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


async def record_history_if_enabled(**kwargs: Any) -> None:
    """
    Запись истории в БД.

    Сейчас no-op: аккаунтов нет, HINT_VIEWER_WEB_HISTORY_ENABLED=false.
    Когда появятся пользователи — включить флаг и передавать user_id.
    """
    if not is_history_enabled():
        return
    try:
        from bot.db.database import async_session_maker
        from bot.db.dao import HintViewerWebUploadDAO

        async with async_session_maker() as session:
            dao = HintViewerWebUploadDAO(session)
            await dao.create_upload(**kwargs)
            await session.commit()
    except Exception as e:
        logger.exception("hint viewer web history write failed: {}", e)
