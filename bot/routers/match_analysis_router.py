"""
API и страницы кабинета «Анализ матча» (admin + владельцы UserMatchAnalysis).
"""
from __future__ import annotations

import asyncio
import copy
import json
import mimetypes
import uuid
from typing import Any, Optional

from aiogram.types import InlineKeyboardMarkup, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder
from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response
from fastapi.templating import Jinja2Templates
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from bot.common.service.hint_s3_service import HintS3Storage
from bot.common.service.webapp_settings_service import get_webapp_fullscreen_enabled
from bot.common.utils.tg_auth import verify_telegram_webapp_data
from bot.config import bot, settings
from bot.db.dao import MatchAnalysisActivationLinkDAO, MatchAnalysisDAO
from bot.db.database import async_session_maker
from bot.db.models import MatchAnalysis, User, UserMatchAnalysis
from bot.db.schemas import SMatchAnalysisCreate
from bot.routers.hint_viewer_router import load_analysis_json_from_s3

match_analysis_api_router = APIRouter()
templates = Jinja2Templates(directory="bot/templates")
from bot.common.utils.static_assets import get_static_asset_version as _get_static_v

templates.env.globals["cache_timestamp"] = _get_static_v()

MA_MEDIA_MAX_BYTES = 30 * 1024 * 1024


class MatchAnalysisInitBody(BaseModel):
    init_data: str


class MatchAnalysisIdBody(BaseModel):
    init_data: str
    id: int


class MatchAnalysisSaveBody(BaseModel):
    init_data: str
    game_id: str
    title: Optional[str] = None
    notes: Optional[str] = None


class MatchAnalysisUpdateMetaBody(BaseModel):
    init_data: str
    id: int
    title: Optional[str] = None
    notes: Optional[str] = None
    is_ready: Optional[bool] = None


class MatchAnalysisAudioDeleteBody(BaseModel):
    init_data: str
    id: int
    game_number: int
    move_index: int
    delete_s3: bool = True


class MatchAnalysisAssignBody(BaseModel):
    init_data: str
    target_user_id: int = Field(..., ge=1)
    match_analysis_ids: list[int]


class MatchAnalysisGenerateLinkBody(BaseModel):
    init_data: str
    match_analysis_ids: list[int]


def _require_match_analysis_admin(user_id: int) -> None:
    if user_id not in settings.ROOT_ADMIN_IDS:
        raise HTTPException(
            status_code=403,
            detail="Доступ к «Анализ матча» только для администраторов",
        )


def _resolve_user_id(init_data: str) -> int:
    if not init_data:
        raise HTTPException(status_code=400, detail="Missing init_data")
    user_data = verify_telegram_webapp_data(init_data)
    if not user_data:
        raise HTTPException(status_code=401, detail="Invalid Telegram data")
    user_id = (user_data.get("user") or {}).get("id")
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid user data")
    return int(user_id)


def _resolve_admin_user_id(init_data: str) -> int:
    uid = _resolve_user_id(init_data)
    _require_match_analysis_admin(uid)
    return uid


def _is_ma_admin(user_id: int) -> bool:
    return user_id in settings.ROOT_ADMIN_IDS


def _ma_cabinet_webapp_markup() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text="Открыть «Анализ матча»",
        web_app=WebAppInfo(
            url=f"{settings.MINI_APP_URL.rstrip('/')}/match-analysis-cabinet"
        ),
    )
    kb.adjust(1)
    return kb.as_markup()


def _normalize_ma_ids(raw_ids: list[int] | None) -> list[int]:
    seen: set[int] = set()
    out: list[int] = []
    for raw in raw_ids or []:
        try:
            mid = int(raw)
        except (TypeError, ValueError):
            continue
        if mid < 1 or mid in seen:
            continue
        seen.add(mid)
        out.append(mid)
    return out


async def _build_malink_start_url(link_token: str) -> str:
    me = await bot.get_me()
    if not me.username:
        raise HTTPException(
            status_code=500,
            detail="Не удалось определить username бота для генерации ссылки",
        )
    return f"https://t.me/{me.username}?start=malink_{link_token}"


def _guess_upload_extension(filename: str | None, content_type: str | None) -> str:
    if filename and "." in filename:
        ext = filename.rsplit(".", 1)[-1].lower()
        if ext.isalnum() and len(ext) <= 8:
            return f".{ext}"
    ct = (content_type or "").split(";")[0].strip().lower()
    if ct:
        ext = mimetypes.guess_extension(ct)
        if ext:
            return ".jpg" if ext == ".jpe" else ext
    return ".bin"


