"""Отдельная веб-версия hint viewer: пароль, загрузка .mat, уведомление о готовности."""

from __future__ import annotations

import asyncio
import io
import json
import os
import shutil
import tempfile
import uuid
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from loguru import logger
from redis import Redis
from rq import Queue
from rq.exceptions import NoSuchJobError
from rq.job import Job

from bot.common.func.hint_viewer import (
    extract_player_names,
    estimate_processing_time,
    random_filename,
)
from bot.common.hint_job_state import (
    BATCH_TIMEOUT_MAX_SEC,
    add_active_job,
    calc_batch_job_timeout,
    get_batch_file_statuses,
    is_batch_effectively_done,
)
from bot.common.service.hint_s3_service import HintS3Storage
from bot.common.service.hint_viewer_web_service import (
    COOKIE_NAME,
    HISTORY_PAGE_SIZE,
    SESSION_TTL_SEC,
    append_session_job,
    authenticate_web_user,
    create_session,
    destroy_session,
    list_history_for_user,
    list_session_jobs,
    record_history,
    replace_session_jobs,
    resolve_web_session,
    sync_history_from_job,
    web_cabinet_page_vars,
    web_hint_open_links,
    safe_web_next,
)
from bot.common.service.webapp_settings_service import (
    get_hint_viewer_screenshot_font_scale_percent,
)
from bot.common.utils.static_assets import get_static_asset_version
from bot.config import settings
from bot.db.models import HintViewerWebUploadStatus
from bot.db.redis import redis_client

hint_viewer_web_api_router = APIRouter()
templates = Jinja2Templates(directory="bot/templates")
templates.env.globals["cache_timestamp"] = get_static_asset_version()

redis_rq = Redis.from_url(settings.REDIS_URL, decode_responses=False)
task_queue = Queue("backgammon_analysis", connection=redis_rq, default_timeout=1800)
batch_queue = Queue(
    "backgammon_batch_analysis",
    connection=redis_rq,
    default_timeout=BATCH_TIMEOUT_MAX_SEC,
)

MAX_UPLOAD_BYTES = 30 * 1024 * 1024
MAX_MAT_FILES = 40
WEB_JOB_TTL = 86400


def _login_redirect() -> RedirectResponse:
    return RedirectResponse(url="/web/hints/login", status_code=303)


async def _require_session(request: Request) -> tuple[str, dict[str, Any]]:
    token = request.cookies.get(COOKIE_NAME)
    session = await resolve_web_session(request)
    if not token or not session:
        raise HTTPException(status_code=401, detail="Нужна авторизация")
    return token, session


def _web_screenshots_dir(user_id: int) -> Path:
    path = Path("files/screenshots") / f"web_{int(user_id)}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _safe_filename(name: str) -> str:
    base = Path(name or "match.mat").name.replace("\\", "/").split("/")[-1]
    return base or "match.mat"


def _is_mat(name: str) -> bool:
    return _safe_filename(name).lower().endswith(".mat")


def _is_zip(name: str) -> bool:
    return _safe_filename(name).lower().endswith(".zip")


def _read_players(path: str) -> tuple[str, str]:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        return extract_player_names(content)
    except Exception:
        return "Red", "Black"


async def _collect_mat_files(
    uploads: list[UploadFile], workdir: str
) -> list[tuple[str, str]]:
    collected: list[tuple[str, str]] = []
    for upload in uploads:
        raw_name = _safe_filename(upload.filename or "")
        data = await upload.read()
        if not data:
            continue
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=400,
                detail=f"Файл {raw_name} слишком большой (макс. 30 МБ)",
            )
        if _is_zip(raw_name):
            zip_path = os.path.join(workdir, f"in_{uuid.uuid4().hex}.zip")
            with open(zip_path, "wb") as f:
                f.write(data)
            try:
                with zipfile.ZipFile(zip_path, "r") as zf:
                    for info in zf.infolist():
                        if info.is_dir():
                            continue
                        inner = _safe_filename(info.filename)
                        if not _is_mat(inner):
                            continue
                        if ".." in info.filename.replace("\\", "/"):
                            continue
                        target = os.path.join(workdir, f"{uuid.uuid4().hex}_{inner}")
                        with zf.open(info) as src, open(target, "wb") as dst:
                            shutil.copyfileobj(src, dst)
                        collected.append((target, inner))
            except zipfile.BadZipFile as exc:
                raise HTTPException(
                    status_code=400, detail=f"Не удалось открыть архив {raw_name}"
                ) from exc
            finally:
                if os.path.isfile(zip_path):
                    os.remove(zip_path)
        elif _is_mat(raw_name):
            target = os.path.join(workdir, f"{uuid.uuid4().hex}_{raw_name}")
            with open(target, "wb") as f:
                f.write(data)
            collected.append((target, raw_name))
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Поддерживаются только .mat и .zip: {raw_name}",
            )
        if len(collected) > MAX_MAT_FILES:
            raise HTTPException(
                status_code=400,
                detail=f"Слишком много матчей (макс. {MAX_MAT_FILES})",
            )
    return collected


