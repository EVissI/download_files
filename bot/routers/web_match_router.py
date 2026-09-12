"""
Сервис «Всё о матче» (/web/match).

Порядок стадий: сначала разбор ошибок во внешнем воркере — это единственная
долгая операция, — и уже по его ответу на сервере считается анализ. Анализ
и разбор для плеера быстрые, отдельной очереди им не нужно.

Запись истории на матч одна (service="match"):
  game_id          — стадия ошибок; по job_id её статус обновляет сам воркер,
                     то есть отслеживание готовности работает штатным путём;
  analyze_game_id  — стадия анализа, заполняется после ответа воркера.

Такие матчи не засоряют историю «Анализа» и «Ошибок» — там фильтр по service.
"""

from __future__ import annotations

import asyncio
import tempfile
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from loguru import logger

from bot.common.service.hint_viewer_web_service import (
    HISTORY_PAGE_SIZE,
    WEB_SERVICE_MATCH,
    list_history_for_user,
    list_session_jobs,
    prune_session_jobs,
    replace_session_jobs,
    resolve_web_session,
    web_cabinet_page_vars,
)
from bot.common.utils.static_assets import get_static_asset_version
from bot.db.models import HintViewerWebUploadStatus
from bot.routers.web_upload_folder_routes import (
    register_web_upload_folder_routes,
    resolve_scoped_folder_id,
)
from bot.routers.web_upload_label_routes import register_web_upload_label_routes

web_match_api_router = APIRouter()

templates = Jinja2Templates(directory="bot/templates")

# Размер каждого файла проверяет _collect_mat_files (30 МБ, как в «Ошибках»).
MAX_FILES_PER_UPLOAD = 20
# Дольше этого вторая стадия не считается: значит она сорвалась молча.
HINTS_STAGE_TIMEOUT_SEC = 3 * 60 * 60


def _login_redirect() -> RedirectResponse:
    return RedirectResponse(url="/login?next=/web/match", status_code=303)


async def _require_session(request: Request) -> tuple[str, dict[str, Any]]:
    from bot.common.service.hint_viewer_web_service import COOKIE_NAME

    token = request.cookies.get(COOKIE_NAME)
    session = await resolve_web_session(request)
    if not session or not token:
        raise HTTPException(status_code=401, detail="Нужна авторизация")
    return token, session


@web_match_api_router.get("/web/match", response_class=HTMLResponse)
async def web_match_page(request: Request):
    session = await resolve_web_session(request)
    if not session:
        return _login_redirect()
    from bot.routers.autoanalize_web_router import ensure_web_analyze_worker

    ensure_web_analyze_worker()
    return templates.TemplateResponse(
        "hint_viewer_web_upload.html",
        {
            "request": request,
            "cache_timestamp": get_static_asset_version(),
            "is_admin": bool(session.get("is_admin")),
            **web_cabinet_page_vars(WEB_SERVICE_MATCH),
        },
    )


@web_match_api_router.post("/web/match/api/upload")
async def web_match_upload(request: Request, files: list[UploadFile] = File(...)):
    """
    Каждый файл — отдельный матч. Отправляем его только на разбор ошибок:
    это единственная долгая стадия, и считает её внешний воркер. Исходник
    сохраняем рядом, чтобы потом, по ответу воркера, быстро посчитать анализ
    на сервере, не заставляя пользователя грузить файл второй раз.
    """
    token, session = await _require_session(request)
    user_id = session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Нужна авторизация")

    from bot.routers.autoanalize_web_router import _persist_source
    from bot.routers.hint_viewer_web_router import _collect_mat_files, _enqueue_single

    web_uid = int(session.get("web_uid") or -int(user_id))
    started: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory() as workdir:
        collected = await _collect_mat_files(files, workdir)
        if not collected:
            raise HTTPException(
                status_code=400, detail="Не нашёл .mat ни в файлах, ни в архиве"
            )
        if len(collected) > MAX_FILES_PER_UPLOAD:
            raise HTTPException(
                status_code=400,
                detail=f"За раз можно отправить не больше {MAX_FILES_PER_UPLOAD} матчей",
            )

        for local_path, filename in collected:
            job = await _enqueue_single(
                local_mat=local_path,
                filename=filename,
                web_uid=web_uid,
                session_token=token,
                user_id=int(user_id),
                history_service=WEB_SERVICE_MATCH,
            )
            game_id = str(job.get("game_id") or "")
            # копия исходника переживёт запрос: по ней посчитаем анализ
            await asyncio.to_thread(_persist_source, local_path, filename, game_id)
            started.append({**job, "stage": "hints"})

    logger.info("match: отправлено в разбор ошибок матчей {} web_user={}",
                len(started), user_id)
    return JSONResponse({"ok": True, "jobs": started})


