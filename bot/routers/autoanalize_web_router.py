"""Веб-кабинет автоанализа партий (GNU Backgammon). Отдельной страницы просмотра нет."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import tempfile
import threading
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from loguru import logger

from bot.common.func.analiz_func import analyze_mat_file
from bot.common.func.func import format_detailed_analysis_html, get_analysis_data
from bot.common.func.hint_viewer import extract_player_names
from bot.common.service.hint_s3_service import HintS3Storage
from bot.common.service.hint_viewer_web_service import (
    COOKIE_NAME,
    HISTORY_PAGE_SIZE,
    WEB_SERVICE_ANALYZE,
    append_session_job,
    list_history_for_user,
    list_session_jobs,
    patch_session_job,
    record_history,
    resolve_web_session,
    sync_history_from_job,
    update_history_status,
    web_cabinet_page_vars,
)
from bot.common.utils.static_assets import get_static_asset_version
from bot.config import translator_hub
from bot.db.models import HintViewerWebUploadStatus
from bot.db.redis import redis_client

autoanalize_web_api_router = APIRouter()
templates = Jinja2Templates(directory="bot/templates")
templates.env.globals["cache_timestamp"] = get_static_asset_version()

MAX_UPLOAD_BYTES = 30 * 1024 * 1024
MAX_ANALYZE_FILES = 40
ANALYZE_DIR = Path("files/web_analyze")
ANALYZE_EXTS = {".mat", ".txt", ".sgf", ".sgg", ".bkg", ".gam", ".pos", ".fibs", ".tmg"}
ANALYZE_PENDING_KEY = "hint_web:analyze:pending"
ANALYZE_ACTIVE_KEY = "hint_web:analyze:active:{game_id}"
ANALYZE_GNU_LOCK_KEY = "hint_web:analyze:gnu_lock"
ANALYZE_GNU_LOCK_TTL = 3 * 3600
ANALYZE_STALE_SEC = 24 * 3600
ANALYZE_REQUEUE_AFTER_SEC = 90

_gnubg_lock = threading.Lock()
_worker_task: asyncio.Task | None = None


def _login_redirect() -> RedirectResponse:
    return RedirectResponse(url="/web/hints/login?next=/web/analyze", status_code=303)


async def _require_session(request: Request) -> tuple[str, dict[str, Any]]:
    token = request.cookies.get(COOKIE_NAME)
    session = await resolve_web_session(request)
    if not token or not session:
        raise HTTPException(status_code=401, detail="Нужна авторизация")
    return token, session


def _safe_filename(name: str) -> str:
    base = Path(name or "match.mat").name.replace("\\", "/").split("/")[-1]
    return base or "match.mat"


def _is_zip(name: str) -> bool:
    return _safe_filename(name).lower().endswith(".zip")


def _is_analyze_file(name: str) -> bool:
    return Path(_safe_filename(name)).suffix.lower() in ANALYZE_EXTS


def _file_type(name: str) -> str | None:
    ext = Path(name).suffix.lower().lstrip(".")
    if ext == "txt":
        return "mat"
    if ext == "gam":
        return None
    return ext or "mat"


def _read_players(path: str) -> tuple[str, str]:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        return extract_player_names(content)
    except Exception:
        return "Red", "Black"


def _run_gnubg(path: str, file_type: str) -> tuple[Any, str]:
    with _gnubg_lock:
        return analyze_mat_file(path, file_type)


def ensure_web_analyze_worker() -> None:
    global _worker_task
    if _worker_task is None or _worker_task.done():
        _worker_task = asyncio.create_task(_worker_loop())


async def _run_gnubg_exclusive(path: str, file_type: str) -> tuple[Any, str]:
    lock_val = uuid.uuid4().hex
    while not await redis_client.set_nx(
        ANALYZE_GNU_LOCK_KEY, lock_val, expire=ANALYZE_GNU_LOCK_TTL
    ):
        await asyncio.sleep(1)
    try:
        return await asyncio.to_thread(_run_gnubg, path, file_type)
    finally:
        current = await redis_client.get(ANALYZE_GNU_LOCK_KEY)
        if current == lock_val:
            await redis_client.delete(ANALYZE_GNU_LOCK_KEY)


async def _patch_job(token: str, job_id: str, mutator) -> dict[str, Any] | None:
    return await patch_session_job(token, job_id, mutator, WEB_SERVICE_ANALYZE)


async def _worker_loop() -> None:
    while True:
        try:
            raw = await redis_client.blpop(ANALYZE_PENDING_KEY, timeout=3)
        except Exception:
            logger.exception("web autoanalyze queue read failed")
            await asyncio.sleep(2)
            continue
        if not raw:
            continue
        try:
            _key, payload = raw
            item = json.loads(payload)
            await _process_file_item(item)
        except Exception:
            logger.exception("web autoanalyze worker failed")


async def _process_file_item(item: dict[str, Any]) -> None:
    token = item["token"]
    job_id = item["job_id"]
    filename = item["filename"]
    src_path = item["src_path"]
    file_type = item["file_type"]
    game_id = item["game_id"]
    kind = item.get("kind") or "single"
    await redis_client.set(
        ANALYZE_ACTIVE_KEY.format(game_id=game_id), "1", expire=ANALYZE_GNU_LOCK_TTL
    )
    try:
        await _process_file_item_inner(
            token, job_id, filename, src_path, file_type, game_id, kind
        )
    finally:
        await redis_client.delete(ANALYZE_ACTIVE_KEY.format(game_id=game_id))


async def _process_file_item_inner(
    token: str,
    job_id: str,
    filename: str,
    src_path: str,
    file_type: str | None,
    game_id: str,
    kind: str,
) -> None:
    async def mark_processing() -> None:
        await update_history_status(
            job_id,
            HintViewerWebUploadStatus.PROCESSING.value,
            original_filename=filename,
            game_id=game_id,
        )

        def mutator(job: dict[str, Any]) -> None:
            if kind == "batch":
                for entry in job.get("files") or []:
                    if entry.get("filename") == filename and entry.get("game_id") == game_id:
                        if entry.get("status") == HintViewerWebUploadStatus.QUEUED.value:
                            entry["status"] = HintViewerWebUploadStatus.PROCESSING.value
                job["status"] = HintViewerWebUploadStatus.PROCESSING.value
            else:
                job["status"] = HintViewerWebUploadStatus.PROCESSING.value

        updated = await _patch_job(token, job_id, mutator)
        if updated:
            await sync_history_from_job(updated)

    await mark_processing()

    async def fail(message: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        await update_history_status(
            job_id,
            HintViewerWebUploadStatus.ERROR.value,
            original_filename=filename,
            game_id=game_id,
            error_message=message,
            finished=True,
        )

        def mutator(job: dict[str, Any]) -> None:
            if kind == "batch":
                ready = 0
                errors = 0
                for entry in job.get("files") or []:
                    if entry.get("filename") == filename and entry.get("game_id") == game_id:
                        entry["status"] = HintViewerWebUploadStatus.ERROR.value
                        entry["error"] = message
                    if entry.get("status") == HintViewerWebUploadStatus.DONE.value:
                        ready += 1
                    elif entry.get("status") == HintViewerWebUploadStatus.ERROR.value:
                        errors += 1
                job["ready_count"] = ready
                total = int(job.get("total_files") or 0)
                if ready + errors >= total:
                    job["status"] = HintViewerWebUploadStatus.DONE.value
                    job["finished_at"] = now
                else:
                    job["status"] = HintViewerWebUploadStatus.PROCESSING.value
            else:
                job["status"] = HintViewerWebUploadStatus.ERROR.value
                job["error"] = message
                job["finished_at"] = now

        updated = await _patch_job(token, job_id, mutator)
        if updated:
            await sync_history_from_job(updated)

    try:
        duration, raw = await _run_gnubg_exclusive(src_path, file_type)
        analysis_data = json.loads(raw)
        player_names = list((analysis_data.get("chequerplay") or {}).keys())
        if len(player_names) != 2:
            await fail("В файле должно быть ровно два игрока")
            return
        metrics = get_analysis_data(analysis_data)
        s3 = HintS3Storage.from_settings()
        await asyncio.to_thread(
            s3.put_autoanalyze_json,
            game_id,
            {
                "players": metrics,
                "duration": duration,
                "filename": filename,
            },
        )
        red_player, black_player = player_names[0], player_names[1]
        now = datetime.now(timezone.utc).isoformat()
        await update_history_status(
            job_id,
            HintViewerWebUploadStatus.DONE.value,
            original_filename=filename,
            game_id=game_id,
            error_message=None,
            finished=True,
            red_player=red_player,
            black_player=black_player,
        )

        def mutator(job: dict[str, Any]) -> None:
            if kind == "batch":
                ready = 0
                errors = 0
                for entry in job.get("files") or []:
                    if entry.get("filename") == filename and entry.get("game_id") == game_id:
                        entry["status"] = HintViewerWebUploadStatus.DONE.value
                        entry["error"] = None
                        entry["red_player"] = red_player
                        entry["black_player"] = black_player
                        entry["expandable"] = True
                    if entry.get("status") == HintViewerWebUploadStatus.DONE.value:
                        ready += 1
                    elif entry.get("status") == HintViewerWebUploadStatus.ERROR.value:
                        errors += 1
                job["ready_count"] = ready
                job["status"] = "processing"
                total = int(job.get("total_files") or 0)
                if ready + errors >= total:
                    job["status"] = HintViewerWebUploadStatus.DONE.value
                    job["finished_at"] = now
            else:
                job["status"] = HintViewerWebUploadStatus.DONE.value
                job["error"] = None
                job["red_player"] = red_player
                job["black_player"] = black_player
                job["expandable"] = True
                job["finished_at"] = now

        updated = await _patch_job(token, job_id, mutator)
        if updated:
            await sync_history_from_job(updated)
    except Exception as exc:
        logger.exception("web autoanalyze failed for {}: {}", filename, exc)
        await fail(str(exc)[:400] or "Не удалось проанализировать файл")


async def _collect_files(uploads: list[UploadFile], workdir: str) -> list[tuple[str, str]]:
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
                        if not _is_analyze_file(inner):
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
        elif _is_analyze_file(raw_name):
            target = os.path.join(workdir, f"{uuid.uuid4().hex}_{raw_name}")
            with open(target, "wb") as f:
                f.write(data)
            collected.append((target, raw_name))
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Неподдерживаемый тип файла: {raw_name}",
            )
        if len(collected) > MAX_ANALYZE_FILES:
            raise HTTPException(
                status_code=400,
                detail=f"Слишком много партий (макс. {MAX_ANALYZE_FILES})",
            )
    return collected


def _persist_source(src: str, filename: str, game_id: str) -> str:
    dest_dir = ANALYZE_DIR / game_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / _safe_filename(filename)
    shutil.copy(src, dest)
    return str(dest)


async def _prepare_analyze_file(
    *,
    src_path: str,
    filename: str,
    token: str,
    user_id: int | None,
    job_id: str,
    game_id: str,
    kind: str,
    batch_id: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    stored = _persist_source(src_path, filename, game_id)
    red_player, black_player = _read_players(stored)
    await record_history(
        session_id=token,
        user_id=user_id,
        original_filename=filename,
        game_id=game_id,
        job_id=job_id,
        batch_id=batch_id,
        red_player=red_player,
        black_player=black_player,
        status=HintViewerWebUploadStatus.QUEUED.value,
        service=WEB_SERVICE_ANALYZE,
    )
    meta = {
        "filename": filename,
        "game_id": game_id,
        "red_player": red_player,
        "black_player": black_player,
        "status": HintViewerWebUploadStatus.QUEUED.value,
        "expandable": False,
    }
    work = {
        "token": token,
        "job_id": job_id,
        "filename": filename,
        "src_path": stored,
        "file_type": _file_type(filename),
        "game_id": game_id,
        "kind": kind,
    }
    return meta, work


async def _push_analyze_work(item: dict[str, Any]) -> None:
    ensure_web_analyze_worker()
    await redis_client.rpush(
        ANALYZE_PENDING_KEY, json.dumps(item, ensure_ascii=False)
    )


async def _pending_analyze_game_ids() -> set[str]:
    ids: set[str] = set()
    try:
        raw_items = await redis_client.lrange(ANALYZE_PENDING_KEY, 0, -1)
    except Exception:
        logger.exception("analyze pending list read failed")
        return ids
    for raw in raw_items:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        gid = payload.get("game_id")
        if gid:
            ids.add(str(gid))
    return ids


@autoanalize_web_api_router.get("/web/analyze", response_class=HTMLResponse)
async def web_analyze_page(request: Request):
    session = await resolve_web_session(request)
    if not session:
        return _login_redirect()
    ensure_web_analyze_worker()
    is_admin = bool(session.get("is_admin"))
    return templates.TemplateResponse(
        "hint_viewer_web_upload.html",
        {
            "request": request,
            "cache_timestamp": get_static_asset_version(),
            "is_admin": is_admin,
            **web_cabinet_page_vars(WEB_SERVICE_ANALYZE),
        },
    )


@autoanalize_web_api_router.post("/web/analyze/api/upload")
async def web_analyze_upload(request: Request, files: list[UploadFile] = File(...)):
    token, session = await _require_session(request)
    uploads = [item for item in files if item and item.filename]
    if not uploads:
        raise HTTPException(status_code=400, detail="Файлы не выбраны")
    workdir = tempfile.mkdtemp(prefix="analyze_web_")
    try:
        collected = await _collect_files(uploads, workdir)
        if not collected:
            raise HTTPException(status_code=400, detail="В загрузке нет файлов партий")
        user_id = session.get("user_id")
        user_id = int(user_id) if user_id else None
        now = datetime.now(timezone.utc).isoformat()
        if len(collected) == 1:
            src, filename = collected[0]
            game_id = uuid.uuid4().hex
            job_id = f"web_analyze_{game_id[:12]}"
            file_meta, work = await _prepare_analyze_file(
                src_path=src,
                filename=filename,
                token=token,
                user_id=user_id,
                job_id=job_id,
                game_id=game_id,
                kind="single",
            )
            job = {
                "kind": "single",
                "job_id": job_id,
                "game_id": game_id,
                "filename": filename,
                "red_player": file_meta["red_player"],
                "black_player": file_meta["black_player"],
                "status": HintViewerWebUploadStatus.QUEUED.value,
                "created_at": now,
                "expandable": False,
            }
            await append_session_job(token, job, WEB_SERVICE_ANALYZE)
            await _push_analyze_work(work)
            return JSONResponse({"ok": True, "job": job})

        batch_id = uuid.uuid4().hex
        job_id = f"web_analyze_batch_{batch_id[:12]}"
        files_meta = []
        works = []
        for src, filename in collected:
            game_id = uuid.uuid4().hex
            meta, work = await _prepare_analyze_file(
                src_path=src,
                filename=filename,
                token=token,
                user_id=user_id,
                job_id=job_id,
                game_id=game_id,
                kind="batch",
                batch_id=batch_id,
            )
            files_meta.append(meta)
            works.append(work)
        job = {
            "kind": "batch",
            "job_id": job_id,
            "batch_id": batch_id,
            "files": files_meta,
            "total_files": len(files_meta),
            "ready_count": 0,
            "status": HintViewerWebUploadStatus.QUEUED.value,
            "created_at": now,
        }
        await append_session_job(token, job, WEB_SERVICE_ANALYZE)
        for work in works:
            await _push_analyze_work(work)
        return JSONResponse({"ok": True, "job": job})
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("web autoanalyze upload failed: {}", e)
        raise HTTPException(status_code=500, detail="Не удалось принять файлы")
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def _row_age_sec(created_at) -> float | None:
    if not created_at:
        return None
    ts = created_at
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - ts.astimezone(timezone.utc)).total_seconds()


async def reconcile_open_analyze_history(user_id: int | None) -> None:
    if not user_id:
        return
    from bot.db.database import async_session_maker
    from bot.db.dao import HintViewerWebUploadDAO, apply_web_upload_status

    s3 = HintS3Storage.from_settings()
    pending_ids = await _pending_analyze_game_ids()
    async with async_session_maker() as session:
        dao = HintViewerWebUploadDAO(session)
        rows = await dao.list_open_for_user(int(user_id), WEB_SERVICE_ANALYZE)
        if not rows:
            return
        changed = False
        for row in rows:
            gid = row.game_id
            payload = None
            if gid:
                try:
                    payload = await asyncio.to_thread(s3.get_autoanalyze_json, gid)
                except Exception:
                    logger.exception("analyze history s3 lookup failed game_id={}", gid)
            if payload:
                apply_web_upload_status(
                    row,
                    HintViewerWebUploadStatus.DONE.value,
                    game_id=gid,
                    finished=True,
                )
                changed = True
                continue
            age = _row_age_sec(row.created_at)
            src = None
            if gid:
                src = ANALYZE_DIR / gid / _safe_filename(row.original_filename or "")
            if (
                gid
                and row.job_id
                and src is not None
                and src.is_file()
                and age is not None
                and age >= ANALYZE_REQUEUE_AFTER_SEC
                and not await redis_client.get(ANALYZE_ACTIVE_KEY.format(game_id=gid))
                and gid not in pending_ids
            ):
                await _push_analyze_work(
                    {
                        "token": row.session_id,
                        "job_id": row.job_id,
                        "filename": row.original_filename,
                        "src_path": str(src),
                        "file_type": _file_type(row.original_filename),
                        "game_id": gid,
                        "kind": "batch" if row.batch_id else "single",
                    }
                )
                pending_ids.add(gid)
                continue
            if age is not None and age >= ANALYZE_STALE_SEC:
                apply_web_upload_status(
                    row,
                    HintViewerWebUploadStatus.ERROR.value,
                    error_message="Анализ прерван, загрузите файл ещё раз",
                    finished=True,
                )
                changed = True
        if changed:
            await session.commit()


async def _refresh_analyze_job_from_results(job: dict[str, Any]) -> dict[str, Any]:
    """Подтягивает готовый результат из S3, если сессия всё ещё показывает очередь."""
    s3 = HintS3Storage.from_settings()
    now = datetime.now(timezone.utc).isoformat()
    if job.get("kind") == "batch":
        ready = 0
        errors = 0
        for entry in job.get("files") or []:
            st = entry.get("status")
            if st == HintViewerWebUploadStatus.ERROR.value:
                errors += 1
                continue
            if st == HintViewerWebUploadStatus.DONE.value:
                ready += 1
                continue
            gid = entry.get("game_id")
            payload = None
            if gid:
                try:
                    payload = await asyncio.to_thread(s3.get_autoanalyze_json, gid)
                except Exception:
                    logger.exception("analyze job s3 lookup failed game_id={}", gid)
            if payload:
                entry["status"] = HintViewerWebUploadStatus.DONE.value
                entry["error"] = None
                entry["expandable"] = True
                ready += 1
        job["ready_count"] = ready
        total = int(job.get("total_files") or 0)
        if total and ready + errors >= total:
            job["status"] = HintViewerWebUploadStatus.DONE.value
            job["finished_at"] = job.get("finished_at") or now
        elif ready or errors:
            job["status"] = HintViewerWebUploadStatus.PROCESSING.value
        return job
    if job.get("status") in {
        HintViewerWebUploadStatus.DONE.value,
        HintViewerWebUploadStatus.ERROR.value,
    }:
        return job
    gid = job.get("game_id")
    if gid:
        try:
            payload = await asyncio.to_thread(s3.get_autoanalyze_json, gid)
        except Exception:
            logger.exception("analyze job s3 lookup failed game_id={}", gid)
            payload = None
        if payload:
            job["status"] = HintViewerWebUploadStatus.DONE.value
            job["error"] = None
            job["expandable"] = True
            job["finished_at"] = job.get("finished_at") or now
    return job


@autoanalize_web_api_router.get("/web/analyze/api/jobs")
async def web_analyze_jobs(request: Request):
    token, session = await _require_session(request)
    ensure_web_analyze_worker()
    await reconcile_open_analyze_history(session.get("user_id"))
    jobs = []
    for stored in await list_session_jobs(token, WEB_SERVICE_ANALYZE):
        original_status = stored.get("status")
        original_ready = stored.get("ready_count")
        refreshed = await _refresh_analyze_job_from_results(stored)
        await sync_history_from_job(refreshed)
        if stored.get("job_id") and (
            refreshed.get("status") != original_status
            or refreshed.get("ready_count") != original_ready
        ):

            def mutator(job: dict[str, Any], snapshot: dict[str, Any] = refreshed) -> None:
                job.update(snapshot)

            await _patch_job(token, stored["job_id"], mutator)
        jobs.append(refreshed)
    return {"ok": True, "jobs": jobs}


@autoanalize_web_api_router.get("/web/analyze/api/history")
async def web_analyze_history(request: Request, page: int = 1):
    _token, session = await _require_session(request)
    ensure_web_analyze_worker()
    user_id = session.get("user_id")
    if user_id:
        await reconcile_open_analyze_history(int(user_id))
    payload = (
        await list_history_for_user(
            int(user_id),
            page=page,
            page_size=HISTORY_PAGE_SIZE,
            service=WEB_SERVICE_ANALYZE,
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


@autoanalize_web_api_router.get("/web/analyze/api/table")
async def web_analyze_table(request: Request, game_id: str = ""):
    _token, session = await _require_session(request)
    gid = (game_id or "").strip()
    if not gid:
        raise HTTPException(status_code=400, detail="Нужен game_id")
    user_id = session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Нужна авторизация")
    from sqlalchemy import select

    from bot.db.database import async_session_maker
    from bot.db.models import HintViewerWebUpload

    async with async_session_maker() as db:
        result = await db.execute(
            select(HintViewerWebUpload.id).where(
                HintViewerWebUpload.user_id == int(user_id),
                HintViewerWebUpload.game_id == gid,
                HintViewerWebUpload.service == WEB_SERVICE_ANALYZE,
            )
        )
        if result.scalar_one_or_none() is None:
            raise HTTPException(status_code=404, detail="Анализ не найден")
    s3 = HintS3Storage.from_settings()
    payload = await asyncio.to_thread(s3.get_autoanalyze_json, gid)
    if not payload:
        raise HTTPException(status_code=404, detail="Таблица ещё не готова")
    metrics = payload.get("players") or payload
    i18n = translator_hub.get_translator_by_locale("ru")
    html = format_detailed_analysis_html(metrics, i18n)
    return {"ok": True, "html": html}
