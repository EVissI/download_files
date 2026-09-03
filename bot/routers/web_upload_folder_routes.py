"""Общие CRUD-маршруты персональных папок веб-загрузок (ошибки / плеер)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from bot.common.service.hint_viewer_web_service import COOKIE_NAME, resolve_web_session
from bot.db.database import async_session_maker
from bot.db.dao import HintViewerWebUploadDAO, HintWebFolderDAO
from bot.db.models import HintWebFolder


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


def _serialize_folder(folder: HintWebFolder, direct_files_count: int = 0) -> dict[str, Any]:
    return {
        "id": folder.id,
        "name": folder.name,
        "parent_id": folder.parent_id,
        "sort_order": folder.sort_order,
        "direct_files_count": int(direct_files_count or 0),
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
) -> list[dict]:
    by_id: dict[int, dict] = {}
    for f in folders:
        by_id[f.id] = {
            **_serialize_folder(f, direct_counts.get(f.id, 0)),
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
            return {"ok": True, "folders": _build_folder_tree(folders, counts)}

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
            parent = None
            if folder.parent_id:
                parent_folder = await dao.get_folder_for_user(
                    folder.parent_id, user_id, folder_service
                )
                if parent_folder:
                    parent = _serialize_folder(
                        parent_folder, counts.get(parent_folder.id, 0)
                    )
            return {
                "ok": True,
                "folder": _serialize_folder(folder, counts.get(folder.id, 0)),
                "parent": parent,
                "child_folders": [
                    _serialize_folder(child, counts.get(child.id, 0))
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