@web_match_api_router.get("/web/match/api/jobs")
async def web_match_jobs(request: Request):
    token, _session = await _require_session(request)
    jobs = await list_session_jobs(token, WEB_SERVICE_MATCH)
    return {"ok": True, "jobs": jobs}


@web_match_api_router.post("/web/match/api/jobs/clear")
async def web_match_jobs_clear(request: Request):
    token, _session = await _require_session(request)
    await replace_session_jobs(token, [], WEB_SERVICE_MATCH)
    return {"ok": True}


async def _start_analyze_stage(row) -> None:
    """
    Ошибки готовы — считаем анализ тем же файлом, что уже лежит на сервере.
    Операция быстрая, поэтому идёт обычной задачей локальной очереди, а не
    через внешний воркер.
    """
    from bot.routers.autoanalize_web_router import (
        _find_analyze_source,
        _prepare_analyze_file,
        _push_analyze_work,
    )

    src = _find_analyze_source(row.game_id, row.original_filename)
    if src is None or not src.is_file():
        row.status = HintViewerWebUploadStatus.ERROR.value
        row.error_message = "Исходник матча не найден — загрузите его заново"
        row.finished_at = datetime.now(timezone.utc)
        logger.warning("match: исходник не найден для game_id={}", row.game_id)
        return

    analyze_game_id = uuid.uuid4().hex[:16]
    _meta, work = await _prepare_analyze_file(
        src_path=str(src),
        filename=row.original_filename,
        token=row.session_id,
        user_id=row.user_id,
        job_id=row.job_id,
        game_id=analyze_game_id,
        kind="single",
    )
    work["service"] = WEB_SERVICE_MATCH
    row.analyze_game_id = analyze_game_id
    row.status = HintViewerWebUploadStatus.PROCESSING.value
    row.finished_at = None
    await _push_analyze_work(work)
    logger.info(
        "match: запущен анализ game_id={} analyze_game_id={}",
        row.game_id,
        analyze_game_id,
    )


async def _reconcile_match_history(user_id: int) -> None:
    """
    Запускает вторую стадию и подчищает зависшее.

    Воркер сам проставляет записи «done», когда разбор ошибок готов, — это
    и есть сигнал, что пора считать анализ. Плюс гасим записи, которые висят
    в работе слишком долго: без этого матч остался бы «в работе» навсегда.
    """
    from sqlalchemy import select

    from bot.db.database import async_session_maker
    from bot.db.models import HintViewerWebUpload

    try:
        async with async_session_maker() as session:
            rows = (
                await session.scalars(
                    select(HintViewerWebUpload).where(
                        HintViewerWebUpload.user_id == int(user_id),
                        HintViewerWebUpload.service == WEB_SERVICE_MATCH,
                        HintViewerWebUpload.status.in_(
                            ("queued", "processing", HintViewerWebUploadStatus.DONE.value)
                        ),
                    )
                )
            ).all()

            changed = False
            now = datetime.now(timezone.utc)
            finished: dict[str, set[str]] = {}
            for row in rows:
                done = row.status == HintViewerWebUploadStatus.DONE.value
                if done and not row.analyze_game_id:
                    # ошибки готовы — пора считать анализ
                    await _start_analyze_stage(row)
                    changed = True
                    continue
                if done:
                    # готово всё: матч уходит из текущих задач в историю
                    if row.session_id and row.job_id:
                        finished.setdefault(row.session_id, set()).add(row.job_id)
                    continue
                created = row.created_at
                if created is None:
                    continue
                if created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
                if (now - created).total_seconds() > HINTS_STAGE_TIMEOUT_SEC:
                    row.status = HintViewerWebUploadStatus.ERROR.value
                    row.error_message = "Разбор ошибок не завершился"
                    row.finished_at = now
                    changed = True
                    if row.session_id and row.job_id:
                        finished.setdefault(row.session_id, set()).add(row.job_id)
            if changed:
                await session.commit()
        for token, job_ids in finished.items():
            await prune_session_jobs(
                token, drop_job_ids=job_ids, service=WEB_SERVICE_MATCH
            )
    except Exception:
        logger.exception("match: сверка истории не удалась")


