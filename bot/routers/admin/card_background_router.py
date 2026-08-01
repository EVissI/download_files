"""
Админ-команда /card_bg: массово поставить картинку-фон кадрам без неё
или снять картинку-фон у всех кадров (цвет canvasBackground не трогаем).
"""
from __future__ import annotations

import copy
import uuid
from io import BytesIO
from typing import Any

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from loguru import logger
from PIL import Image

from bot.common.service.hint_s3_service import HintS3Storage
from bot.config import admins
from bot.db.dao import ContentCardDAO

card_background_router = Router()

# Режим как в редакторе: cover = картинка на весь кадр.
_DEFAULT_PATTERN_MODE = "cover"
_DEFAULT_PATTERN_INTERVAL = 100


class CardBgStates(StatesGroup):
    waiting_input = State()


def _has_image_background(editor: dict[str, Any] | None) -> bool:
    """True, если у кадра задан фон картинкой (S3 или data URL). Цвет не учитываем."""
    if not isinstance(editor, dict):
        return False
    pattern = editor.get("canvasBackgroundPattern")
    if not isinstance(pattern, dict):
        return False
    s3_key = str(pattern.get("imageS3Key") or "").strip()
    data_url = str(pattern.get("imageDataUrl") or "").strip()
    return bool(s3_key or data_url)


def _iter_frame_entries(frames_wrap: Any) -> list[dict[str, Any]]:
    if not isinstance(frames_wrap, dict):
        return []
    inner = frames_wrap.get("frames")
    if not isinstance(inner, list):
        return []
    return [item for item in inner if isinstance(item, dict)]


def _ensure_editor(payload: dict[str, Any]) -> dict[str, Any]:
    editor = payload.get("editor")
    if not isinstance(editor, dict):
        editor = {}
        payload["editor"] = editor
    return editor


def _build_pattern(
    *,
    s3_key: str,
    file_name: str,
    image_width: int,
    image_height: int,
) -> dict[str, Any]:
    return {
        "mode": _DEFAULT_PATTERN_MODE,
        "imageDataUrl": "",
        "imageS3Key": s3_key,
        "imageWidth": max(8, min(4096, int(image_width) or 64)),
        "imageHeight": max(8, min(4096, int(image_height) or 64)),
        "interval": _DEFAULT_PATTERN_INTERVAL,
        "fileName": file_name or "pattern-image.jpg",
    }


def apply_image_bg_to_frames_missing(
    frames_wrap: dict[str, Any],
    pattern: dict[str, Any],
) -> int:
    """Ставит pattern только кадрам без картинки-фона. Цвет не меняет. Возвращает число обновлённых кадров."""
    updated = 0
    for item in _iter_frame_entries(frames_wrap):
        payload = item.get("payload")
        if not isinstance(payload, dict):
            continue
        editor = _ensure_editor(payload)
        if _has_image_background(editor):
            continue
        editor["canvasBackgroundPattern"] = copy.deepcopy(pattern)
        updated += 1
    return updated


def clear_image_bg_from_all_frames(frames_wrap: dict[str, Any]) -> int:
    """Убирает только canvasBackgroundPattern. canvasBackground (цвет) не трогает."""
    cleared = 0
    for item in _iter_frame_entries(frames_wrap):
        payload = item.get("payload")
        if not isinstance(payload, dict):
            continue
        editor = payload.get("editor")
        if not isinstance(editor, dict):
            continue
        if not _has_image_background(editor):
            continue
        editor["canvasBackgroundPattern"] = None
        cleared += 1
    return cleared


@card_background_router.message(Command("card_bg"))
async def start_card_bg(message: Message, state: FSMContext):
    if message.from_user is None or message.from_user.id not in admins:
        return await message.answer("Доступ запрещен.")

    await state.set_state(CardBgStates.waiting_input)
    await message.answer(
        "Фон кадров карточек (только картинка, цвет не трогаем).\n\n"
        "• Пришлите фото — поставлю фон всем кадрам без картинки-фона.\n"
        "• Отправьте <code>0</code> — сниму картинку-фон у всех кадров.\n"
        "• /cancel — отмена."
    )


