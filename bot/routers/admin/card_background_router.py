"""
Админ-команда /card_bg: массово поставить картинку-фон всем кадрам
или обнулить фон (без картинки, цвет #ffffff).
"""
from __future__ import annotations

import uuid
from io import BytesIO

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from loguru import logger
from PIL import Image

from bot.common.service.content_card_bg_service import (
    build_pattern,
    reset_all_backgrounds,
    set_image_backgrounds_on_all,
)
from bot.common.service.hint_s3_service import HintS3Storage
from bot.config import admins

card_background_router = Router()


class CardBgStates(StatesGroup):
    waiting_input = State()


@card_background_router.message(Command("card_bg"))
async def start_card_bg(message: Message, state: FSMContext):
    if message.from_user is None or message.from_user.id not in admins:
        return await message.answer("Доступ запрещен.")

    await state.set_state(CardBgStates.waiting_input)
    await message.answer(
        "Фон кадров карточек.\n\n"
        "• Пришлите фото — поставлю картинку-фон всем кадрам.\n"
        "• Отправьте <code>0</code> — обнулю фон (без картинки, белый цвет).\n"
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
            "Нужно фото или <code>0</code> для обнуления фона. /cancel — отмена."
        )

    await state.clear()
    status = await message.answer("Обнуляю фон у всех кадров…")
    try:
        cards_updated, frames_cleared, cards_total = await reset_all_backgrounds(
            session_without_commit
        )
        await session_without_commit.commit()
        await status.edit_text(
            f"Готово.\n"
            f"Карточек просмотрено: {cards_total}\n"
            f"Карточек изменено: {cards_updated}\n"
            f"Кадров с обнулённым фоном: {frames_cleared}"
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
        await status.edit_text("Ошибка при обнулении фонов. Подробности в логах.")


@card_background_router.message(StateFilter(CardBgStates.waiting_input), F.photo)
async def process_card_bg_photo(message: Message, state: FSMContext, session_without_commit):
    if message.from_user is None or message.from_user.id not in admins:
        await state.clear()
        return await message.answer("Доступ запрещен.")

    await state.clear()
    status = await message.answer("Загружаю фото и обновляю все кадры…")
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

        pattern = build_pattern(
            s3_key=s3_key,
            file_name=unique_name,
            image_width=width,
            image_height=height,
        )
        cards_updated, frames_updated, cards_total = await set_image_backgrounds_on_all(
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
        "Нужно фото или <code>0</code> для обнуления фона. /cancel — отмена."
    )
