"""Сессии и история веб-версии hint viewer (аккаунты WebUser, без Telegram)."""

from __future__ import annotations

import asyncio
import json
import re
import secrets
import time
from contextlib import asynccontextmanager
from typing import Any, Callable
from urllib.parse import quote

from loguru import logger
from sqlalchemy.orm import Session, sessionmaker

from bot.common.utils.password import passwords_match
from bot.db.models import WebUser
from bot.db.redis import redis_client

COOKIE_NAME = "hint_web_session"
DEVICE_COOKIE_NAME = "hint_web_device"
SESSION_TTL_SEC = 7 * 24 * 3600
DEVICE_COOKIE_TTL_SEC = 400 * 24 * 3600
JOBS_TTL_SEC = 7 * 24 * 3600
SESSION_KEY = "hint_web:session:{token}"
USER_SESSIONS_KEY = "hint_web:sessions:{user_id}"
DEVICE_TOKEN_KEY = "hint_web:user_device:{user_id}:{device_id}"
JOBS_KEY = "hint_web:jobs:{token}"
JOBS_LOCK_KEY = "hint_web:jobs_lock:{service}:{token}"
ACCT_CACHE_KEY = "hint_web:acct:{user_id}"
ACCT_CACHE_TTL_SEC = 60
_DEVICE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
WEB_SERVICE_HINTS = "hints"
WEB_SERVICE_BOARD = "board"
WEB_SERVICE_ANALYZE = "analyze"
WEB_ALLOWED_NEXT = (
    "/web/hints",
    "/web/board",
    "/web/pokaz",
    "/web/cards",
    "/web/pip-count",
    "/web/match-analysis",
    "/web/analyze",
)


def safe_web_next(value: str | None) -> str:
    if value in WEB_ALLOWED_NEXT:
        return value
    return "/web/hints"


def _jobs_key(token: str, service: str = WEB_SERVICE_HINTS) -> str:
    if service == WEB_SERVICE_HINTS:
        return JOBS_KEY.format(token=token)
    return f"hint_web:jobs:{service}:{token}"


def normalize_device_id(raw: str | None) -> str | None:
    value = (raw or "").strip()
    if _DEVICE_ID_RE.fullmatch(value):
        return value
    return None


def new_device_id() -> str:
    return secrets.token_urlsafe(24)


def device_id_from_request(request) -> str:
    return normalize_device_id(request.cookies.get(DEVICE_COOKIE_NAME)) or new_device_id()


def attach_device_cookie(response, device_id: str) -> None:
    response.set_cookie(
        key=DEVICE_COOKIE_NAME,
        value=device_id,
        max_age=DEVICE_COOKIE_TTL_SEC,
        httponly=True,
        samesite="lax",
        path="/",
    )


def _sessions_key(user_id: int) -> str:
    return USER_SESSIONS_KEY.format(user_id=int(user_id))


def _device_key(user_id: int, device_id: str) -> str:
    return DEVICE_TOKEN_KEY.format(user_id=int(user_id), device_id=device_id)


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
    if service == WEB_SERVICE_ANALYZE:
        return []
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
            max_sessions=WebUser.clamp_max_sessions(getattr(user, "max_sessions", 1)),
        ), None


async def _user_session_tokens(user_id: int) -> list[str]:
    tokens = await redis_client.zrange(_sessions_key(user_id), 0, -1)
    return [str(t) for t in tokens if t]


async def _register_session_index(
    user_id: int, token: str, created_at: float, device_id: str | None
) -> None:
    await redis_client.zadd(_sessions_key(user_id), {token: created_at})
    await redis_client.expire(_sessions_key(user_id), SESSION_TTL_SEC)
    if device_id:
        await redis_client.set(
            _device_key(user_id, device_id), token, expire=SESSION_TTL_SEC
        )


async def _unregister_session_index(
    user_id: int, token: str, device_id: str | None
) -> None:
    await redis_client.zrem(_sessions_key(user_id), token)
    if not device_id:
        return
    dkey = _device_key(user_id, device_id)
    current = await redis_client.get(dkey)
    if current == token:
        await redis_client.delete(dkey)


