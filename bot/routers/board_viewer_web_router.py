"""Веб-версия плеера (short board / board viewer): загрузка .mat без Telegram."""

from __future__ import annotations

import os
import shutil
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from loguru import logger

from bot.common.func.game_parser import get_names, parse_file
from bot.common.service.hint_viewer_web_service import (
    COOKIE_NAME,
    HISTORY_PAGE_SIZE,
    WEB_SERVICE_BOARD,
    append_session_job,
    get_session,
    list_history_for_user,
    list_session_jobs,
    record_history,
    replace_session_jobs,
    web_board_open_links,
    web_cabinet_page_vars,
    web_user_is_admin,
)
from bot.common.service.webapp_settings_service import (
    get_board_viewer_screenshot_font_scale_percent,
)
from bot.common.utils.static_assets import get_static_asset_version
from bot.db.models import HintViewerWebUploadStatus

board_viewer_web_api_router = APIRouter()
templates = Jinja2Templates(directory="bot/templates")
templates.env.globals["cache_timestamp"] = get_static_asset_version()

_CURRENT_JOB_KEEP_AFTER_FINISH = timedelta(minutes=20)


def _login_redirect() -> RedirectResponse:
    return RedirectResponse(url="/web/hints/login?next=/web/board", status_code=303)


async def _require_session(request: Request) -> tuple[str, dict[str, Any]]:
    token = request.cookies.get(COOKIE_NAME)
    session = await get_session(token)
    if not token or not session:
        raise HTTPException(status_code=401, detail="Нужна авторизация")
    return token, session


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


def _is_stale_current_job(item: dict[str, Any]) -> bool:
    if item.get("status") not in {"done", "error"}:
        return False
    finished = _parse_dt(item.get("finished_at"))
    if not finished:
        return False
    return datetime.now(timezone.utc) - finished >= _CURRENT_JOB_KEEP_AFTER_FINISH


def _read_names(path: str) -> tuple[str, str]:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        names = get_names(content)
        return names[0], names[1]
    except Exception:
        return "Red", "Black"