def _build_title_from_summary(summary: dict[str, Any], game_id: str) -> str:
    gi = summary.get("game_info") or {}
    red = (gi.get("red_player") or "").strip()
    black = (gi.get("black_player") or "").strip()
    if red or black:
        return f"{red or 'Red'} vs {black or 'Black'}"[:255]
    mat_name = (gi.get("mat_file_name") or "").strip()
    if mat_name:
        return mat_name[:255]
    return f"Матч {game_id}"[:255]


def _build_analysis_document(game_id: str, summary: dict[str, Any]) -> dict[str, Any]:
    """Собирает полный JSON матча: summary + все game_N.json с полями audio*."""
    games_meta = summary.get("games") or []
    games_out: list[dict[str, Any]] = []
    for g in games_meta:
        gnum = g.get("game_number")
        if gnum is None:
            continue
        game_json = load_analysis_json_from_s3(game_id, str(gnum))
        moves = game_json.get("moves") or []
        for move in moves:
            if isinstance(move, dict):
                move.setdefault("audioS3Key", None)
                move.setdefault("audioName", None)
        games_out.append(
            {
                "game_number": int(gnum) if str(gnum).isdigit() else gnum,
                "game_info": game_json.get("game_info") or {},
                "moves": moves,
            }
        )
    game_info = dict(summary.get("game_info") or {})
    return {
        "version": 1,
        "source_game_id": game_id,
        "game_info": game_info,
        "games": games_out,
    }


