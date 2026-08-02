"""
API папок кабинета «Анализ матча» (ROOT_ADMIN).
Регистрирует маршруты на match_analysis_api_router.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from bot.common.tasks.folder_schedule import normalize_weekdays, validate_issue_time_msk
from bot.common.tasks.match_analysis_folder_schedule import (
    remove_ma_folder_schedule_job,
    upsert_ma_folder_schedule_job,
)
from bot.config import bot, settings
from bot.db.dao import MatchAnalysisFolderDAO, MatchAnalysisFolderLinkDAO
from bot.db.database import async_session_maker
from bot.db.models import (
    MatchAnalysis,
    MatchAnalysisFolder,
    MatchAnalysisFolderItem,
    MatchAnalysisFolderSchedule,
)
from bot.routers.match_analysis_router import (
    _resolve_admin_user_id,
    _serialize_list_item,
    match_analysis_api_router,
)

MA_FOLDER_LINK_START_PREFIX = "mafolderlink_"


class MaFolderBaseBody(BaseModel):
    init_data: str


class MaFolderCreateBody(MaFolderBaseBody):
    name: str = Field(..., min_length=1, max_length=255)
    parent_id: int | None = None
    sort_order: int = 0


class MaFolderUpdateBody(MaFolderBaseBody):
    folder_id: int
    name: str | None = Field(None, min_length=1, max_length=255)
    sort_order: int | None = None


class MaFolderMoveBody(MaFolderBaseBody):
    folder_id: int
    new_parent_id: int | None = None
    new_sort_order: int = 0


class MaFolderDeleteBody(MaFolderBaseBody):
    folder_id: int


class MaFolderItemsBody(MaFolderBaseBody):
    folder_id: int
    # Совместимость с JS кабинета: поле называется card_ids.
    card_ids: list[int]


class MaFolderGenerateLinkBody(MaFolderBaseBody):
    folder_id: int


class MaFolderLinkResolveBody(MaFolderBaseBody):
    folder_token: str
    direct_only: bool = False


class MaFolderNavigateLinkBody(MaFolderBaseBody):
    folder_token: str
    target_folder_id: int


class MaFolderScheduleGetBody(MaFolderBaseBody):
    folder_id: int


class MaFolderScheduleSaveBody(MaFolderBaseBody):
    folder_id: int
    cards_per_run: int = Field(1, ge=1, le=3000)
    weekdays: list[str]
    issue_time_msk: str
    labels: list[str] | None = None
    is_active: bool = True


class MaFolderScheduleDeleteBody(MaFolderBaseBody):
    folder_id: int


def _serialize_ma_folder(f: MatchAnalysisFolder) -> dict[str, Any]:
    return {
        "id": f.id,
        "name": f.name,
        "parent_id": f.parent_id,
        "sort_order": f.sort_order,
        "created_by_admin_id": f.created_by_admin_id,
        "created_at": f.created_at.isoformat() if f.created_at else None,
    }


def _serialize_ma_folder_link(link) -> dict[str, Any]:
    return {
        "link_token": link.link_token,
        "folder_id": link.folder_id,
        "is_active": link.is_active,
    }


def _serialize_ma_folder_schedule(
    schedule: MatchAnalysisFolderSchedule | None,
) -> dict | None:
    if not schedule:
        return None
    return {
        "id": schedule.id,
        "folder_id": schedule.folder_id,
        # JS кабинета ожидает cards_per_run
        "cards_per_run": schedule.items_per_run,
        "items_per_run": schedule.items_per_run,
        "weekdays": schedule.weekdays or [],
        "issue_time_msk": schedule.issue_time_msk,
        "labels": [],
        "is_active": schedule.is_active,
        "last_run_at": schedule.last_run_at.isoformat() if schedule.last_run_at else None,
    }


def _sort_folder_tree_nodes(nodes: list[dict]) -> None:
    nodes.sort(key=lambda n: (n.get("sort_order", 0), n.get("id", 0)))
    for node in nodes:
        children = node.get("children")
        if children:
            _sort_folder_tree_nodes(children)


def _collect_folder_tree_ids(nodes: list[dict], placed: set[int]) -> None:
    for node in nodes:
        placed.add(node["id"])
        children = node.get("children")
        if children:
            _collect_folder_tree_ids(children, placed)


def _build_ma_folder_tree(
    folders: list[MatchAnalysisFolder],
    direct_counts: dict[int, int],
    schedules_by_folder: dict[int, MatchAnalysisFolderSchedule] | None = None,
) -> list[dict]:
    schedules_by_folder = schedules_by_folder or {}
    nodes: dict[int, dict] = {}
    for f in folders:
        nodes[f.id] = {
            **_serialize_ma_folder(f),
            "children": [],
            "direct_cards_count": direct_counts.get(f.id, 0),
            "schedule": _serialize_ma_folder_schedule(schedules_by_folder.get(f.id)),
        }

    roots: list[dict] = []
    for f in folders:
        node = nodes[f.id]
        if f.parent_id is not None and f.parent_id in nodes:
            nodes[f.parent_id]["children"].append(node)
        else:
            roots.append(node)

    placed: set[int] = set()
    _collect_folder_tree_ids(roots, placed)
    for f in folders:
        if f.id not in placed:
            roots.append(nodes[f.id])

    _sort_folder_tree_nodes(roots)
    return roots


def _normalize_ids(raw_ids: list[int] | None) -> list[int]:
    seen: set[int] = set()
    out: list[int] = []
    for raw_id in raw_ids or []:
        try:
            mid = int(raw_id)
        except (TypeError, ValueError):
            continue
        if mid < 1 or mid in seen:
            continue
        seen.add(mid)
        out.append(mid)
    return out


async def _build_ma_folder_start_link(link_token: str) -> str:
    me = await bot.get_me()
    if not me.username:
        raise HTTPException(
            status_code=500,
            detail="Не удалось определить username бота для генерации ссылки",
        )
    payload = f"{MA_FOLDER_LINK_START_PREFIX}{link_token}"
    return f"https://t.me/{me.username}?start={payload}"


@match_analysis_api_router.post("/api/match_analysis/folders/tree")
async def ma_folder_tree(body: MaFolderBaseBody):
    _resolve_admin_user_id(body.init_data)
    async with async_session_maker() as session:
        dao = MatchAnalysisFolderDAO(session)
        folders = await dao.get_all_folders()
        counts_res = await session.execute(
            select(
                MatchAnalysisFolderItem.folder_id,
                func.count(MatchAnalysisFolderItem.id),
            ).group_by(MatchAnalysisFolderItem.folder_id)
        )
        direct_counts: dict[int, int] = {row[0]: row[1] for row in counts_res.all()}
        schedules_res = await session.execute(select(MatchAnalysisFolderSchedule))
        schedules_by_folder = {
            schedule.folder_id: schedule for schedule in schedules_res.scalars().all()
        }
        roots = _build_ma_folder_tree(folders, direct_counts, schedules_by_folder)
    return {"folders": roots}


@match_analysis_api_router.post("/api/match_analysis/folders/create")
async def ma_folder_create(body: MaFolderCreateBody):
    user_id = _resolve_admin_user_id(body.init_data)
    async with async_session_maker() as session:
        async with session.begin():
            dao = MatchAnalysisFolderDAO(session)
            if body.parent_id is not None:
                parent = await dao.get_folder_by_id(body.parent_id)
                if not parent:
                    raise HTTPException(
                        status_code=404, detail="Родительская папка не найдена"
                    )
            folder = await dao.create_folder(
                name=body.name,
                parent_id=body.parent_id,
                sort_order=body.sort_order,
                admin_id=user_id,
            )
            return {"folder": _serialize_ma_folder(folder)}


@match_analysis_api_router.post("/api/match_analysis/folders/update")
async def ma_folder_update(body: MaFolderUpdateBody):
    _resolve_admin_user_id(body.init_data)
    async with async_session_maker() as session:
        async with session.begin():
            dao = MatchAnalysisFolderDAO(session)
            folder = await dao.update_folder(
                folder_id=body.folder_id,
                name=body.name,
                sort_order=body.sort_order,
            )
            if not folder:
                raise HTTPException(status_code=404, detail="Папка не найдена")
            return {"folder": _serialize_ma_folder(folder)}


@match_analysis_api_router.post("/api/match_analysis/folders/move")
async def ma_folder_move(body: MaFolderMoveBody):
    _resolve_admin_user_id(body.init_data)
    async with async_session_maker() as session:
        async with session.begin():
            dao = MatchAnalysisFolderDAO(session)
            if body.new_parent_id is not None:
                new_parent = await dao.get_folder_by_id(body.new_parent_id)
                if not new_parent:
                    raise HTTPException(
                        status_code=404, detail="Родительская папка не найдена"
                    )
            try:
                folder = await dao.move_folder(
                    folder_id=body.folder_id,
                    new_parent_id=body.new_parent_id,
                    new_sort_order=body.new_sort_order,
                )
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e)) from e
            if not folder:
                raise HTTPException(status_code=404, detail="Папка не найдена")
            return {"folder": _serialize_ma_folder(folder)}


@match_analysis_api_router.post("/api/match_analysis/folders/delete")
async def ma_folder_delete(body: MaFolderDeleteBody):
    _resolve_admin_user_id(body.init_data)
    async with async_session_maker() as session:
        async with session.begin():
            dao = MatchAnalysisFolderDAO(session)
            schedule = await session.scalar(
                select(MatchAnalysisFolderSchedule).where(
                    MatchAnalysisFolderSchedule.folder_id == body.folder_id
                )
            )
            if schedule:
                remove_ma_folder_schedule_job(schedule)
            deleted = await dao.delete_folder(body.folder_id)
    return {"ok": True, "deleted": deleted}


@match_analysis_api_router.post("/api/match_analysis/folders/add_items")
async def ma_folder_add_items(body: MaFolderItemsBody):
    _resolve_admin_user_id(body.init_data)
    match_ids = _normalize_ids(body.card_ids)
    if not match_ids:
        raise HTTPException(status_code=400, detail="Нужен хотя бы один id матча")

    async with async_session_maker() as session:
        async with session.begin():
            dao = MatchAnalysisFolderDAO(session)
            folder = await dao.get_folder_by_id(body.folder_id)
            if not folder:
                raise HTTPException(status_code=404, detail="Папка не найдена")
            existing = await session.execute(
                select(MatchAnalysis.id).where(MatchAnalysis.id.in_(match_ids))
            )
            found = {int(x) for x in existing.scalars().all() if x is not None}
            missing = [mid for mid in match_ids if mid not in found]
            if missing:
                raise HTTPException(
                    status_code=404,
                    detail=f"Анализы не найдены: {', '.join(map(str, missing))}",
                )
            added = await dao.add_matches_to_folder(body.folder_id, match_ids)
    return {"ok": True, "added_count": added}


@match_analysis_api_router.post("/api/match_analysis/folders/remove_items")
async def ma_folder_remove_items(body: MaFolderItemsBody):
    _resolve_admin_user_id(body.init_data)
    match_ids = _normalize_ids(body.card_ids)
    if not match_ids:
        raise HTTPException(status_code=400, detail="Нужен хотя бы один id матча")

    async with async_session_maker() as session:
        async with session.begin():
            dao = MatchAnalysisFolderDAO(session)
            folder = await dao.get_folder_by_id(body.folder_id)
            if not folder:
                raise HTTPException(status_code=404, detail="Папка не найдена")
            removed = 0
            for mid in match_ids:
                if await dao.remove_match_from_folder(body.folder_id, mid):
                    removed += 1
    return {"ok": True, "removed_count": removed}


@match_analysis_api_router.post("/api/match_analysis/folders/set_items")
async def ma_folder_set_items(body: MaFolderItemsBody):
    _resolve_admin_user_id(body.init_data)
    match_ids = _normalize_ids(body.card_ids)
    async with async_session_maker() as session:
        async with session.begin():
            dao = MatchAnalysisFolderDAO(session)
            folder = await dao.get_folder_by_id(body.folder_id)
            if not folder:
                raise HTTPException(status_code=404, detail="Папка не найдена")
            await dao.set_folder_items(
                folder_id=body.folder_id,
                match_ids_ordered=match_ids,
            )
    return {"ok": True}


@match_analysis_api_router.post("/api/match_analysis/folders/generate_link")
async def ma_folder_generate_link(body: MaFolderGenerateLinkBody):
    user_id = _resolve_admin_user_id(body.init_data)
    async with async_session_maker() as session:
        async with session.begin():
            folder_dao = MatchAnalysisFolderDAO(session)
            folder = await folder_dao.get_folder_by_id(body.folder_id)
            if not folder:
                raise HTTPException(status_code=404, detail="Папка не найдена")
            link_dao = MatchAnalysisFolderLinkDAO(session)
            link = await link_dao.get_or_create_link(
                folder_id=body.folder_id,
                admin_id=user_id,
            )
            link_payload = _serialize_ma_folder_link(link)

    start_link = await _build_ma_folder_start_link(link_payload["link_token"])
    return {**link_payload, "start_link": start_link}


@match_analysis_api_router.post("/api/match_analysis/folders/navigate_link")
async def ma_folder_navigate_link(body: MaFolderNavigateLinkBody):
    _resolve_admin_user_id(body.init_data)
    token = str(body.folder_token or "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="folder_token обязателен")

    async with async_session_maker() as session:
        link_dao = MatchAnalysisFolderLinkDAO(session)
        current_link = await link_dao.find_by_token(token)
        if not current_link:
            raise HTTPException(
                status_code=404, detail="Ссылка не найдена или неактивна"
            )

        folder_dao = MatchAnalysisFolderDAO(session)
        current_folder = await folder_dao.get_folder_by_id(current_link.folder_id)
        target_folder = await folder_dao.get_folder_by_id(body.target_folder_id)
        if not current_folder or not target_folder:
            raise HTTPException(status_code=404, detail="Папка не найдена")

        is_child = target_folder.parent_id == current_folder.id
        is_parent = (
            current_folder.parent_id is not None
            and target_folder.id == current_folder.parent_id
        )
        if not is_child and not is_parent:
            raise HTTPException(status_code=403, detail="Нет доступа к этой папке")

        target_link = await link_dao.get_or_create_link(
            body.target_folder_id,
            admin_id=None,
        )
        await session.commit()
        return _serialize_ma_folder_link(target_link)


@match_analysis_api_router.post("/api/match_analysis/folders/link_resolve")
async def ma_folder_link_resolve(body: MaFolderLinkResolveBody):
    user_id = _resolve_admin_user_id(body.init_data)
    token = str(body.folder_token or "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="folder_token обязателен")

    async with async_session_maker() as session:
        link_dao = MatchAnalysisFolderLinkDAO(session)
        link = await link_dao.find_by_token(token)
        if not link:
            raise HTTPException(
                status_code=404, detail="Ссылка не найдена или неактивна"
            )

        folder_dao = MatchAnalysisFolderDAO(session)
        folder = await folder_dao.get_folder_by_id(link.folder_id)
        if not folder:
            raise HTTPException(status_code=404, detail="Папка не найдена")

        if body.direct_only:
            match_ids = await folder_dao.get_folder_match_ids(link.folder_id)
        else:
            match_ids = await folder_dao.collect_match_ids_for_folder_tree(
                root_folder_id=link.folder_id, include_children=True
            )

        child_folders: list[dict] = []
        all_folders = await folder_dao.get_all_folders()
        counts_res = await session.execute(
            select(
                MatchAnalysisFolderItem.folder_id,
                func.count(MatchAnalysisFolderItem.id),
            ).group_by(MatchAnalysisFolderItem.folder_id)
        )
        direct_counts: dict[int, int] = {row[0]: row[1] for row in counts_res.all()}
        for f in all_folders:
            if f.parent_id == link.folder_id:
                child_link = await link_dao.get_link_for_folder(f.id)
                child_folders.append({
                    "id": f.id,
                    "name": f.name,
                    "parent_id": f.parent_id,
                    "direct_cards_count": direct_counts.get(f.id, 0),
                    "link_token": child_link.link_token if child_link else None,
                })

        cards_data: list[dict] = []
        if match_ids:
            rows_res = await session.execute(
                select(MatchAnalysis).where(MatchAnalysis.id.in_(match_ids))
            )
            by_id = {row.id: row for row in rows_res.scalars().all()}
            match_ids = [mid for mid in match_ids if mid in by_id]
            for mid in match_ids:
                row = by_id.get(mid)
                if row:
                    cards_data.append(_serialize_list_item(row))

        return {
            "folder": _serialize_ma_folder(folder),
            "card_ids": match_ids,
            "cards": cards_data,
            "child_folders": child_folders,
            "is_root_admin": user_id in settings.ROOT_ADMIN_IDS,
        }


@match_analysis_api_router.post("/api/match_analysis/folders/schedule_get")
async def ma_folder_schedule_get(body: MaFolderScheduleGetBody):
    _resolve_admin_user_id(body.init_data)
    async with async_session_maker() as session:
        folder = await session.scalar(
            select(MatchAnalysisFolder).where(MatchAnalysisFolder.id == body.folder_id)
        )
        if not folder:
            raise HTTPException(status_code=404, detail="Папка не найдена")
        schedule = await session.scalar(
            select(MatchAnalysisFolderSchedule).where(
                MatchAnalysisFolderSchedule.folder_id == body.folder_id
            )
        )
    return {"schedule": _serialize_ma_folder_schedule(schedule)}


@match_analysis_api_router.post("/api/match_analysis/folders/schedule_save")
async def ma_folder_schedule_save(body: MaFolderScheduleSaveBody):
    user_id = _resolve_admin_user_id(body.init_data)
    try:
        weekdays = normalize_weekdays(body.weekdays)
        validate_issue_time_msk(body.issue_time_msk)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    async with async_session_maker() as session:
        folder = await session.scalar(
            select(MatchAnalysisFolder).where(MatchAnalysisFolder.id == body.folder_id)
        )
        if not folder:
            raise HTTPException(status_code=404, detail="Папка не найдена")

        schedule = await session.scalar(
            select(MatchAnalysisFolderSchedule).where(
                MatchAnalysisFolderSchedule.folder_id == body.folder_id
            )
        )
        if schedule is None:
            schedule = MatchAnalysisFolderSchedule(
                folder_id=body.folder_id,
                created_by_admin_id=user_id,
            )
            session.add(schedule)

        schedule.items_per_run = int(body.cards_per_run)
        schedule.weekdays = weekdays
        schedule.issue_time_msk = str(body.issue_time_msk).strip()
        schedule.is_active = bool(body.is_active)
        schedule.updated_at = datetime.now(timezone.utc)

        await session.flush()

        try:
            if schedule.is_active:
                upsert_ma_folder_schedule_job(schedule)
            else:
                remove_ma_folder_schedule_job(schedule)
        except ValueError as exc:
            await session.rollback()
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            await session.rollback()
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except Exception as exc:
            await session.rollback()
            logger.exception("Failed to upsert MA folder schedule job: {}", exc)
            raise HTTPException(
                status_code=500,
                detail="Расписание сохранено не полностью: не удалось обновить задачу APScheduler.",
            ) from exc

        await session.commit()
        await session.refresh(schedule)

    return {"schedule": _serialize_ma_folder_schedule(schedule)}


@match_analysis_api_router.post("/api/match_analysis/folders/schedule_delete")
async def ma_folder_schedule_delete(body: MaFolderScheduleDeleteBody):
    _resolve_admin_user_id(body.init_data)
    async with async_session_maker() as session:
        schedule = await session.scalar(
            select(MatchAnalysisFolderSchedule).where(
                MatchAnalysisFolderSchedule.folder_id == body.folder_id
            )
        )
        if not schedule:
            return {"ok": True, "deleted": False}
        remove_ma_folder_schedule_job(schedule)
        await session.delete(schedule)
        await session.commit()
    return {"ok": True, "deleted": True}