async def _process_mat(
    local_mat: str,
    filename: str,
    session_token: str,
    user_id: int | None,
    batch_id: str | None = None,
) -> dict[str, Any]:
    dir_name = str(uuid.uuid4())
    files_dir = os.path.join(os.getcwd(), "files", dir_name)
    os.makedirs(files_dir, exist_ok=True)
    dest_name = (filename or "match.mat").replace(" ", "")
    if not dest_name.lower().endswith(".mat"):
        dest_name += ".mat"
    dest_path = os.path.join(files_dir, dest_name)
    shutil.copy(local_mat, dest_path)

    with open(dest_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    red_player, black_player = _read_names(dest_path)
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    status = HintViewerWebUploadStatus.DONE.value
    error = None
    try:
        await parse_file(content, dir_name)
        json_path = os.path.join(files_dir, "games.json")
        if not os.path.isfile(json_path):
            status = HintViewerWebUploadStatus.ERROR.value
            error = "Не удалось разобрать матч"
    except Exception as exc:
        logger.exception("web board parse failed for {}: {}", filename, exc)
        status = HintViewerWebUploadStatus.ERROR.value
        error = str(exc)[:500] or "Не удалось разобрать матч"

    game_id = dir_name if status == HintViewerWebUploadStatus.DONE.value else None
    links = web_board_open_links(game_id) if game_id else []
    job_id = f"web_board_{dir_name[:8]}"
    job = {
        "kind": "single",
        "job_id": job_id,
        "game_id": game_id,
        "filename": filename,
        "red_player": red_player,
        "black_player": black_player,
        "status": status,
        "error": error,
        "created_at": now_iso,
        "finished_at": now_iso,
        "open_links": links,
        "view_url": links[0]["url"] if links else None,
    }
    await record_history(
        session_id=session_token,
        user_id=user_id,
        original_filename=filename,
        game_id=game_id,
        job_id=job_id,
        batch_id=batch_id,
        red_player=red_player,
        black_player=black_player,
        status=status,
        service=WEB_SERVICE_BOARD,
        error_message=error,
    )
    return job


def _enrich_board_job(item: dict[str, Any]) -> dict[str, Any]:
    job = {**item}
    if job.get("kind") == "batch":
        files = []
        for entry in job.get("files") or []:
            files.append(_enrich_board_job(entry))
        job["files"] = files
        return job
    game_id = job.get("game_id")
    if job.get("status") == "done" and game_id:
        links = web_board_open_links(game_id)
        job["open_links"] = links
        job["view_url"] = links[0]["url"] if links else None
    return job


@board_viewer_web_api_router.get("/web/board", response_class=HTMLResponse)
async def web_board_upload_page(request: Request):
    token = request.cookies.get(COOKIE_NAME)
    session = await get_session(token)
    if not session:
        return _login_redirect()
    is_admin = await web_user_is_admin(session.get("user_id"))
    return templates.TemplateResponse(
        "hint_viewer_web_upload.html",
        {
            "request": request,
            "cache_timestamp": get_static_asset_version(),
            "is_admin": is_admin,
            **web_cabinet_page_vars(WEB_SERVICE_BOARD),
        },
    )


@board_viewer_web_api_router.post("/web/board/api/upload")
async def web_board_upload(request: Request, files: list[UploadFile] = File(...)):
    from bot.routers.hint_viewer_web_router import _collect_mat_files

    token, session = await _require_session(request)
    if not files:
        raise HTTPException(status_code=400, detail="Файлы не выбраны")
    workdir = tempfile.mkdtemp(prefix="board_web_")
    try:
        collected = await _collect_mat_files(files, workdir)
        if not collected:
            raise HTTPException(status_code=400, detail="В загрузке нет .mat файлов")
        user_id = session.get("user_id")
        user_id = int(user_id) if user_id else None
        now_iso = datetime.now(timezone.utc).isoformat()
        if len(collected) == 1:
            payload = await _process_mat(
                collected[0][0], collected[0][1], token, user_id
            )
            await append_session_job(token, payload, service=WEB_SERVICE_BOARD)
        else:
            batch_id = f"web_board_batch_{uuid.uuid4().hex[:8]}"
            file_jobs = []
            for local_mat, filename in collected:
                file_jobs.append(
                    await _process_mat(
                        local_mat, filename, token, user_id, batch_id=batch_id
                    )
                )
            ready = sum(1 for j in file_jobs if j.get("status") == "done")
            status = "done" if ready == len(file_jobs) else "error"
            payload = {
                "kind": "batch",
                "job_id": batch_id,
                "status": status,
                "files": file_jobs,
                "ready_count": ready,
                "total_files": len(file_jobs),
                "created_at": now_iso,
                "finished_at": now_iso,
            }
            await append_session_job(token, payload, service=WEB_SERVICE_BOARD)
        return JSONResponse({"ok": True, "job": payload})
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("web board upload failed: {}", e)
        raise HTTPException(status_code=500, detail="Не удалось обработать матч")
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


@board_viewer_web_api_router.get("/web/board/api/jobs")
async def web_board_jobs(request: Request):
    token, _session = await _require_session(request)
    stored = await list_session_jobs(token, service=WEB_SERVICE_BOARD)
    jobs = []
    kept = []
    for item in stored:
        enriched = _enrich_board_job(item)
        if _is_stale_current_job(enriched):
            continue
        kept.append(item)
        jobs.append(enriched)
    await replace_session_jobs(token, kept, service=WEB_SERVICE_BOARD)
    return {"ok": True, "jobs": jobs}


@board_viewer_web_api_router.get("/web/board/api/history")
async def web_board_history(request: Request, page: int = 1):
    _token, session = await _require_session(request)
    user_id = session.get("user_id")
    payload = (
        await list_history_for_user(
            int(user_id),
            page=page,
            page_size=HISTORY_PAGE_SIZE,
            service=WEB_SERVICE_BOARD,
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


@board_viewer_web_api_router.get("/web/board/view", response_class=HTMLResponse)
async def web_board_view(request: Request, game_id: str | None = None):
    token = request.cookies.get(COOKIE_NAME)
    session = await get_session(token)
    if not session:
        return _login_redirect()
    if not game_id:
        raise HTTPException(status_code=400, detail="Нужен параметр game_id")
    json_path = os.path.join("files", game_id, "games.json")
    if not os.path.isfile(json_path):
        raise HTTPException(status_code=404, detail="Игра не найдена")
    font_scale = await get_board_viewer_screenshot_font_scale_percent()
    response = templates.TemplateResponse(
        "board_viewer.html",
        {
            "request": request,
            "game_id": game_id,
            "webapp_fullscreen_enabled": False,
            "cache_timestamp": get_static_asset_version(),
            "board_viewer_screenshot_font_scale_percent": font_scale,
            "web_standalone_mode": True,
        },
    )
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response