async def save_match_analysis_from_game_id(
    game_id: str,
    user_id: int,
    *,
    title: str | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    """
    Сохраняет анализ из S3 hints в match_analyses.
    Возвращает {id, title, view_url, cabinet_url}.
    """
    game_id = (game_id or "").strip()
    if not game_id:
        raise ValueError("game_id обязателен")

    summary = await asyncio.to_thread(load_analysis_json_from_s3, game_id, None)
    analysis_doc = await asyncio.to_thread(_build_analysis_document, game_id, summary)
    resolved_title = (title or "").strip() or _build_title_from_summary(summary, game_id)

    async with async_session_maker() as session:
        dao = MatchAnalysisDAO(session)
        row = await dao.add(
            SMatchAnalysisCreate(
                title=resolved_title,
                source_game_id=game_id,
                created_by_user_id=user_id,
                notes=notes,
                analysis=analysis_doc,
            )
        )
        row_id = row.id
        await session.commit()

    base = settings.MINI_APP_URL.rstrip("/")
    return {
        "id": row_id,
        "title": resolved_title,
        "view_url": f"{base}/match-analysis-view?id={row_id}&error=0",
        "cabinet_url": f"{base}/match-analysis-cabinet",
    }


def _find_game_and_move(
    analysis: dict[str, Any], game_number: int, move_index: int
) -> tuple[dict[str, Any], dict[str, Any]]:
    games = analysis.get("games") or []
    game = None
    for g in games:
        try:
            if int(g.get("game_number")) == int(game_number):
                game = g
                break
        except (TypeError, ValueError):
            continue
    if game is None:
        raise HTTPException(status_code=404, detail="Игра не найдена")
    moves = game.get("moves") or []
    if move_index < 0 or move_index >= len(moves):
        raise HTTPException(status_code=404, detail="Ход не найден")
    move = moves[move_index]
    if not isinstance(move, dict):
        raise HTTPException(status_code=400, detail="Некорректный ход")
    return game, move


def _serialize_list_item(row) -> dict[str, Any]:
    gi = (row.analysis or {}).get("game_info") or {}
    games = (row.analysis or {}).get("games") or []
    audio_count = 0
    for g in games:
        for m in g.get("moves") or []:
            if isinstance(m, dict) and m.get("audioS3Key"):
                audio_count += 1
    return {
        "id": row.id,
        "content_card_id": row.id,  # совместимость с тайлами cards_cabinet
        "title": row.title,
        "source_game_id": row.source_game_id,
        "notes": row.notes,
        "is_ready": bool(getattr(row, "is_ready", False)),
        "created_by_user_id": row.created_by_user_id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "red_player": gi.get("red_player"),
        "black_player": gi.get("black_player"),
        "match_length": gi.get("match_length"),
        "games_count": len(games),
        "audio_count": audio_count,
    }


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------


@match_analysis_api_router.get("/match-analysis-cabinet")
async def match_analysis_cabinet_page(request: Request):
    from bot.common.utils.static_assets import get_static_asset_version

    cache_timestamp = get_static_asset_version()
    webapp_fullscreen_enabled = await get_webapp_fullscreen_enabled("cards")
    response = templates.TemplateResponse(
        "cards_cabinet.html",
        {
            "request": request,
            "cache_timestamp": cache_timestamp,
            "webapp_fullscreen_enabled": webapp_fullscreen_enabled,
            "cabinet_kind": "match_analysis",
            "cabinet_pool": "match_analysis",
            "cabinet_base_path": "/match-analysis-cabinet",
            "cabinet_title": "Анализ матча",
            "cabinet_state_key": "match_analysis_cabinet_state_v1",
            "show_open_hints_toggle": False,
            "cabinet_features": {
                "enable_gallery": True,
                "enable_admin_fab": True,
                "enable_search": True,
                "enable_folders": True,
                "enable_labels": False,
                "enable_status_filter": False,
                "enable_shuffle": False,
                "enable_selection": True,
                "enable_bulk_bg": False,
                "enable_interactive_stats": False,
                "enable_create_empty": False,
            },
        },
    )
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@match_analysis_api_router.get("/match-analysis-view")
async def match_analysis_view_page(request: Request, id: int | None = None):
    """Просмотр сохранённого анализа — тот же UI, что hint-viewer, в режиме match_analysis."""
    from bot.common.service.webapp_settings_service import (
        get_hint_viewer_screenshot_font_scale_percent,
    )

    if id is None:
        raise HTTPException(status_code=400, detail="id parameter is required")

    from bot.common.utils.static_assets import get_static_asset_version

    cache_timestamp = get_static_asset_version()
    webapp_fullscreen_enabled = await get_webapp_fullscreen_enabled("hints")
    font_scale = await get_hint_viewer_screenshot_font_scale_percent()
    response = templates.TemplateResponse(
        "hint_viewer.html",
        {
            "request": request,
            "cache_timestamp": cache_timestamp,
            "webapp_fullscreen_enabled": webapp_fullscreen_enabled,
            "hint_viewer_screenshot_font_scale_percent": font_scale,
            "match_analysis_mode": True,
        },
    )
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


@match_analysis_api_router.post("/api/match_analysis/save")
async def match_analysis_save(body: MatchAnalysisSaveBody):
    uid = _resolve_admin_user_id(body.init_data)
    game_id = (body.game_id or "").strip()
    if not game_id:
        raise HTTPException(status_code=400, detail="game_id обязателен")

    try:
        return await save_match_analysis_from_game_id(
            game_id,
            uid,
            title=body.title,
            notes=body.notes,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"match_analysis save load failed game_id={game_id}: {e}")
        raise HTTPException(status_code=500, detail="Не удалось загрузить анализ из S3")


@match_analysis_api_router.post("/api/match_analysis/list")
async def match_analysis_list(body: MatchAnalysisInitBody):
    uid = _resolve_user_id(body.init_data)
    is_admin = _is_ma_admin(uid)
    async with async_session_maker() as session:
        dao = MatchAnalysisDAO(session)
        if is_admin:
            rows = await dao.list_all_ordered()
            ready_count = await dao.count_ready_for_issue()
        else:
            rows = await dao.list_for_user_ordered(uid)
            ready_count = 0
        items = [_serialize_list_item(r) for r in rows]
    return {
        "items": items,
        "is_root_admin": is_admin,
        "ready_for_issue_count": ready_count,
    }


@match_analysis_api_router.post("/api/match_analysis/fetch")
async def match_analysis_fetch(body: MatchAnalysisIdBody):
    uid = _resolve_user_id(body.init_data)
    async with async_session_maker() as session:
        dao = MatchAnalysisDAO(session)
        if not await dao.user_has_access(uid, body.id):
            raise HTTPException(status_code=403, detail="Нет доступа к этому анализу")
        row = await dao.find_one_or_none_by_id(body.id)
        if not row:
            raise HTTPException(status_code=404, detail="Анализ не найден")
        return {
            "id": row.id,
            "title": row.title,
            "source_game_id": row.source_game_id,
            "notes": row.notes,
            "is_ready": bool(getattr(row, "is_ready", False)),
            "created_by_user_id": row.created_by_user_id,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            "analysis": row.analysis,
            "is_root_admin": _is_ma_admin(uid),
        }


@match_analysis_api_router.post("/api/match_analysis/update_meta")
async def match_analysis_update_meta(body: MatchAnalysisUpdateMetaBody):
    _resolve_admin_user_id(body.init_data)
    async with async_session_maker() as session:
        dao = MatchAnalysisDAO(session)
        row = await dao.find_one_or_none_by_id(body.id)
        if not row:
            raise HTTPException(status_code=404, detail="Анализ не найден")
        if body.title is not None:
            title = body.title.strip()
            if not title:
                raise HTTPException(status_code=400, detail="title пустой")
            row.title = title[:255]
        if body.notes is not None:
            row.notes = body.notes
        if body.is_ready is not None:
            row.is_ready = bool(body.is_ready)
        out = {
            "id": row.id,
            "title": row.title,
            "notes": row.notes,
            "is_ready": bool(row.is_ready),
        }
        await session.commit()
        return out


@match_analysis_api_router.post("/api/match_analysis/assign_to_user")
async def match_analysis_assign_to_user(body: MatchAnalysisAssignBody):
    _resolve_admin_user_id(body.init_data)
    ids = _normalize_ma_ids(body.match_analysis_ids)
    if not ids:
        raise HTTPException(
            status_code=400,
            detail="Нужно передать хотя бы один корректный match_analysis_id",
        )

    issued_count = 0
    already_had_count = 0
    invalid_count = 0
    async with async_session_maker() as session:
        target_exists = await session.scalar(
            select(User.id).where(User.id == body.target_user_id).limit(1)
        )
        if target_exists is None:
            raise HTTPException(status_code=404, detail="Пользователь не найден")

        existing_result = await session.execute(
            select(MatchAnalysis.id).where(MatchAnalysis.id.in_(ids))
        )
        existing_ids = {
            int(mid) for mid in existing_result.scalars().all() if mid is not None
        }
        selected = [mid for mid in ids if mid in existing_ids]
        invalid_count = len(ids) - len(selected)
        if not selected:
            raise HTTPException(status_code=404, detail="Выбранные анализы не найдены")

        owned_result = await session.execute(
            select(UserMatchAnalysis.match_analysis_id).where(
                UserMatchAnalysis.user_id == body.target_user_id,
                UserMatchAnalysis.match_analysis_id.in_(selected),
            )
        )
        already_has = {
            int(mid) for mid in owned_result.scalars().all() if mid is not None
        }
        already_had_count = len(already_has)

        for mid in selected:
            if mid in already_has:
                continue
            session.add(
                UserMatchAnalysis(
                    user_id=body.target_user_id,
                    match_analysis_id=mid,
                )
            )
            issued_count += 1

        if issued_count > 0:
            await session.commit()

    notify_sent = False
    notify_error = None
    if issued_count > 0:
        try:
            await bot.send_message(
                chat_id=body.target_user_id,
                text=(
                    f"Вам зачислено {issued_count} анализов матча.\n"
                    "Посмотрите их в кабинете «Анализ матча»."
                ),
                reply_markup=_ma_cabinet_webapp_markup(),
            )
            notify_sent = True
        except Exception as e:
            notify_error = str(e)
            logger.warning("MA assign notify failed: {}", e)

    return {
        "ok": True,
        "issued_count": issued_count,
        "already_had_count": already_had_count,
        "invalid_count": invalid_count,
        "notify_sent": notify_sent,
        "notify_error": notify_error,
    }


@match_analysis_api_router.post("/api/match_analysis/generate_link")
async def match_analysis_generate_link(body: MatchAnalysisGenerateLinkBody):
    _resolve_admin_user_id(body.init_data)
    ids = _normalize_ma_ids(body.match_analysis_ids)
    if not ids:
        raise HTTPException(
            status_code=400,
            detail="Нужно передать хотя бы один корректный match_analysis_id",
        )

    async with async_session_maker() as session:
        existing_result = await session.execute(
            select(MatchAnalysis.id).where(MatchAnalysis.id.in_(ids))
        )
        existing_ids = {
            int(mid) for mid in existing_result.scalars().all() if mid is not None
        }
        selected = [mid for mid in ids if mid in existing_ids]
        if not selected:
            raise HTTPException(status_code=404, detail="Выбранные анализы не найдены")

        link_dao = MatchAnalysisActivationLinkDAO(session)
        try:
            activation_link = await link_dao.create_link(selected)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        link_token = str(activation_link.link)
        await session.commit()

    start_link = await _build_malink_start_url(link_token)
    return {
        "ok": True,
        "link": start_link,
        "token": link_token,
        "cards_count": len(selected),
    }


@match_analysis_api_router.post("/api/match_analysis/delete")
async def match_analysis_delete(body: MatchAnalysisIdBody):
    _resolve_admin_user_id(body.init_data)
    async with async_session_maker() as session:
        dao = MatchAnalysisDAO(session)
        row = await dao.find_one_or_none_by_id(body.id)
        if not row:
            raise HTTPException(status_code=404, detail="Анализ не найден")
        await session.delete(row)
        await session.commit()
    return {"ok": True, "id": body.id}


@match_analysis_api_router.post("/api/match_analysis/audio/upload")
async def match_analysis_audio_upload(
    init_data: str = Form(...),
    match_analysis_id: int = Form(...),
    game_number: int = Form(...),
    move_index: int = Form(...),
    file: UploadFile = File(...),
):
    uid = _resolve_admin_user_id(init_data)
    raw = await file.read()
    if len(raw) > MA_MEDIA_MAX_BYTES:
        raise HTTPException(status_code=413, detail="Файл слишком большой")
    if not raw:
        raise HTTPException(status_code=400, detail="Пустой файл")

    ext = _guess_upload_extension(file.filename, file.content_type)
    unique_name = f"{uuid.uuid4().hex}{ext}"
    key = HintS3Storage.match_analysis_media_key(uid, unique_name)
    ct = file.content_type or mimetypes.guess_type(unique_name)[0] or "audio/webm"
    if ";" in str(ct):
        ct = str(ct).split(";")[0].strip()

    s3 = HintS3Storage.from_settings()
    s3.upload_bytes(key, raw, content_type=ct)

    audio_name = (file.filename or unique_name)[:255]

    async with async_session_maker() as session:
        dao = MatchAnalysisDAO(session)
        row = await dao.find_one_or_none_by_id(match_analysis_id)
        if not row:
            raise HTTPException(status_code=404, detail="Анализ не найден")
        analysis = copy.deepcopy(row.analysis or {})
        _, move = _find_game_and_move(analysis, game_number, move_index)
        old_key = move.get("audioS3Key")
        move["audioS3Key"] = key
        move["audioName"] = audio_name
        row.analysis = analysis
        flag_modified(row, "analysis")
        await session.commit()

    if old_key and old_key != key and HintS3Storage.is_match_analysis_media_key(old_key):
        try:
            s3.delete_object(old_key)
        except Exception as e:
            logger.warning(f"Failed to delete old match analysis audio {old_key}: {e}")

    logger.info(
        f"Match analysis audio uploaded: ma={match_analysis_id} "
        f"g={game_number} m={move_index} key={key} user={uid}"
    )
    return {
        "s3_key": key,
        "audio_name": audio_name,
        "content_type": ct,
        "game_number": game_number,
        "move_index": move_index,
    }


@match_analysis_api_router.post("/api/match_analysis/audio/delete")
async def match_analysis_audio_delete(body: MatchAnalysisAudioDeleteBody):
    _resolve_admin_user_id(body.init_data)
    s3 = HintS3Storage.from_settings()
    async with async_session_maker() as session:
        dao = MatchAnalysisDAO(session)
        row = await dao.find_one_or_none_by_id(body.id)
        if not row:
            raise HTTPException(status_code=404, detail="Анализ не найден")
        analysis = copy.deepcopy(row.analysis or {})
        _, move = _find_game_and_move(analysis, body.game_number, body.move_index)
        old_key = move.get("audioS3Key")
        move["audioS3Key"] = None
        move["audioName"] = None
        row.analysis = analysis
        flag_modified(row, "analysis")
        await session.commit()

    if body.delete_s3 and old_key and HintS3Storage.is_match_analysis_media_key(old_key):
        try:
            s3.delete_object(old_key)
        except Exception as e:
            logger.warning(f"Failed to delete match analysis audio {old_key}: {e}")

    return {"ok": True, "game_number": body.game_number, "move_index": body.move_index}


@match_analysis_api_router.get("/api/match_analysis/media")
async def match_analysis_media_proxy(key: str = Query(...)):
    if not key:
        raise HTTPException(status_code=400, detail="Параметр key обязателен")
    if not HintS3Storage.is_match_analysis_media_key(key):
        raise HTTPException(status_code=400, detail="Некорректный key")
    s3 = HintS3Storage.from_settings()
    if not s3.exists(key):
        raise HTTPException(status_code=404, detail="Файл не найден")
    blob = s3.download_bytes(key)
    fname = key.rsplit("/", 1)[-1]
    media_type = mimetypes.guess_type(fname)[0] or "application/octet-stream"
    return Response(
        content=blob,
        media_type=media_type,
        headers={"Cache-Control": "public, max-age=3600"},
    )


# Регистрация API папок на том же router.
from bot.routers import match_analysis_folder_routes as _match_analysis_folder_routes  # noqa: E402,F401
