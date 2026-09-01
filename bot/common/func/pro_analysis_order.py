"""Заказ анализа у эксперта: хранение заявки и рассылка .mat админам."""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
import uuid
from typing import TYPE_CHECKING, Any

from aiogram import Bot
from aiogram.types import FSInputFile, Message
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from bot.common.func.telegram_safe import safe_answer
from bot.common.kbds.inline.pro_analysis import (
    get_pro_analysis_admin_reply_kb,
    get_pro_analysis_order_kb,
)
from bot.common.service.hint_s3_service import HintS3Storage
from bot.config import settings, translator_hub
from bot.db.dao import UserDAO
from bot.db.models import User
from bot.db.redis import redis_client
from bot.db.schemas import SUser

if TYPE_CHECKING:
    from locales.stub import TranslatorRunner

PRO_ORDER_REDIS_PREFIX = "pro_order:"
PRO_ORDER_TTL = 86400


def _get_i18n(lang_code: str | None = None) -> "TranslatorRunner":
    return translator_hub.get_translator_by_locale(lang_code or "ru")


def _service_label(i18n: "TranslatorRunner", service: str) -> str:
    # fluentogram накапливает ключ на одном runner — нельзя сохранять getters
    # и нельзя вызывать i18n.* пока уже открыт другой атрибутный путь.
    if service == "hint_viewer":
        return i18n.pro.analysis.service_hints()
    if service == "autoanaliz":
        return i18n.pro.analysis.service_match()
    if service == "short_board":
        return i18n.pro.analysis.service_short_board()
    return service or "—"


async def create_pro_order(
    *,
    user_id: int,
    username: str | None,
    service: str,
    file_path: str | None = None,
    s3_key: str | None = None,
    file_name: str | None = None,
) -> str:
    """Сохраняет заявку в Redis и возвращает request_id для callback."""
    if not file_path and not s3_key:
        raise ValueError("Нужен file_path или s3_key")

    request_id = uuid.uuid4().hex[:12]
    payload = {
        "user_id": int(user_id),
        "username": (username or "").lstrip("@") or None,
        "service": service,
        "file_path": file_path,
        "s3_key": s3_key,
        "file_name": file_name
        or (os.path.basename(file_path) if file_path else None)
        or "match.mat",
    }
    await redis_client.set(
        f"{PRO_ORDER_REDIS_PREFIX}{request_id}",
        json.dumps(payload),
        expire=PRO_ORDER_TTL,
    )
    return request_id


async def load_pro_order(request_id: str) -> dict[str, Any] | None:
    raw = await redis_client.get(f"{PRO_ORDER_REDIS_PREFIX}{request_id}")
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


async def delete_pro_order(request_id: str) -> None:
    await redis_client.delete(f"{PRO_ORDER_REDIS_PREFIX}{request_id}")


async def offer_pro_analysis_order(
    message: Message,
    *,
    user_id: int,
    username: str | None,
    service: str,
    i18n: "TranslatorRunner | None" = None,
    lang_code: str | None = None,
    file_path: str | None = None,
    s3_key: str | None = None,
    file_name: str | None = None,
) -> str | None:
    """Отправляет пользователю кнопку заказа. Возвращает request_id или None."""
    i18n = i18n or _get_i18n(lang_code)
    try:
        request_id = await create_pro_order(
            user_id=user_id,
            username=username,
            service=service,
            file_path=file_path,
            s3_key=s3_key,
            file_name=file_name,
        )
    except Exception as e:
        logger.error(f"create_pro_order failed: {e}")
        return None

    await safe_answer(
        message,
        i18n.pro.analysis.ask(),
        reply_markup=get_pro_analysis_order_kb(request_id, i18n),
    )
    return request_id


async def _resolve_admin_ids(session: AsyncSession) -> list[int]:
    admin_ids: set[int] = set(settings.ROOT_ADMIN_IDS or [])
    try:
        admins = await UserDAO(session).find_all(
            filters=SUser(role=User.Role.ADMIN.value)
        )
        for admin in admins or []:
            if getattr(admin, "id", None) is not None:
                admin_ids.add(int(admin.id))
    except Exception as e:
        logger.error(f"Failed to load admin users for pro order: {e}")
    return sorted(admin_ids)


async def _resolve_local_mat(order: dict[str, Any]) -> tuple[str, bool]:
    """
    Возвращает (local_path, is_temp).
    is_temp=True — файл нужно удалить после отправки.
    """
    file_path = order.get("file_path")
    if file_path and os.path.isfile(file_path):
        return file_path, False

    s3_key = order.get("s3_key")
    if s3_key:
        fd, temp_path = tempfile.mkstemp(suffix=".mat")
        os.close(fd)
        try:
            s3 = HintS3Storage.from_settings()
            await asyncio.to_thread(s3.download_file, s3_key, temp_path)
            return temp_path, True
        except Exception:
            if os.path.isfile(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
            raise

    raise FileNotFoundError("Файл матча для заказа не найден")


def _build_admin_caption(order: dict[str, Any], i18n: "TranslatorRunner") -> str:
    user_id = order.get("user_id")
    username = order.get("username")
    service = order.get("service") or ""
    username_line = f"@{username}" if username else "—"
    # Сначала резолвим service_label: иначе admin_caption + kwargs склеят ключ.
    service_label = _service_label(i18n, service)
    return i18n.pro.analysis.admin_caption(
        service=service_label,
        user_id=user_id,
        username=username_line,
    )


async def fulfill_pro_order(
    bot: Bot,
    session: AsyncSession,
    order: dict[str, Any],
    *,
    i18n: "TranslatorRunner | None" = None,
) -> int:
    """
    Отправляет .mat админам с кнопкой «Ответить».
    Возвращает число успешных отправок.
    """
    # Подписи админам — на русском по умолчанию
    i18n = i18n or _get_i18n("ru")
    local_path, is_temp = await _resolve_local_mat(order)
    admin_ids = await _resolve_admin_ids(session)
    if not admin_ids:
        raise RuntimeError("Не найдены администраторы для отправки заказа")

    file_name = order.get("file_name") or os.path.basename(local_path) or "match.mat"
    if not str(file_name).lower().endswith(".mat"):
        file_name = f"{file_name}.mat"

    caption = _build_admin_caption(order, i18n)
    reply_kb = get_pro_analysis_admin_reply_kb(int(order["user_id"]), i18n)
    sent = 0
    try:
        for admin_id in admin_ids:
            try:
                await bot.send_document(
                    chat_id=admin_id,
                    document=FSInputFile(local_path, filename=file_name),
                    caption=caption,
                    parse_mode="HTML",
                    reply_markup=reply_kb,
                )
                sent += 1
            except Exception as e:
                logger.error(
                    f"Failed to send pro order to admin {admin_id}: {e}"
                )
    finally:
        if is_temp and os.path.isfile(local_path):
            try:
                os.remove(local_path)
            except OSError:
                pass

    if sent == 0:
        raise RuntimeError("Не удалось отправить заказ ни одному админу")
    return sent
