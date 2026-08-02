"""
Массовая установка / очистка картинки-фона кадров content_cards.
Цвет editor.canvasBackground не трогаем — только canvasBackgroundPattern.
"""
from __future__ import annotations

import copy
from typing import Any

from bot.db.dao import ContentCardDAO

DEFAULT_PATTERN_MODE = "cover"
DEFAULT_PATTERN_INTERVAL = 100


def has_image_background(editor: dict[str, Any] | None) -> bool:
    """True, если у кадра задан фон картинкой (S3 или data URL). Цвет не учитываем."""
    if not isinstance(editor, dict):
        return False
    pattern = editor.get("canvasBackgroundPattern")
    if not isinstance(pattern, dict):
        return False
    s3_key = str(pattern.get("imageS3Key") or "").strip()
    data_url = str(pattern.get("imageDataUrl") or "").strip()
    return bool(s3_key or data_url)


def iter_frame_entries(frames_wrap: Any) -> list[dict[str, Any]]:
    if not isinstance(frames_wrap, dict):
        return []
    inner = frames_wrap.get("frames")
    if not isinstance(inner, list):
        return []
    return [item for item in inner if isinstance(item, dict)]


def ensure_editor(payload: dict[str, Any]) -> dict[str, Any]:
    editor = payload.get("editor")
    if not isinstance(editor, dict):
        editor = {}
        payload["editor"] = editor
    return editor


def build_pattern(
    *,
    s3_key: str,
    file_name: str,
    image_width: int,
    image_height: int,
    mode: str = DEFAULT_PATTERN_MODE,
    interval: int = DEFAULT_PATTERN_INTERVAL,
) -> dict[str, Any]:
    mode_norm = "cover" if str(mode).lower() == "cover" else "tile"
    return {
        "mode": mode_norm,
        "imageDataUrl": "",
        "imageS3Key": s3_key,
        "imageWidth": max(8, min(4096, int(image_width) or 64)),
        "imageHeight": max(8, min(4096, int(image_height) or 64)),
        "interval": max(20, min(200, int(interval) or 100)),
        "fileName": file_name or "pattern-image.jpg",
    }


def apply_image_bg_to_frames_missing(
    frames_wrap: dict[str, Any],
    pattern: dict[str, Any],
) -> int:
    """Ставит pattern только кадрам без картинки-фона. Цвет не меняет."""
    updated = 0
    for item in iter_frame_entries(frames_wrap):
        payload = item.get("payload")
        if not isinstance(payload, dict):
            continue
        editor = ensure_editor(payload)
        if has_image_background(editor):
            continue
        editor["canvasBackgroundPattern"] = copy.deepcopy(pattern)
        updated += 1
    return updated


def clear_image_bg_from_all_frames(frames_wrap: dict[str, Any]) -> int:
    """Убирает только canvasBackgroundPattern. canvasBackground (цвет) не трогает."""
    cleared = 0
    for item in iter_frame_entries(frames_wrap):
        payload = item.get("payload")
        if not isinstance(payload, dict):
            continue
        editor = payload.get("editor")
        if not isinstance(editor, dict):
            continue
        if not has_image_background(editor):
            continue
        editor["canvasBackgroundPattern"] = None
        cleared += 1
    return cleared


async def clear_all_image_backgrounds(session) -> tuple[int, int, int]:
    """Возвращает (cards_updated, frames_cleared, cards_total)."""
    dao = ContentCardDAO(session)
    cards = await dao.find_all()
    cards_updated = 0
    frames_cleared = 0
    for card in cards:
        frames = copy.deepcopy(card.frames or {})
        n = clear_image_bg_from_all_frames(frames)
        if n <= 0:
            continue
        await dao.update(card.id, {"frames": frames})
        cards_updated += 1
        frames_cleared += n
    return cards_updated, frames_cleared, len(cards)


async def set_missing_image_backgrounds(
    session, pattern: dict[str, Any]
) -> tuple[int, int, int]:
    """Возвращает (cards_updated, frames_updated, cards_total)."""
    dao = ContentCardDAO(session)
    cards = await dao.find_all()
    cards_updated = 0
    frames_updated = 0
    for card in cards:
        frames = copy.deepcopy(card.frames or {})
        n = apply_image_bg_to_frames_missing(frames, pattern)
        if n <= 0:
            continue
        await dao.update(card.id, {"frames": frames})
        cards_updated += 1
        frames_updated += n
    return cards_updated, frames_updated, len(cards)
