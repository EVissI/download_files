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
ACCT_CACHE_KEY = "hint_web:acct:{user_id}"
ACCT_CACHE_TTL_SEC = 60
WEB_SERVICE_HINTS = "hints"
WEB_SERVICE_BOARD = "board"
WEB_ALLOWED_NEXT = (
    "/web/hints",
    "/web/board",
    "/web/pokaz",
    "/web/cards",
    "/web/pip-count",
    "/web/match-analysis",
)


def safe_web_next(value: str | None) -> str:
    if value in WEB_ALLOWED_NEXT:
        return value
    return "/web/hints"


def _jobs_key(token: str, service: str = WEB_SERVICE_HINTS) -> str:
    if service == WEB_SERVICE_HINTS:
        return JOBS_KEY.format(token=token)
    return f"hint_web:jobs:{service}:{token}"


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


def web_board_open_links(game_id: str | None) -> list[dict[str, str]]:
    if not game_id:
        return []
    gid = quote(str(game_id), safe="")
    return [{"label": "Открыть игру", "url": f"/web/board/view?game_id={gid}"}]


def web_open_links_for_service(
    service: str | None,
    game_id: str | None,
    red_player: str | None = None,
    black_player: str | None = None,
) -> list[dict[str, str]]:
    if service == WEB_SERVICE_BOARD:
        return web_board_open_links(game_id)
    return web_hint_open_links(game_id, red_player, black_player)


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
    try:
        from bot.common.service.web_grant_user import ensure_web_grant_user_async

        await ensure_web_grant_user_async(
            int(user.id), login=getattr(user, "login", None)
        )
        if bool(getattr(user, "is_admin", False)):
            from bot.common.service.cabinet_admin import grant_all_cabinet_content_async
            from bot.common.service.web_grant_user import web_grant_user_id

            await grant_all_cabinet_content_async(web_grant_user_id(int(user.id)))
    except Exception:
        logger.exception("web grant user ensure failed for web_user_id={}", user.id)
    return {"token": token, **payload}


def web_cabinet_page_vars(service: str) -> dict[str, Any]:
    if service == WEB_SERVICE_BOARD:
        return {
            "web_service": WEB_SERVICE_BOARD,
            "api_base": "/web/board",
            "page_title": "Плеер",
            "intro_text": (
                "Загрузите один .mat — сразу откроется просмотр партии."
            ),
            "upload_ok_message": "Открываем плеер…",
            "login_url": "/web/hints/login?next=/web/board",
            "card_title": "Новый матч",
            "upload_btn_label": "Открыть",
            "show_current_jobs": False,
            "allow_multiple": False,
            "open_on_upload": True,
            "dropzone_hint": ".mat",
            "accept": ".mat",
            "dropzone_title": "Нажмите или перетащите файл сюда",
        }
    return {
        "web_service": WEB_SERVICE_HINTS,
        "api_base": "/web/hints",
        "page_title": "Ошибки",
        "intro_text": (
            "Можно загрузить один или несколько .mat, либо zip с матчами. "
            "Когда анализ будет готов, появится уведомление."
        ),
        "upload_ok_message": "Файл(ы) приняты, анализ в очереди.",
        "login_url": "/web/hints/login",
        "card_title": "Новый анализ",
        "upload_btn_label": "Отправить на анализ",
        "show_current_jobs": True,
        "allow_multiple": True,
        "open_on_upload": False,
        "dropzone_hint": ".mat или .zip",
        "accept": ".mat,.zip,application/zip",
        "dropzone_title": "Нажмите или перетащите файлы сюда",
    }


async def resolve_web_session(request) -> dict[str, Any] | None:
    """Сессия из middleware (request.state), иначе чтение cookie."""
    state = getattr(request, "state", None)
    if state is not None and hasattr(state, "web_session"):
        return state.web_session
    return await get_session(request.cookies.get(COOKIE_NAME))


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
    snapshot = await web_account_snapshot(data.get("user_id"))
    if not snapshot or not snapshot.get("active"):
        await destroy_session(token)
        return None
    data["is_admin"] = bool(snapshot.get("is_admin"))
    if "web_uid" not in data:
        data["web_uid"] = -int(data["user_id"])
    return data


async def web_account_snapshot(user_id: int | None) -> dict[str, Any] | None:
    """active + is_admin; кэш в Redis, чтобы не ходить в БД на каждый запрос."""
    if not user_id:
        return None
    uid = int(user_id)
    cache_key = ACCT_CACHE_KEY.format(user_id=uid)
    cached = await redis_client.get(cache_key)
    if cached:
        try:
            data = json.loads(cached)
            if isinstance(data, dict) and "active" in data:
                return data
        except json.JSONDecodeError:
            pass

    from sqlalchemy import select

    from bot.db.database import async_session_maker
    from bot.db.models import WebUser, web_user_expires_at_passed

    async with async_session_maker() as session:
        result = await session.execute(
            select(WebUser.id, WebUser.is_admin, WebUser.expires_at).where(
                WebUser.id == uid
            )
        )
        row = result.one_or_none()
    if row is None:
        payload = {"active": False, "is_admin": False}
    else:
        payload = {
            "active": not web_user_expires_at_passed(row.expires_at),
            "is_admin": bool(row.is_admin),
        }
    await redis_client.set(
        cache_key, json.dumps(payload), expire=ACCT_CACHE_TTL_SEC
    )
    return payload


async def invalidate_web_account_cache(user_id: int | None) -> None:
    if not user_id:
        return
    await redis_client.delete(ACCT_CACHE_KEY.format(user_id=int(user_id)))


def invalidate_web_account_cache_sync(user_id: int | None) -> None:
    if not user_id:
        return
    from bot.db.redis import sync_redis_client

    sync_redis_client.delete(ACCT_CACHE_KEY.format(user_id=int(user_id)))


async def web_user_account_active(user_id: int | None) -> bool:
    snapshot = await web_account_snapshot(user_id)
    return bool(snapshot and snapshot.get("active"))


async def web_user_is_admin(user_id: int | None) -> bool:
    snapshot = await web_account_snapshot(user_id)
    return bool(snapshot and snapshot.get("active") and snapshot.get("is_admin"))


async def destroy_session(token: str | None) -> None:
    if not token:
        return
    await redis_client.delete(SESSION_KEY.format(token=token))
    await redis_client.delete(_jobs_key(token, WEB_SERVICE_HINTS))
    await redis_client.delete(_jobs_key(token, WEB_SERVICE_BOARD))


async def append_session_job(
    token: str, job: dict[str, Any], service: str = WEB_SERVICE_HINTS
) -> None:
    key = _jobs_key(token, service)
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


async def list_session_jobs(
    token: str, service: str = WEB_SERVICE_HINTS
) -> list[dict[str, Any]]:
    raw = await redis_client.get(_jobs_key(token, service))
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


async def replace_session_jobs(
    token: str, jobs: list[dict[str, Any]], service: str = WEB_SERVICE_HINTS
) -> None:
    key = _jobs_key(token, service)
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
    service = getattr(row, "service", None) or WEB_SERVICE_HINTS
    links = (
        web_open_links_for_service(service, game_id, row.red_player, row.black_player)
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
    user_id: int,
    page: int = 1,
    page_size: int = HISTORY_PAGE_SIZE,
    service: str = WEB_SERVICE_HINTS,
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
        total = await dao.count_for_user(user_id, service=service)
        pages = max(1, (total + size - 1) // size) if total else 1
        current = max(1, int(page or 1))
        if current > pages:
            current = pages
        offset = (current - 1) * size
        rows = await dao.list_for_user(
            user_id, limit=size, offset=offset, service=service
        )
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