@card_background_router.message(Command("cancel"), StateFilter(CardBgStates.waiting_input))
async def cancel_card_bg(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Отменено.")


@card_background_router.message(StateFilter(CardBgStates.waiting_input), F.text)
async def process_card_bg_text(message: Message, state: FSMContext, session_without_commit):
    if message.from_user is None or message.from_user.id not in admins:
        await state.clear()
        return await message.answer("Доступ запрещен.")

    text = (message.text or "").strip()
    if text != "0":
        return await message.answer(
            "Нужно фото или <code>0</code> для очистки. /cancel — отмена."
        )

    await state.clear()
    status = await message.answer("Снимаю картинку-фон у всех кадров…")
    try:
        cards_updated, frames_cleared, cards_total = await _clear_all_image_backgrounds(
            session_without_commit
        )
        await session_without_commit.commit()
        await status.edit_text(
            f"Готово.\n"
            f"Карточек просмотрено: {cards_total}\n"
            f"Карточек изменено: {cards_updated}\n"
            f"Кадров очищено от картинки-фона: {frames_cleared}"
        )
        logger.info(
            "card_bg clear by {}: cards_updated={} frames_cleared={} total={}",
            message.from_user.id,
            cards_updated,
            frames_cleared,
            cards_total,
        )
    except Exception as e:
        await session_without_commit.rollback()
        logger.exception("Ошибка /card_bg clear: {}", e)
        await status.edit_text("Ошибка при очистке фонов. Подробности в логах.")


@card_background_router.message(StateFilter(CardBgStates.waiting_input), F.photo)
async def process_card_bg_photo(message: Message, state: FSMContext, session_without_commit):
    if message.from_user is None or message.from_user.id not in admins:
        await state.clear()
        return await message.answer("Доступ запрещен.")

    await state.clear()
    status = await message.answer("Загружаю фото и обновляю кадры без фона…")
    try:
        photo = message.photo[-1]
        buf = BytesIO()
        await message.bot.download(photo.file_id, destination=buf)
        raw = buf.getvalue()
        if not raw:
            return await status.edit_text("Не удалось скачать фото.")

        with Image.open(BytesIO(raw)) as img:
            width, height = img.size
            fmt = (img.format or "JPEG").upper()

        ext = ".jpg"
        content_type = "image/jpeg"
        if fmt == "PNG":
            ext = ".png"
            content_type = "image/png"
        elif fmt == "WEBP":
            ext = ".webp"
            content_type = "image/webp"

        admin_id = int(message.from_user.id)
        unique_name = f"{uuid.uuid4().hex}{ext}"
        s3_key = HintS3Storage.content_card_media_key(admin_id, unique_name)
        s3 = HintS3Storage.from_settings()
        s3.upload_bytes(s3_key, raw, content_type=content_type)

        pattern = _build_pattern(
            s3_key=s3_key,
            file_name=unique_name,
            image_width=width,
            image_height=height,
        )
        cards_updated, frames_updated, cards_total = await _set_missing_image_backgrounds(
            session_without_commit, pattern
        )
        await session_without_commit.commit()
        await status.edit_text(
            f"Готово.\n"
            f"S3: <code>{s3_key}</code>\n"
            f"Карточек просмотрено: {cards_total}\n"
            f"Карточек изменено: {cards_updated}\n"
            f"Кадров с новым фоном: {frames_updated}"
        )
        logger.info(
            "card_bg set by {}: key={} cards_updated={} frames_updated={} total={}",
            admin_id,
            s3_key,
            cards_updated,
            frames_updated,
            cards_total,
        )
    except Exception as e:
        await session_without_commit.rollback()
        logger.exception("Ошибка /card_bg set: {}", e)
        await status.edit_text("Ошибка при установке фона. Подробности в логах.")


@card_background_router.message(StateFilter(CardBgStates.waiting_input))
async def process_card_bg_other(message: Message):
    await message.answer(
        "Нужно фото или <code>0</code> для очистки. /cancel — отмена."
    )


async def _clear_all_image_backgrounds(session) -> tuple[int, int, int]:
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


async def _set_missing_image_backgrounds(
    session, pattern: dict[str, Any]
) -> tuple[int, int, int]:
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
