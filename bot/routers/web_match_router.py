"""
Сервис «Всё о матче» (/web/match).

Загруженный файл проходит две стадии подряд: сначала анализ (gnubg считает
статистику), затем разбор ошибок. Параллельно их пускать нельзя — gnubg
одноинстансный и стадии дрались бы за общий лок.

Запись истории на матч одна (service="match"): в game_id лежит стадия анализа,
в hints_game_id — стадия ошибок. Поэтому такие матчи не засоряют историю
«Анализа» и «Ошибок», отфильтрованную по своему service.

Собственной обработки здесь почти нет: страница, постановка в очередь и тонкие
обёртки над уже готовыми действиями обоих сервисов.
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
    append_session_job,
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
    """Каждый файл — отдельный матч: своя запись, свой конвейер, свои кнопки."""
    token, session = await _require_session(request)
    user_id = session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Нужна авторизация")

    from bot.routers.autoanalize_web_router import (
        _prepare_analyze_file,
        _push_analyze_bundle,
    )
    from bot.routers.hint_viewer_web_router import _collect_mat_files

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

        works: list[dict[str, Any]] = []
        for local_path, filename in collected:
            game_id = uuid.uuid4().hex[:16]
            job_id = f"web_match_{abs(int(user_id))}_{uuid.uuid4().hex[:8]}"
            meta, work = await _prepare_analyze_file(
                src_path=local_path,
                filename=filename,
                token=token,
                user_id=int(user_id),
                job_id=job_id,
                game_id=game_id,
                kind="single",
            )
            # стадию ошибок запустит сам обработчик анализа, когда досчитает
            work["service"] = WEB_SERVICE_MATCH
            work["chain_hints"] = True
            works.append(work)
            job_payload = {
                "kind": "single",
                "job_id": job_id,
                "stage": "analyze",
                **meta,
            }
            await append_session_job(token, job_payload, WEB_SERVICE_MATCH)
            started.append(job_payload)

        # Вся пачка уходит одной задачей: файлы разбираются строго по очереди,
        # а не соревнуются за gnubg между собой и с другими сервисами.
        await _push_analyze_bundle(works)

    logger.info("match: принято матчей {} web_user={}", len(started), user_id)
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


async def _reconcile_match_history(user_id: int) -> None:
    """
    Матч считается готовым, когда вторая стадия выложила результат в S3.
    Воркер ошибок про запись матча не знает (истории для неё не заводили),
    поэтому статус досчитываем здесь — тем же приёмом, что и в «Ошибках».

    Он же единственное место, где ловится сорвавшаяся вторая стадия: воркеру
    некуда записать ошибку, поэтому давно висящие записи гасим по возрасту,
    иначе матч остался бы «в работе» навсегда.
    """
    from sqlalchemy import select

    from bot.db.database import async_session_maker
    from bot.db.models import HintViewerWebUpload
    from bot.routers.hint_viewer_web_router import _hint_s3_ready

    try:
        async with async_session_maker() as session:
            rows = (
                await session.scalars(
                    select(HintViewerWebUpload).where(
                        HintViewerWebUpload.user_id == int(user_id),
                        HintViewerWebUpload.service == WEB_SERVICE_MATCH,
                        HintViewerWebUpload.status
                        == HintViewerWebUploadStatus.PROCESSING.value,
                        HintViewerWebUpload.hints_game_id.is_not(None),
                    )
                )
            ).all()
            changed = False
            now = datetime.now(timezone.utc)
            # какие задачи убрать из «текущих» — матч уходит в историю целиком
            finished: dict[str, set[str]] = {}

            def _finish(row) -> None:
                if row.session_id and row.job_id:
                    finished.setdefault(row.session_id, set()).add(row.job_id)

            for row in rows:
                ready = await asyncio.to_thread(_hint_s3_ready, row.hints_game_id)
                if ready:
                    row.status = HintViewerWebUploadStatus.DONE.value
                    row.finished_at = now
                    changed = True
                    _finish(row)
                    continue
                created = row.created_at
                if created is not None:
                    if created.tzinfo is None:
                        created = created.replace(tzinfo=timezone.utc)
                    if (now - created).total_seconds() > HINTS_STAGE_TIMEOUT_SEC:
                        row.status = HintViewerWebUploadStatus.ERROR.value
                        row.error_message = (
                            "Анализ готов, но разбор ошибок не завершился"
                        )
                        row.finished_at = now
                        changed = True
                        _finish(row)
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
