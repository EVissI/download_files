"""Персональные метки веб-загрузок (ошибки / плеер)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError

from bot.common.service.hint_viewer_web_service import COOKIE_NAME, resolve_web_session
from bot.db.database import async_session_maker
from bot.db.dao import HintViewerWebUploadDAO, HintWebLabelDAO


class LabelSetBody(BaseModel):
    upload_id: int
    labels: list[str] = Field(default_factory=list)


class LabelPresetCreateBody(BaseModel):
    value: str = Field(min_length=1, max_length=255)


class LabelPresetDeleteBody(BaseModel):
    preset_id: int


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


def normalize_labels(raw: list[str] | None) -> list[str]:
    if not raw:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for item in raw[:200]:
        text = str(item).strip()[:255]
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return out


def register_web_upload_label_routes(
    router: APIRouter, *, service: str, prefix: str
) -> None:
    label_service = service
    base = prefix.rstrip("/")

    def _op(name: str) -> str:
        return f"{label_service}_{name}"

    @router.post(f"{base}/api/labels/all", operation_id=_op("labels_all"))
    async def labels_all(request: Request):
        session = await _require_session(request)
        user_id = _require_user_id(session)
        async with async_session_maker() as db:
            dao = HintWebLabelDAO(db)
            labels = await dao.list_all_labels(user_id, label_service)
            return {"ok": True, "labels": labels}

    @router.post(f"{base}/api/labels/set", operation_id=_op("labels_set"))
    async def labels_set(request: Request, body: LabelSetBody):
        session = await _require_session(request)
        user_id = _require_user_id(session)
        labels = normalize_labels(body.labels)
        async with async_session_maker() as db:
            async with db.begin():
                upload_dao = HintViewerWebUploadDAO(db)
                owned = await upload_dao.get_owned_upload_ids(
                    user_id, [body.upload_id], service=label_service
                )
                if not owned:
                    raise HTTPException(status_code=404, detail="Файл не найден")
                dao = HintWebLabelDAO(db)
                saved = await dao.set_labels(user_id, owned[0], labels)
                return {"ok": True, "labels": saved}

    @router.post(f"{base}/api/labels/presets", operation_id=_op("label_presets"))
    async def label_presets(request: Request):
        session = await _require_session(request)
        user_id = _require_user_id(session)
        async with async_session_maker() as db:
            dao = HintWebLabelDAO(db)
            presets = await dao.list_presets(user_id, label_service)
            return {
                "ok": True,
                "presets": [{"id": p.id, "value": p.value} for p in presets],
            }

    @router.post(
        f"{base}/api/labels/presets/create",
        operation_id=_op("label_preset_create"),
    )
    async def label_preset_create(request: Request, body: LabelPresetCreateBody):
        session = await _require_session(request)
        user_id = _require_user_id(session)
        value = body.value.strip()[:255]
        if not value:
            raise HTTPException(status_code=400, detail="Введите текст пресета")
        async with async_session_maker() as db:
            async with db.begin():
                dao = HintWebLabelDAO(db)
                try:
                    preset = await dao.create_preset(user_id, label_service, value)
                except IntegrityError as exc:
                    raise HTTPException(
                        status_code=400, detail="Такой пресет уже есть"
                    ) from exc
                return {"ok": True, "preset": {"id": preset.id, "value": preset.value}}

    @router.post(
        f"{base}/api/labels/presets/delete",
        operation_id=_op("label_preset_delete"),
    )
    async def label_preset_delete(request: Request, body: LabelPresetDeleteBody):
        session = await _require_session(request)
        user_id = _require_user_id(session)
        async with async_session_maker() as db:
            async with db.begin():
                dao = HintWebLabelDAO(db)
                deleted = await dao.delete_preset(
                    body.preset_id, user_id, label_service
                )
                if not deleted:
                    raise HTTPException(status_code=404, detail="Пресет не найден")
                return {"ok": True}