@web_match_api_router.get("/web/match/api/history")
async def web_match_history(
    request: Request,
    page: int = 1,
    folder_id: int | None = None,
    label: str | None = None,
):
    _token, session = await _require_session(request)
    user_id = session.get("user_id")
    if not user_id:
        return {"ok": True, "items": [], "page": 1, "pages": 1, "total": 0}

    scoped_folder_id = None
    if folder_id:
        scoped_folder_id = await resolve_scoped_folder_id(
            int(user_id), int(folder_id), WEB_SERVICE_MATCH
        )
    await _reconcile_match_history(int(user_id))
    payload = await list_history_for_user(
        int(user_id),
        page=page,
        page_size=HISTORY_PAGE_SIZE,
        service=WEB_SERVICE_MATCH,
        folder_id=scoped_folder_id,
        label=label,
    )
    return {"ok": True, "folder_id": scoped_folder_id, **payload}


# --- действия над матчем: тонкие обёртки над готовыми обработчиками ---------


@web_match_api_router.get("/web/match/api/table")
async def web_match_table(request: Request, game_id: str = ""):
    from bot.routers.autoanalize_web_router import web_analyze_table

    return await web_analyze_table(request, game_id=game_id)


@web_match_api_router.get("/web/match/api/pdf")
async def web_match_pdf(request: Request, game_id: str = ""):
    from bot.routers.autoanalize_web_router import web_analyze_pdf

    return await web_analyze_pdf(request, game_id=game_id)


@web_match_api_router.post("/web/match/api/send-to-board")
async def web_match_send_to_board(request: Request, game_id: str = ""):
    from bot.routers.autoanalize_web_router import web_analyze_send_to_board

    return await web_analyze_send_to_board(request, game_id=game_id)


@web_match_api_router.post("/web/match/api/order-analysis")
async def web_match_order_analysis(request: Request, game_id: str = ""):
    """game_id здесь — стадия ошибок: заказ уходит по разобранному матчу."""
    from bot.routers.hint_viewer_web_router import web_hints_order_analysis

    return await web_hints_order_analysis(request, game_id=game_id)


@web_match_api_router.post("/web/match/api/save-match-analysis")
async def web_match_save_match_analysis(request: Request, game_id: str = ""):
    from bot.routers.hint_viewer_web_router import web_hints_save_match_analysis

    return await web_hints_save_match_analysis(request, game_id=game_id)


@web_match_api_router.post("/web/match/api/send-to-user")
async def web_match_send_to_user(request: Request):
    from bot.routers.hint_viewer_web_router import (
        SendHintToUserBody,
        web_hints_send_to_user,
    )

    payload = await request.json()
    return await web_hints_send_to_user(request, SendHintToUserBody(**payload))


register_web_upload_folder_routes(
    web_match_api_router, service=WEB_SERVICE_MATCH, prefix="/web/match"
)
register_web_upload_label_routes(
    web_match_api_router, service=WEB_SERVICE_MATCH, prefix="/web/match"
)
