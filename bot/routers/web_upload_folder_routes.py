"""Общие CRUD-маршруты персональных папок веб-загрузок (ошибки / плеер)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy import select

from bot.common.service.hint_viewer_web_service import COOKIE_NAME, resolve_web_session
from bot.common.tasks.folder_schedule import (
    normalize_labels,
    normalize_weekdays,
    validate_issue_time_msk,
)
from bot.common.tasks.hint_web_folder_schedule import (
    remove_hint_web_folder_schedule_job,
    upsert_hint_web_folder_schedule_job,
)
from bot.db.database import async_session_maker
from bot.db.dao import HintViewerWebUploadDAO, HintWebFolderDAO
from bot.db.models import HintWebFolder, HintWebFolderSchedule


class FolderCreateBody(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    parent_id: int | None = None


class FolderUpdateBody(BaseModel):
    folder_id: int
    name: str = Field(min_length=1, max_length=255)


class FolderIdBody(BaseModel):
    folder_id: int


class FolderItemsBody(BaseModel):
    folder_id: int
    upload_ids: list[int] = Field(default_factory=list)


class FolderScheduleSaveBody(BaseModel):
    folder_id: int
    cards_per_run: int = Field(1, ge=1, le=3000)
    weekdays: list[str]
    issue_time_msk: str
    labels: list[str] = Field(default_factory=list)
    is_active: bool = True


async def _require_session(request: Request) -> dict[str, Any]:
    token = request.cookies.get(COOKIE_NAME)
    session = await resolve_web_session(request)
    if not token or not session:
        raise HTTPException(status_code=401, detail="Нужна авторизация")
    return session


def _require_user_id(session: dict[str, Any]) -> int:
    user_id = session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Нужна авторизация")
    return int(user_id)


def _serialize_folder_schedule(
    schedule: HintWebFolderSchedule | None,
) -> dict[str, Any] | None:
    if not schedule:
        return None
    files_per_run = int(schedule.files_per_run or 1)
    return {
        "id": schedule.id,
        "folder_id": schedule.folder_id,
        "files_per_run": files_per_run,
        "cards_per_run": files_per_run,
        "weekdays": schedule.weekdays or [],
        "issue_time_msk": schedule.issue_time_msk,
        "labels": schedule.labels or [],
        "is_active": schedule.is_active,
        "last_run_at": schedule.last_run_at.isoformat() if schedule.last_run_at else None,
    }


def _serialize_folder(
    folder: HintWebFolder,
    direct_files_count: int = 0,
    schedule: HintWebFolderSchedule | None = None,
) -> dict[str, Any]:
    return {
        "id": folder.id,
        "name": folder.name,
        "parent_id": folder.parent_id,
        "sort_order": folder.sort_order,
        "direct_files_count": int(direct_files_count or 0),
        "schedule": _serialize_folder_schedule(schedule),
    }


def _sort_folder_tree_nodes(nodes: list[dict]) -> None:
    nodes.sort(key=lambda n: (n.get("sort_order") or 0, n.get("id") or 0))
    for node in nodes:
        children = node.get("children") or []
        if children:
            _sort_folder_tree_nodes(children)


def _collect_folder_tree_ids(nodes: list[dict], placed: set[int]) -> None:
    for node in nodes:
        placed.add(int(node["id"]))
        _collect_folder_tree_ids(node.get("children") or [], placed)


def _build_folder_tree(
    folders: list[HintWebFolder],
    direct_counts: dict[int, int],
    schedules_by_folder: dict[int, HintWebFolderSchedule] | None = None,
) -> list[dict]:
    schedules_by_folder = schedules_by_folder or {}
    by_id: dict[int, dict] = {}
    for f in folders:
        by_id[f.id] = {
            **_serialize_folder(
                f, direct_counts.get(f.id, 0), schedules_by_folder.get(f.id)
            ),
            "children": [],
        }
    roots: list[dict] = []
    for f in folders:
        node = by_id[f.id]
        if f.parent_id and f.parent_id in by_id:
            by_id[f.parent_id]["children"].append(node)
        else:
            roots.append(node)
    placed: set[int] = set()
    _collect_folder_tree_ids(roots, placed)
    for f in folders:
        if f.id not in placed:
            roots.append(by_id[f.id])
    _sort_folder_tree_nodes(roots)
    return roots


async def resolve_scoped_folder_id(
    user_id: int, folder_id: int, service: str
) -> int:
    async with async_session_maker() as db:
        dao = HintWebFolderDAO(db)
        folder = await dao.get_folder_for_user(int(folder_id), int(user_id), service)
        if not folder:
            raise HTTPException(status_code=404, detail="Папка не найдена")
        return int(folder_id)


def register_web_upload_folder_routes(
    router: APIRouter, *, service: str, prefix: str
) -> None:
    folder_service = service
    base = prefix.rstrip("/")

    def _op(name: str) -> str:
        return f"{folder_service}_{name}"

    @router.post(f"{base}/api/folders/tree", operation_id=_op("folder_tree"))
    async def folder_tree(request: Request):
        session = await _require_session(request)
        user_id = _require_user_id(session)
        async with async_session_maker() as db:
            dao = HintWebFolderDAO(db)
            folders = await dao.get_all_folders(user_id, folder_service)
            counts = await dao.get_direct_counts(user_id, folder_service)
            schedules = await dao.get_schedules_by_folder_id(user_id, folder_service)
            return {
                "ok": True,
                "folders": _build_folder_tree(folders, counts, schedules),
            }

    @router.get(
        f"{base}/api/folders/{{folder_id}}", operation_id=_op("folder_get")
    )
    async def folder_get(request: Request, folder_id: int):
        session = await _require_session(request)
        user_id = _require_user_id(session)
        async with async_session_maker() as db:
            dao = HintWebFolderDAO(db)
            folder = await dao.get_folder_for_user(folder_id, user_id, folder_service)
            if not folder:
                raise HTTPException(status_code=404, detail="Папка не найдена")
            counts = await dao.get_direct_counts(user_id, folder_service)
            children = await dao.get_child_folders(
                folder_id, user_id, folder_service
            )
            schedules = await dao.get_schedules_by_folder_id(user_id, folder_service)
            parent = None
            if folder.parent_id:
                parent_folder = await dao.get_folder_for_user(
                    folder.parent_id, user_id, folder_service
                )
                if parent_folder:
                    parent = _serialize_folder(
                        parent_folder,
                        counts.get(parent_folder.id, 0),
                        schedules.get(parent_folder.id),
                    )
            return {
                "ok": True,
                "folder": _serialize_folder(
                    folder, counts.get(folder.id, 0), schedules.get(folder.id)
                ),
                "parent": parent,
                "child_folders": [
                    _serialize_folder(
                        child, counts.get(child.id, 0), schedules.get(child.id)
                    )
                    for child in children
                ],
            }

    @router.post(f"{base}/api/folders/create", operation_id=_op("folder_create"))
    async def folder_create(request: Request, body: FolderCreateBody):
        session = await _require_session(request)
        user_id = _require_user_id(session)
        name = body.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Введите название папки")
        async with async_session_maker() as db:
            async with db.begin():
                dao = HintWebFolderDAO(db)
                try:
                    folder = await dao.create_folder(
                        user_id=user_id,
                        name=name,
                        parent_id=body.parent_id,
                        service=folder_service,
                    )
                except ValueError as exc:
                    raise HTTPException(status_code=404, detail=str(exc)) from exc
                return {"ok": True, "folder": _serialize_folder(folder)}

    @router.post(f"{base}/api/folders/update", operation_id=_op("folder_update"))
    async def folder_update(request: Request, body: FolderUpdateBody):
        session = await _require_session(request)
        user_id = _require_user_id(session)
        name = body.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Введите название папки")
        async with async_session_maker() as db:
            async with db.begin():
                dao = HintWebFolderDAO(db)
                folder = await dao.update_folder(
                    folder_id=body.folder_id,
                    user_id=user_id,
                    name=name,
                    service=folder_service,
                )
                if not folder:
                    raise HTTPException(status_code=404, detail="Папка не найдена")
                return {"ok": True, "folder": _serialize_folder(folder)}

    @router.post(f"{base}/api/folders/delete", operation_id=_op("folder_delete"))
    async def folder_delete(request: Request, body: FolderIdBody):
        session = await _require_session(request)
        user_id = _require_user_id(session)
        async with async_session_maker() as db:
            async with db.begin():
                dao = HintWebFolderDAO(db)
                folder = await dao.get_folder_for_user(
                    body.folder_id, user_id, folder_service
                )
                if not folder:
                    raise HTTPException(status_code=404, detail="Папка не найдена")
                ids_to_delete = await dao.collect_subtree_folder_ids(
                    body.folder_id, user_id, folder_service
                )
                schedules = (
                    await db.execute(
                        select(HintWebFolderSchedule).where(
                            HintWebFolderSchedule.folder_id.in_(ids_to_delete)
                        )
                    )
                ).scalars().all()
                for schedule in schedules:
                    remove_hint_web_folder_schedule_job(schedule)
                deleted = await dao.delete_folder(
                    body.folder_id, user_id, folder_service
                )
                if not deleted:
                    raise HTTPException(status_code=404, detail="Папка не найдена")
                return {"ok": True}

    @router.post(
        f"{base}/api/folders/add_items", operation_id=_op("folder_add_items")
    )
    async def folder_add_items(request: Request, body: FolderItemsBody):
        session = await _require_session(request)
        user_id = _require_user_id(session)
        async with async_session_maker() as db:
            async with db.begin():
                folder_dao = HintWebFolderDAO(db)
                folder = await folder_dao.get_folder_for_user(
                    body.folder_id, user_id, folder_service
                )
                if not folder:
                    raise HTTPException(status_code=404, detail="Папка не найдена")
                upload_dao = HintViewerWebUploadDAO(db)
                owned_ids = await upload_dao.get_owned_upload_ids(
                    user_id, body.upload_ids, service=folder_service
                )
                if not owned_ids:
                    raise HTTPException(status_code=404, detail="Файлы не найдены")
                added = await folder_dao.add_uploads_to_folder(
                    body.folder_id, owned_ids
                )
                return {"ok": True, "added_count": added}

    @router.post(
        f"{base}/api/folders/remove_items",
        operation_id=_op("folder_remove_items"),
    )
    async def folder_remove_items(request: Request, body: FolderItemsBody):
        session = await _require_session(request)
        user_id = _require_user_id(session)
        async with async_session_maker() as db:
            async with db.begin():
                folder_dao = HintWebFolderDAO(db)
                folder = await folder_dao.get_folder_for_user(
                    body.folder_id, user_id, folder_service
                )
                if not folder:
                    raise HTTPException(status_code=404, detail="Папка не найдена")
                upload_dao = HintViewerWebUploadDAO(db)
                owned_ids = await upload_dao.get_owned_upload_ids(
                    user_id, body.upload_ids, service=folder_service
                )
                removed = 0
                for uid in owned_ids:
                    if await folder_dao.remove_upload_from_folder(
                        body.folder_id, uid
                    ):
                        removed += 1
                return {"ok": True, "removed_count": removed}

    @router.post(
        f"{base}/api/folders/schedule_get", operation_id=_op("folder_schedule_get")
    )
    async def folder_schedule_get(request: Request, body: FolderIdBody):
        session = await _require_session(request)
        user_id = _require_user_id(session)
        async with async_session_maker() as db:
            dao = HintWebFolderDAO(db)
            folder = await dao.get_folder_for_user(
                body.folder_id, user_id, folder_service
            )
            if not folder:
                raise HTTPException(status_code=404, detail="Папка не найдена")
            schedule = await db.scalar(
                select(HintWebFolderSchedule).where(
                    HintWebFolderSchedule.folder_id == body.folder_id
                )
            )
        return {"ok": True, "schedule": _serialize_folder_schedule(schedule)}

    @router.post(
        f"{base}/api/folders/schedule_save",
        operation_id=_op("folder_schedule_save"),
    )
    async def folder_schedule_save(request: Request, body: FolderScheduleSaveBody):
        session = await _require_session(request)
        user_id = _require_user_id(session)
        try:
            weekdays = normalize_weekdays(body.weekdays)
            validate_issue_time_msk(body.issue_time_msk)
            labels = normalize_labels(body.labels)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        async with async_session_maker() as db:
            dao = HintWebFolderDAO(db)
            folder = await dao.get_folder_for_user(
                body.folder_id, user_id, folder_service
            )
            if not folder:
                raise HTTPException(status_code=404, detail="Папка не найдена")

            schedule = await db.scalar(
                select(HintWebFolderSchedule).where(
                    HintWebFolderSchedule.folder_id == body.folder_id
                )
            )
            if schedule is None:
                schedule = HintWebFolderSchedule(folder_id=body.folder_id)
                db.add(schedule)

            schedule.files_per_run = int(body.cards_per_run)
            schedule.weekdays = weekdays
            schedule.issue_time_msk = str(body.issue_time_msk).strip()
            schedule.labels = labels
            schedule.is_active = bool(body.is_active)
            schedule.updated_at = datetime.now(timezone.utc)

            await db.flush()

            try:
                if schedule.is_active:
                    upsert_hint_web_folder_schedule_job(schedule)
                else:
                    remove_hint_web_folder_schedule_job(schedule)
            except ValueError as exc:
                await db.rollback()
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            except RuntimeError as exc:
                await db.rollback()
                raise HTTPException(status_code=503, detail=str(exc)) from exc
            except Exception as exc:
                await db.rollback()
                logger.exception(
                    "Failed to upsert hint web folder schedule job: {}", exc
                )
                raise HTTPException(
                    status_code=500,
                    detail="Расписание сохранено не полностью: не удалось обновить задачу APScheduler.",
                ) from exc

            await db.commit()
            await db.refresh(schedule)

        return {"ok": True, "schedule": _serialize_folder_schedule(schedule)}

    @router.post(
        f"{base}/api/folders/schedule_delete",
        operation_id=_op("folder_schedule_delete"),
    )
    async def folder_schedule_delete(request: Request, body: FolderIdBody):
        session = await _require_session(request)
        user_id = _require_user_id(session)
        async with async_session_maker() as db:
            dao = HintWebFolderDAO(db)
            folder = await dao.get_folder_for_user(
                body.folder_id, user_id, folder_service
            )
            if not folder:
                raise HTTPException(status_code=404, detail="Папка не найдена")
            schedule = await db.scalar(
                select(HintWebFolderSchedule).where(
                    HintWebFolderSchedule.folder_id == body.folder_id
                )
            )
            if not schedule:
                return {"ok": True, "deleted": False}
            remove_hint_web_folder_schedule_job(schedule)
            await db.delete(schedule)
            await db.commit()
        return {"ok": True, "deleted": True}
