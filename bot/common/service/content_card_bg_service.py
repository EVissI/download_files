"""
Массовая установка / очистка фона кадров content_cards:
- картинка: editor.canvasBackgroundPattern
- цвет: editor.canvasBackground
"""
from __future__ import annotations

import copy
import re
from typing import Any

from bot.db.dao import ContentCardDAO

DEFAULT_PATTERN_MODE = "cover"
DEFAULT_PATTERN_INTERVAL = 100
DEFAULT_CANVAS_BACKGROUND = "#ffffff"

_HEX6_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
_HEX3_RE = re.compile(r"^#[0-9A-Fa-f]{3}$")


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


def normalize_canvas_background_color(raw: str | None) -> str | None:
    """Нормализует цвет к #rrggbb (lowercase) или None если невалидно."""
    s = str(raw or "").strip()
    if _HEX6_RE.fullmatch(s):
        return s.lower()
    if _HEX3_RE.fullmatch(s):
        return "#" + "".join(ch * 2 for ch in s[1:]).lower()
    return None


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


def apply_image_bg_to_all_frames(
    frames_wrap: dict[str, Any],
    pattern: dict[str, Any],
) -> int:
    """Ставит pattern всем кадрам (перезаписывает). Цвет canvasBackground не меняет."""
    updated = 0
    for item in iter_frame_entries(frames_wrap):
        payload = item.get("payload")
        if not isinstance(payload, dict):
            continue
        editor = ensure_editor(payload)
        editor["canvasBackgroundPattern"] = copy.deepcopy(pattern)
        updated += 1
    return updated


def apply_color_bg_to_all_frames(
    frames_wrap: dict[str, Any],
    color: str,
) -> int:
    """
    Ставит canvasBackground всем кадрам и снимает картинку-фон,
    чтобы цвет был виден. color — уже нормализованный #rrggbb.
    """
    updated = 0
    for item in iter_frame_entries(frames_wrap):
        payload = item.get("payload")
        if not isinstance(payload, dict):
            continue
        editor = ensure_editor(payload)
        prev_color = str(editor.get("canvasBackground") or "").strip().lower()
        had_image = has_image_background(editor)
        if prev_color == color and not had_image:
            continue
        editor["canvasBackground"] = color
        if had_image:
            editor["canvasBackgroundPattern"] = None
        updated += 1
    return updated


def reset_bg_on_all_frames(frames_wrap: dict[str, Any]) -> int:
    """
    Обнуляет фон кадра: без картинки, цвет = DEFAULT_CANVAS_BACKGROUND (#ffffff).
    """
    reset = 0
    for item in iter_frame_entries(frames_wrap):
        payload = item.get("payload")
        if not isinstance(payload, dict):
            continue
        editor = ensure_editor(payload)
        had_image = has_image_background(editor)
        prev_color = str(editor.get("canvasBackground") or "").strip().lower()
        if not had_image and prev_color == DEFAULT_CANVAS_BACKGROUND:
            continue
        editor["canvasBackgroundPattern"] = None
        editor["canvasBackground"] = DEFAULT_CANVAS_BACKGROUND
        reset += 1
    return reset


async def reset_all_backgrounds(session) -> tuple[int, int, int]:
    """Возвращает (cards_updated, frames_reset, cards_total)."""
    dao = ContentCardDAO(session)
    cards = await dao.find_all()
    cards_updated = 0
    frames_reset = 0
    for card in cards:
        frames = copy.deepcopy(card.frames or {})
        n = reset_bg_on_all_frames(frames)
        if n <= 0:
            continue
        await dao.update(card.id, {"frames": frames})
        cards_updated += 1
        frames_reset += n
    return cards_updated, frames_reset, len(cards)


# Совместимость со старым именем
async def clear_all_image_backgrounds(session) -> tuple[int, int, int]:
    return await reset_all_backgrounds(session)


async def set_image_backgrounds_on_all(
    session, pattern: dict[str, Any]
) -> tuple[int, int, int]:
    """Возвращает (cards_updated, frames_updated, cards_total)."""
    dao = ContentCardDAO(session)
    cards = await dao.find_all()
    cards_updated = 0
    frames_updated = 0
    for card in cards:
        frames = copy.deepcopy(card.frames or {})
        n = apply_image_bg_to_all_frames(frames, pattern)
        if n <= 0:
            continue
        await dao.update(card.id, {"frames": frames})
        cards_updated += 1
        frames_updated += n
    return cards_updated, frames_updated, len(cards)


async def set_color_backgrounds_on_all(
    session, color: str
) -> tuple[int, int, int]:
    """Возвращает (cards_updated, frames_updated, cards_total). color — #rrggbb."""
    dao = ContentCardDAO(session)
    cards = await dao.find_all()
    cards_updated = 0
    frames_updated = 0
    for card in cards:
        frames = copy.deepcopy(card.frames or {})
        n = apply_color_bg_to_all_frames(frames, color)
        if n <= 0:
            continue
        await dao.update(card.id, {"frames": frames})
        cards_updated += 1
        frames_updated += n
    return cards_updated, frames_updated, len(cards)