async def _enqueue_single(
    *,
    local_mat: str,
    filename: str,
    web_uid: int,
    session_token: str,
    user_id: int | None,
) -> dict[str, Any]:
    game_id = random_filename(ext="")
    job_id = f"web_hint_{abs(web_uid)}_{uuid.uuid4().hex[:8]}"
    red_player, black_player = _read_players(local_mat)
    estimated_time = estimate_processing_time(local_mat)

    def _put_mat():
        return HintS3Storage.from_settings().put_source_mat(game_id, local_mat)

    mat_s3_key = await asyncio.to_thread(_put_mat)
    task_queue.enqueue(
        "bot.workers.hint_worker.analyze_backgammon_job",
        game_id,
        str(web_uid),
        job_id=job_id,
    )
    await redis_client.set(f"mat_path:{game_id}", mat_s3_key, expire=WEB_JOB_TTL)
    add_active_job(web_uid, job_id, WEB_JOB_TTL)
    await redis_client.set(
        f"job_info:{job_id}",
        json.dumps(
            {
                "type": "single",
                "source": "web",
                "game_id": game_id,
                "mat_s3_key": mat_s3_key,
                "red_player": red_player,
                "black_player": black_player,
                "user_id": web_uid,
                "original_filename": filename,
            }
        ),
        expire=WEB_JOB_TTL,
    )
    job_payload = {
        "kind": "single",
        "job_id": job_id,
        "game_id": game_id,
        "filename": filename,
        "red_player": red_player,
        "black_player": black_player,
        "estimated_time": estimated_time,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await append_session_job(session_token, job_payload)
    await record_history(
        session_id=session_token,
        user_id=user_id,
        original_filename=filename,
        game_id=game_id,
        job_id=job_id,
        red_player=red_player,
        black_player=black_player,
        status=HintViewerWebUploadStatus.QUEUED.value,
    )
    return job_payload


async def _enqueue_batch(
    *,
    files: list[tuple[str, str]],
    web_uid: int,
    session_token: str,
    user_id: int | None,
) -> dict[str, Any]:
    batch_id = f"web_batch_{abs(web_uid)}_{uuid.uuid4().hex[:8]}"
    job_id = f"web_batch_job_{batch_id}"
    total_files = len(files)
    s3 = HintS3Storage.from_settings()

    def upload_batch_inputs():
        keys = []
        for i, (local_path, _) in enumerate(files):
            key = s3.batch_input_key(batch_id, i)
            s3.upload_file(local_path, key)
            keys.append(key)
        return keys

    mat_s3_keys = await asyncio.to_thread(upload_batch_inputs)
    original_fnames = [name for _, name in files]
    players = [_read_players(path) for path, _ in files]
    estimated_time = sum(estimate_processing_time(path) for path, _ in files)
    job_timeout = calc_batch_job_timeout(total_files)

    batch_queue.enqueue(
        "bot.workers.hint_worker.analyze_backgammon_batch_job",
        mat_s3_keys,
        str(web_uid),
        batch_id,
        original_fnames,
        job_id=job_id,
        job_timeout=job_timeout,
        result_ttl=WEB_JOB_TTL,
        failure_ttl=WEB_JOB_TTL,
    )
    add_active_job(web_uid, job_id, job_timeout + 3600)
    await redis_client.set(
        f"job_info:{job_id}",
        json.dumps(
            {
                "type": "batch",
                "source": "web",
                "batch_id": batch_id,
                "user_id": web_uid,
                "total_files": total_files,
                "original_fnames": original_fnames,
            }
        ),
        expire=job_timeout + 3600,
    )
    await redis_client.set(
        f"batch_info:{batch_id}",
        json.dumps(
            {
                "batch_id": batch_id,
                "job_id": job_id,
                "mat_s3_keys": mat_s3_keys,
                "original_fnames": original_fnames,
                "user_id": web_uid,
                "total_files": total_files,
                "status": "queued",
                "job_timeout": job_timeout,
                "source": "web",
            }
        ),
        expire=job_timeout + 3600,
    )
    file_items = []
    for i, fname in enumerate(original_fnames):
        red_player, black_player = players[i]
        file_items.append(
            {
                "index": i,
                "filename": fname,
                "red_player": red_player,
                "black_player": black_player,
            }
        )
        await record_history(
            session_id=session_token,
            user_id=user_id,
            original_filename=fname,
            job_id=job_id,
            batch_id=batch_id,
            red_player=red_player,
            black_player=black_player,
            status=HintViewerWebUploadStatus.QUEUED.value,
        )
    job_payload = {
        "kind": "batch",
        "job_id": job_id,
        "batch_id": batch_id,
        "total_files": total_files,
        "files": file_items,
        "estimated_time": estimated_time,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await append_session_job(session_token, job_payload)
    return job_payload


_JOB_NOT_FOUND_ERROR = "Задача не найдена"
_CURRENT_JOB_KEEP_AFTER_FINISH = timedelta(minutes=20)


def _rq_status(job: Job) -> str:
    if job.is_failed:
        return "error"
    if job.is_finished:
        return "finished"
    if job.is_started:
        return "processing"
    return "queued"


def _is_missing_job(item: dict[str, Any]) -> bool:
    return item.get("error") == _JOB_NOT_FOUND_ERROR


def _parse_dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        ts = value
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ts.astimezone(timezone.utc)
    if isinstance(value, str) and value:
        try:
            ts = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ts.astimezone(timezone.utc)
    return None


def _stamp_finished_at(item: dict[str, Any], rq_job: Job | None = None) -> None:
    if item.get("status") not in {"done", "error"}:
        return
    existing = _parse_dt(item.get("finished_at"))
    if existing:
        item["finished_at"] = existing.isoformat()
        return
    ended = _parse_dt(getattr(rq_job, "ended_at", None) if rq_job is not None else None)
    item["finished_at"] = (ended or datetime.now(timezone.utc)).isoformat()


def _is_stale_current_job(item: dict[str, Any]) -> bool:
    if item.get("status") not in {"done", "error"}:
        return False
    finished = _parse_dt(item.get("finished_at"))
    if not finished:
        return False
    return datetime.now(timezone.utc) - finished >= _CURRENT_JOB_KEEP_AFTER_FINISH


def _enrich_single_job(stored: dict[str, Any]) -> dict[str, Any]:
    job_id = stored.get("job_id")
    item = {**stored, "status": "queued", "view_url": None, "error": None}
    try:
        job = Job.fetch(job_id, connection=redis_rq)
    except NoSuchJobError:
        item["status"] = "error"
        item["error"] = _JOB_NOT_FOUND_ERROR
        return item
    rq_status = _rq_status(job)
    if rq_status == "finished":
        result = job.result or {}
        if isinstance(result, dict) and result.get("status") == "error":
            item["status"] = "error"
            item["error"] = result.get("error") or "Ошибка анализа"
        elif isinstance(result, dict) and result.get("status") == "success":
            game_id = result.get("game_id") or stored.get("game_id")
            item["status"] = "done"
            item["game_id"] = game_id
            item["has_games"] = bool(result.get("has_games"))
            item["open_links"] = web_hint_open_links(
                game_id, stored.get("red_player"), stored.get("black_player")
            )
            item["view_url"] = item["open_links"][0]["url"] if item["open_links"] else None
        else:
            item["status"] = "done"
            game_id = stored.get("game_id")
            item["open_links"] = web_hint_open_links(
                game_id, stored.get("red_player"), stored.get("black_player")
            )
            item["view_url"] = item["open_links"][0]["url"] if item["open_links"] else None
        _stamp_finished_at(item, job)
    else:
        item["status"] = rq_status
        if rq_status == "error":
            _stamp_finished_at(item, job)
    return item


def _enrich_batch_job(stored: dict[str, Any]) -> dict[str, Any]:
    job_id = stored.get("job_id")
    batch_id = stored.get("batch_id")
    total_files = int(stored.get("total_files") or 0)
    item = {**stored, "status": "queued", "error": None}
    files_out = []
    statuses = get_batch_file_statuses(batch_id) if batch_id else {}
    ready = 0
    errors = 0
    for meta in stored.get("files") or []:
        idx = str(meta.get("index"))
        entry = {**meta, "status": "queued", "view_url": None, "error": None}
        raw = statuses.get(idx)
        if raw:
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                payload = {}
            if payload.get("status") == "error":
                entry["status"] = "error"
                entry["error"] = payload.get("error") or "Ошибка анализа"
                errors += 1
            else:
                entry["status"] = "done"
                entry["game_id"] = payload.get("game_id")
                entry["has_games"] = bool(payload.get("has_games"))
                entry["open_links"] = web_hint_open_links(
                    payload.get("game_id"),
                    meta.get("red_player"),
                    meta.get("black_player"),
                )
                entry["view_url"] = (
                    entry["open_links"][0]["url"] if entry["open_links"] else None
                )
                ready += 1
        files_out.append(entry)
    item["files"] = files_out
    item["ready_count"] = ready
    item["error_count"] = errors
    done = bool(total_files and batch_id and is_batch_effectively_done(batch_id, total_files))
    job = None
    try:
        job = Job.fetch(job_id, connection=redis_rq)
        rq_status = _rq_status(job)
        if rq_status == "error" and not done:
            item["status"] = "error"
            item["error"] = "Пакетный анализ завершился с ошибкой"
            _stamp_finished_at(item, job)
            return item
        if rq_status == "finished":
            done = True
        elif not done:
            item["status"] = (
                "processing" if ready or rq_status == "processing" else rq_status
            )
            return item
    except NoSuchJobError:
        if not done:
            item["status"] = "error"
            item["error"] = _JOB_NOT_FOUND_ERROR
            return item
    item["status"] = "done"
    _stamp_finished_at(item, job)
    return item


@hint_viewer_web_api_router.get("/web/hints/login", response_class=HTMLResponse)
async def web_hints_login_page(request: Request, next: str = "/web/hints"):
    next_path = safe_web_next(next)
    if await resolve_web_session(request):
        return RedirectResponse(url=next_path, status_code=303)
    return templates.TemplateResponse(
        "hint_viewer_web_login.html",
        {
            "request": request,
            "error": None,
            "login_value": "",
            "next_path": next_path,
            "cache_timestamp": get_static_asset_version(),
        },
    )


@hint_viewer_web_api_router.post("/web/hints/login")
async def web_hints_login(
    request: Request,
    login: str = Form(""),
    password: str = Form(""),
    next: str = Form("/web/hints"),
):
    next_path = safe_web_next(next)
    user, auth_error = await authenticate_web_user(login, password)
    if not user:
        message = (
            "Срок действия аккаунта истёк"
            if auth_error == "expired"
            else "Неверный логин или пароль"
        )
        return templates.TemplateResponse(
            "hint_viewer_web_login.html",
            {
                "request": request,
                "error": message,
                "login_value": (login or "").strip(),
                "next_path": next_path,
                "cache_timestamp": get_static_asset_version(),
            },
            status_code=200,
        )
    created = await create_session(user)
    response = RedirectResponse(url=next_path, status_code=303)
    response.set_cookie(
        key=COOKIE_NAME,
        value=created["token"],
        max_age=SESSION_TTL_SEC,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return response


@hint_viewer_web_api_router.post("/web/hints/logout")
async def web_hints_logout(request: Request):
    token = request.cookies.get(COOKIE_NAME)
    await destroy_session(token)
    response = _login_redirect()
    response.delete_cookie(COOKIE_NAME, path="/")
    return response


@hint_viewer_web_api_router.get("/web/hints", response_class=HTMLResponse)
async def web_hints_upload_page(request: Request):
    session = await resolve_web_session(request)
    if not session:
        return _login_redirect()
    is_admin = bool(session.get("is_admin"))
    return templates.TemplateResponse(
        "hint_viewer_web_upload.html",
        {
            "request": request,
            "cache_timestamp": get_static_asset_version(),
            "is_admin": is_admin,
            **web_cabinet_page_vars("hints"),
        },
    )


@hint_viewer_web_api_router.post("/web/hints/api/upload")
async def web_hints_upload(request: Request, files: list[UploadFile] = File(...)):
    token, session = await _require_session(request)
    if not files:
        raise HTTPException(status_code=400, detail="Файлы не выбраны")
    workdir = tempfile.mkdtemp(prefix="hint_web_")
    try:
        collected = await _collect_mat_files(files, workdir)
        if not collected:
            raise HTTPException(status_code=400, detail="В загрузке нет .mat файлов")
        web_uid = int(session.get("web_uid") or -int(session.get("user_id") or 1))
        user_id = session.get("user_id")
        user_id = int(user_id) if user_id else None
        if len(collected) == 1:
            local_mat, filename = collected[0]
            payload = await _enqueue_single(
                local_mat=local_mat,
                filename=filename,
                web_uid=web_uid,
                session_token=token,
                user_id=user_id,
            )
        else:
            payload = await _enqueue_batch(
                files=collected,
                web_uid=web_uid,
                session_token=token,
                user_id=user_id,
            )
        return JSONResponse({"ok": True, "job": payload})
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("web hint upload failed: {}", e)
        raise HTTPException(status_code=500, detail="Не удалось поставить анализ в очередь")
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


@hint_viewer_web_api_router.get("/web/hints/api/jobs")
async def web_hints_jobs(request: Request):
    token, _session = await _require_session(request)
    stored = await list_session_jobs(token)
    jobs = []
    kept = []
    for item in stored:
        enriched = (
            _enrich_batch_job(item)
            if item.get("kind") == "batch"
            else _enrich_single_job(item)
        )
        if _is_missing_job(enriched):
            continue
        if _is_stale_current_job(enriched):
            continue
        if enriched.get("finished_at"):
            item["finished_at"] = enriched["finished_at"]
        kept.append(item)
        jobs.append(enriched)
        await sync_history_from_job(enriched)
    await replace_session_jobs(token, kept)
    return {"ok": True, "jobs": jobs}


@hint_viewer_web_api_router.get("/web/hints/api/history")
async def web_hints_history(request: Request, page: int = 1):
    _token, session = await _require_session(request)
    user_id = session.get("user_id")
    payload = (
        await list_history_for_user(
            int(user_id),
            page=page,
            page_size=HISTORY_PAGE_SIZE,
            service="hints",
        )
        if user_id
        else {
            "items": [],
            "page": 1,
            "pages": 1,
            "page_size": HISTORY_PAGE_SIZE,
            "total": 0,
        }
    )
    return {"ok": True, **payload}


@hint_viewer_web_api_router.post("/web/hints/api/save_screenshot")
async def web_save_screenshot(request: Request, photo: UploadFile = File(...)):
    _token, session = await _require_session(request)
    user_id = session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Нужна авторизация")
    photo_bytes = await photo.read()
    if not photo_bytes:
        raise HTTPException(status_code=400, detail="Пустой скриншот")
    buffer_dir = _web_screenshots_dir(int(user_id))
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = buffer_dir / f"screenshot_{timestamp}.png"
    filepath.write_bytes(photo_bytes)
    return {"status": "success"}


@hint_viewer_web_api_router.post("/web/hints/api/download_screenshots")
async def web_download_screenshots(request: Request):
    _token, session = await _require_session(request)
    user_id = session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Нужна авторизация")
    buffer_dir = Path("files/screenshots") / f"web_{int(user_id)}"
    if not buffer_dir.is_dir():
        raise HTTPException(status_code=404, detail="В архиве нет скриншотов")
    screenshots = sorted(p for p in buffer_dir.iterdir() if p.is_file() and p.suffix.lower() == ".png")
    if not screenshots:
        raise HTTPException(status_code=404, detail="В архиве нет скриншотов")
    extras = sorted(
        p
        for p in buffer_dir.iterdir()
        if p.is_file() and p.suffix.lower() != ".png"
    )
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in screenshots:
            zf.write(path, path.name)
        for path in extras:
            zf.write(path, path.name)
    zip_data = zip_buffer.getvalue()
    shutil.rmtree(buffer_dir, ignore_errors=True)
    return Response(
        content=zip_data,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="screenshots.zip"'},
    )


@hint_viewer_web_api_router.get("/web/hints/view", response_class=HTMLResponse)
async def web_hints_view(request: Request, game_id: str | None = None):
    session = await resolve_web_session(request)
    if not session:
        return _login_redirect()
    if not game_id:
        raise HTTPException(status_code=400, detail="Нужен параметр game_id")
    cache_timestamp = get_static_asset_version()
    font_scale = await get_hint_viewer_screenshot_font_scale_percent()
    response = templates.TemplateResponse(
        "hint_viewer.html",
        {
            "request": request,
            "game_id": game_id,
            "cache_timestamp": cache_timestamp,
            "webapp_fullscreen_enabled": False,
            "hint_viewer_screenshot_font_scale_percent": font_scale,
            "match_analysis_mode": False,
            "web_standalone_mode": True,
        },
    )
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response