async def _ensure_session_indexed(token: str, data: dict[str, Any]) -> None:
    uid = int(data["user_id"])
    tokens = await _user_session_tokens(uid)
    if token in tokens:
        return
    created_at = float(data.get("created_at") or time.time())
    await _register_session_index(uid, token, created_at, data.get("device_id"))


async def create_session(user, device_id: str | None = None) -> dict[str, Any]:
    uid = int(user.id)
    max_sessions = WebUser.clamp_max_sessions(getattr(user, "max_sessions", 1))
    device_id = normalize_device_id(device_id) or new_device_id()

    old_token = await redis_client.get(_device_key(uid, device_id))
    if old_token:
        await destroy_session(old_token, user_id=uid)

    active = await _user_session_tokens(uid)
    if len(active) >= max_sessions:
        return {
            "ok": False,
            "error": "session_limit",
            "max_sessions": max_sessions,
            "device_id": device_id,
        }

    token = secrets.token_urlsafe(32)
    created_at = time.time()
    payload = {
        "ok": True,
        "user_id": uid,
        "web_uid": -uid,
        "is_admin": bool(getattr(user, "is_admin", False)),
        "device_id": device_id,
        "created_at": created_at,
    }
    await redis_client.set(
        SESSION_KEY.format(token=token), json.dumps(payload), expire=SESSION_TTL_SEC
    )
    await _register_session_index(uid, token, created_at, device_id)
    try:
        from bot.common.service.web_grant_user import ensure_web_grant_user_async

        await ensure_web_grant_user_async(
            uid, login=getattr(user, "login", None)
        )
        if bool(getattr(user, "is_admin", False)):
            from bot.common.service.cabinet_admin import grant_all_cabinet_content_async
            from bot.common.service.web_grant_user import web_grant_user_id

            await grant_all_cabinet_content_async(web_grant_user_id(uid))
    except Exception:
        logger.exception("web grant user ensure failed for web_user_id={}", uid)
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
    if service == WEB_SERVICE_ANALYZE:
        return {
            "web_service": WEB_SERVICE_ANALYZE,
            "api_base": "/web/analyze",
            "page_title": "Анализ",
            "intro_text": (
                "Загрузите один или несколько файлов партий либо zip. "
                "Когда GNU Backgammon посчитает статистику, в истории "
                "можно раскрыть таблицу анализа."
            ),
            "upload_ok_message": "Файл(ы) приняты, анализ запущен.",
            "login_url": "/web/hints/login?next=/web/analyze",
            "card_title": "Новый анализ",
            "upload_btn_label": "Отправить на анализ",
            "show_current_jobs": True,
            "allow_multiple": True,
            "open_on_upload": False,
            "history_expandable": True,
            "pdf_download": True,
            "send_to_hints": True,
            "dropzone_hint": ".mat, .zip, .sgf, .gam и др.",
            "accept": ".mat,.zip,.txt,.sgf,.sgg,.bkg,.gam,.pos,.fibs,.tmg,application/zip",
            "dropzone_title": "Нажмите или перетащите файлы сюда",
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
        "send_to_analyze": True,
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
    await _ensure_session_indexed(token, data)
    data["is_admin"] = bool(snapshot.get("is_admin"))
    if "web_uid" not in data:
        data["web_uid"] = -int(data["user_id"])
    return data


async def web_account_snapshot(user_id: int | None) -> dict[str, Any] | None:
    """active + is_admin + max_sessions; кэш в Redis, чтобы не ходить в БД на каждый запрос."""
    if not user_id:
        return None
    uid = int(user_id)
    cache_key = ACCT_CACHE_KEY.format(user_id=uid)
    cached = await redis_client.get(cache_key)
    if cached:
        try:
            data = json.loads(cached)
            if isinstance(data, dict) and "active" in data and "max_sessions" in data:
                return data
        except json.JSONDecodeError:
            pass

    from sqlalchemy import select

    from bot.db.database import async_session_maker
    from bot.db.models import WebUser, web_user_expires_at_passed

    async with async_session_maker() as session:
        result = await session.execute(
            select(
                WebUser.id,
                WebUser.is_admin,
                WebUser.expires_at,
                WebUser.max_sessions,
            ).where(WebUser.id == uid)
        )
        row = result.one_or_none()
    if row is None:
        payload = {"active": False, "is_admin": False, "max_sessions": 1}
    else:
        payload = {
            "active": not web_user_expires_at_passed(row.expires_at),
            "is_admin": bool(row.is_admin),
            "max_sessions": WebUser.clamp_max_sessions(row.max_sessions),
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


async def destroy_session(token: str | None, *, user_id: int | None = None) -> None:
    if not token:
        return
    payload_user_id = None
    device_id = None
    raw = await redis_client.get(SESSION_KEY.format(token=token))
    if raw:
        try:
            data = json.loads(raw)
            payload_user_id = int(data.get("user_id") or 0) or None
            device_id = data.get("device_id")
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    uid = payload_user_id or user_id
    await redis_client.delete(SESSION_KEY.format(token=token))
    await redis_client.delete(_jobs_key(token, WEB_SERVICE_HINTS))
    await redis_client.delete(_jobs_key(token, WEB_SERVICE_BOARD))
    await redis_client.delete(_jobs_key(token, WEB_SERVICE_ANALYZE))
    if uid:
        await _unregister_session_index(int(uid), token, device_id)


def _parse_jobs_payload(raw: Any) -> list[dict[str, Any]]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


async def _read_session_jobs(token: str, service: str) -> list[dict[str, Any]]:
    return _parse_jobs_payload(await redis_client.get(_jobs_key(token, service)))


async def _write_session_jobs(
    token: str, jobs: list[dict[str, Any]], service: str
) -> None:
    await redis_client.set(
        _jobs_key(token, service),
        json.dumps(jobs, ensure_ascii=False),
        expire=JOBS_TTL_SEC,
    )


@asynccontextmanager
async def _session_jobs_lock(token: str, service: str):
    lock_key = JOBS_LOCK_KEY.format(service=service, token=token)
    lock_val = secrets.token_hex(8)
    acquired = False
    for _ in range(80):
        acquired = await redis_client.set_nx(lock_key, lock_val, expire=8)
        if acquired:
            break
        await asyncio.sleep(0.05)
    if not acquired:
        logger.warning("web session jobs lock timeout service={} token={}", service, token[:8])
    try:
        yield
    finally:
        if acquired:
            current = await redis_client.get(lock_key)
            if current == lock_val:
                await redis_client.delete(lock_key)


async def append_session_job(
    token: str, job: dict[str, Any], service: str = WEB_SERVICE_HINTS
) -> None:
    async with _session_jobs_lock(token, service):
        items = await _read_session_jobs(token, service)
        items.insert(0, job)
        await _write_session_jobs(token, items[:80], service)


async def list_session_jobs(
    token: str, service: str = WEB_SERVICE_HINTS
) -> list[dict[str, Any]]:
    return await _read_session_jobs(token, service)


async def replace_session_jobs(
    token: str, jobs: list[dict[str, Any]], service: str = WEB_SERVICE_HINTS
) -> None:
    async with _session_jobs_lock(token, service):
        await _write_session_jobs(token, jobs, service)


async def patch_session_job(
    token: str,
    job_id: str,
    mutator: Callable[[dict[str, Any]], None],
    service: str = WEB_SERVICE_HINTS,
) -> dict[str, Any] | None:
    if not token or not job_id:
        return None
    async with _session_jobs_lock(token, service):
        jobs = await _read_session_jobs(token, service)
        updated = None
        for job in jobs:
            if job.get("job_id") == job_id:
                mutator(job)
                updated = job
                break
        if updated is None:
            return None
        await _write_session_jobs(token, jobs, service)
        return updated


async def prune_session_jobs(
    token: str,
    *,
    drop_job_ids: set[str] | None = None,
    finished_at_by_id: dict[str, str] | None = None,
    service: str = WEB_SERVICE_HINTS,
) -> None:
    drop_job_ids = {jid for jid in (drop_job_ids or set()) if jid}
    finished_at_by_id = finished_at_by_id or {}
    if not drop_job_ids and not finished_at_by_id:
        return
    async with _session_jobs_lock(token, service):
        jobs = await _read_session_jobs(token, service)
        kept: list[dict[str, Any]] = []
        for job in jobs:
            jid = job.get("job_id")
            if jid in drop_job_ids:
                continue
            stamp = finished_at_by_id.get(jid)
            if stamp and not job.get("finished_at"):
                job["finished_at"] = stamp
            kept.append(job)
        await _write_session_jobs(token, kept, service)


_ACTIVE_JOB_STATUSES = {"queued", "processing"}


def _session_job_is_active(job: dict[str, Any]) -> bool:
    status = job.get("status")
    if status in _ACTIVE_JOB_STATUSES:
        return True
    if job.get("kind") == "batch":
        return any(
            (item.get("status") in _ACTIVE_JOB_STATUSES)
            for item in (job.get("files") or [])
        )
    return False


async def clear_finished_session_jobs(
    token: str, service: str = WEB_SERVICE_HINTS
) -> int:
    """Убирает из текущих задач готовые и ошибочные. История не меняется."""
    if not token:
        return 0
    async with _session_jobs_lock(token, service):
        jobs = await _read_session_jobs(token, service)
        kept = [job for job in jobs if _session_job_is_active(job)]
        removed = len(jobs) - len(kept)
        if removed:
            await _write_session_jobs(token, kept, service)
        return removed


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


async def update_history_status(
    job_id: str | None,
    status: str,
    *,
    original_filename: str | None = None,
    game_id: str | None = None,
    error_message: str | None = None,
    finished: bool | None = None,
    red_player: str | None = None,
    black_player: str | None = None,
) -> None:
    if not job_id or status not in {"queued", "processing", "done", "error"}:
        return
    if finished is None:
        finished = status in {"done", "error"}
    try:
        from bot.db.database import async_session_maker
        from bot.db.dao import HintViewerWebUploadDAO

        async with async_session_maker() as session:
            dao = HintViewerWebUploadDAO(session)
            await dao.update_status_for_job(
                job_id,
                status,
                original_filename=original_filename,
                game_id=game_id,
                error_message=error_message,
                finished=finished,
                red_player=red_player,
                black_player=black_player,
            )
            await session.commit()
    except Exception as e:
        logger.exception("hint viewer web history status update failed: {}", e)


_sync_web_upload_engine = None
_sync_web_upload_session: sessionmaker[Session] | None = None


def _web_upload_sync_session() -> Session:
    global _sync_web_upload_engine, _sync_web_upload_session
    if _sync_web_upload_session is None:
        from sqlalchemy import create_engine

        from bot.config import settings

        _sync_web_upload_engine = create_engine(settings.DB_URL_SYNC, pool_pre_ping=True)
        _sync_web_upload_session = sessionmaker(bind=_sync_web_upload_engine)
    return _sync_web_upload_session()


def sync_web_history_status(
    job_id: str | None,
    status: str,
    *,
    original_filename: str | None = None,
    game_id: str | None = None,
    error_message: str | None = None,
    finished: bool | None = None,
    red_player: str | None = None,
    black_player: str | None = None,
) -> None:
    """Синхронная запись статуса истории — для RQ-воркера."""
    if not job_id or status not in {"queued", "processing", "done", "error"}:
        return
    if finished is None:
        finished = status in {"done", "error"}
    try:
        from sqlalchemy import select

        from bot.db.dao import apply_web_upload_status, web_upload_job_filter
        from bot.db.models import HintViewerWebUpload

        with _web_upload_sync_session() as session:
            rows = session.execute(
                select(HintViewerWebUpload).where(
                    *web_upload_job_filter(
                        job_id,
                        game_id=game_id,
                        original_filename=original_filename,
                    )
                )
            ).scalars().all()
            changed = False
            for row in rows:
                if apply_web_upload_status(
                    row,
                    status,
                    game_id=game_id,
                    error_message=error_message,
                    finished=finished,
                    red_player=red_player,
                    black_player=black_player,
                ):
                    changed = True
            if changed:
                session.commit()
    except Exception:
        logger.exception("sync web history status failed job_id={}", job_id)


HISTORY_PAGE_SIZE = 10


def _history_item(row) -> dict[str, Any]:
    game_id = row.game_id
    service = getattr(row, "service", None) or WEB_SERVICE_HINTS
    is_analyze = service == WEB_SERVICE_ANALYZE
    links = (
        []
        if is_analyze
        else (
            web_open_links_for_service(service, game_id, row.red_player, row.black_player)
            if row.status == "done" and game_id
            else []
        )
    )
    return {
        "id": row.id,
        "kind": "single",
        "batch_id": row.batch_id,
        "original_filename": row.original_filename,
        "red_player": row.red_player,
        "black_player": row.black_player,
        "status": row.status,
        "error_message": row.error_message,
        "game_id": game_id,
        "view_url": links[0]["url"] if links else None,
        "open_links": links,
        "expandable": bool(is_analyze and row.status == "done" and game_id),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "finished_at": row.finished_at.isoformat() if row.finished_at else None,
    }


def _batch_group_status(rows: list[Any]) -> str:
    statuses = {row.status for row in rows}
    if statuses & {"queued", "processing"}:
        return "processing" if statuses & {"processing", "done"} else "queued"
    if statuses and statuses <= {"error"}:
        return "error"
    if any(row.status == "done" for row in rows):
        return "done"
    return "queued"


def _history_batch_item(rows: list[Any]) -> dict[str, Any]:
    children = sorted(rows, key=lambda row: row.id or 0)
    first = children[0]
    n = len(children)
    done_n = sum(1 for row in children if row.status == "done")
    status = _batch_group_status(children)
    created = max((row.created_at for row in children if row.created_at), default=None)
    finished = None
    if status in {"done", "error"}:
        finished = max(
            (row.finished_at for row in children if row.finished_at), default=None
        )
    return {
        "id": first.id,
        "kind": "batch",
        "batch_id": first.batch_id,
        "original_filename": f"Пакет: {n} файл(ов)",
        "red_player": None,
        "black_player": None,
        "status": status,
        "error_message": None,
        "game_id": None,
        "view_url": None,
        "open_links": [],
        "expandable": n > 0,
        "files": [_history_item(row) for row in children],
        "total_files": n,
        "ready_count": done_n,
        "created_at": created.isoformat() if created else None,
        "finished_at": finished.isoformat() if finished else None,
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
        group_batches = service == WEB_SERVICE_ANALYZE
        if group_batches:
            total = await dao.count_groups_for_user(user_id, service=service)
        else:
            total = await dao.count_for_user(user_id, service=service)
        pages = max(1, (total + size - 1) // size) if total else 1
        current = max(1, int(page or 1))
        if current > pages:
            current = pages
        offset = (current - 1) * size
        if group_batches:
            groups = await dao.list_grouped_for_user(
                user_id, limit=size, offset=offset, service=service
            )
            items = []
            for rows in groups:
                if len(rows) > 1 or (rows and rows[0].batch_id):
                    items.append(_history_batch_item(rows))
                elif rows:
                    items.append(_history_item(rows[0]))
        else:
            rows = await dao.list_for_user(
                user_id, limit=size, offset=offset, service=service
            )
            items = [_history_item(row) for row in rows]
        return {
            "items": items,
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
                    if file_status not in {"done", "error", "processing"}:
                        if status in {"done", "error"}:
                            file_status = "error"
                        else:
                            continue
                    await dao.update_status_for_job(
                        job_id,
                        file_status,
                        original_filename=entry.get("filename"),
                        game_id=entry.get("game_id"),
                        error_message=entry.get("error")
                        or (
                            "Файл не был обработан"
                            if file_status == "error" and status in {"done", "error"}
                            else None
                        ),
                        finished=file_status in {"done", "error"},
                        red_player=entry.get("red_player"),
                        black_player=entry.get("black_player"),
                    )
            else:
                await dao.update_status_for_job(
                    job_id,
                    status,
                    original_filename=job.get("filename"),
                    game_id=job.get("game_id"),
                    error_message=job.get("error"),
                    finished=finished,
                    red_player=job.get("red_player"),
                    black_player=job.get("black_player"),
                )
            await session.commit()
    except Exception as e:
        logger.exception("hint viewer web history sync failed: {}", e)
