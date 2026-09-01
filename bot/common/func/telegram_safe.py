"""Защита исходящих сообщений от flood-control Telegram."""

from __future__ import annotations

import asyncio
import time
from typing import Awaitable, Callable, TypeVar

from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramRetryAfter,
)
from aiogram.types import Message
from loguru import logger

from bot.db.redis import redis_client

T = TypeVar("T")

FLOOD_KEY_PREFIX = "tg_flood:"
BUSY_NOTICE_PREFIX = "tg_busy_notice:"
# Короткие лимиты ждём и повторяем; длинные (часы) — только пропускаем.
MAX_WAIT_RETRY = 5
BUSY_NOTICE_TTL = 20
SEND_GAP = 0.4
FLOOD_TTL_CAP = 86400

_last_send: dict[int, float] = {}
_chat_locks: dict[int, asyncio.Lock] = {}
_locks_guard = asyncio.Lock()
_busy_users: set[int] = set()
_busy_guard = asyncio.Lock()


async def _get_chat_lock(chat_id: int) -> asyncio.Lock:
    async with _locks_guard:
        lock = _chat_locks.get(chat_id)
        if lock is None:
            lock = asyncio.Lock()
            _chat_locks[chat_id] = lock
        return lock


async def flood_ttl(chat_id: int) -> int:
    try:
        ttl = await redis_client.ttl(f"{FLOOD_KEY_PREFIX}{chat_id}")
        return max(int(ttl or 0), 0)
    except Exception:
        return 0


async def is_flood_limited(chat_id: int) -> bool:
    return await flood_ttl(chat_id) > 0


async def mark_flood(chat_id: int | None, retry_after: int | float | None) -> None:
    if chat_id is None:
        return
    ttl = max(int(retry_after or 1), 1)
    ttl = min(ttl, FLOOD_TTL_CAP)
    try:
        await redis_client.set(f"{FLOOD_KEY_PREFIX}{chat_id}", str(ttl), expire=ttl)
    except Exception as exc:
        logger.warning("Не удалось сохранить flood cooldown для чата {}: {}", chat_id, exc)


async def should_send_busy_notice(chat_id: int) -> bool:
    """Не чаще одного «подождите» на чат за BUSY_NOTICE_TTL секунд."""
    key = f"{BUSY_NOTICE_PREFIX}{chat_id}"
    try:
        if await redis_client.get(key):
            return False
        await redis_client.set(key, "1", expire=BUSY_NOTICE_TTL)
        return True
    except Exception:
        return True


async def try_mark_user_busy(user_id: int) -> bool:
    async with _busy_guard:
        if user_id in _busy_users:
            return False
        _busy_users.add(user_id)
        return True


async def mark_user_free(user_id: int) -> None:
    async with _busy_guard:
        _busy_users.discard(user_id)


async def _pace(chat_id: int) -> None:
    last = _last_send.get(chat_id, 0.0)
    gap = SEND_GAP - (time.monotonic() - last)
    if gap > 0:
        await asyncio.sleep(gap)


def _touch(chat_id: int) -> None:
    _last_send[chat_id] = time.monotonic()


async def safe_call(
    chat_id: int | None,
    factory: Callable[[], Awaitable[T]],
) -> T | None:
    """
    Выполняет Telegram-вызов: пропускает чат под flood wait,
    для короткого retry_after ждёт и повторяет один раз.
    """
    if chat_id is not None and await is_flood_limited(chat_id):
        logger.warning(
            "Пропуск отправки в чат {}: flood wait ещё {}с",
            chat_id,
            await flood_ttl(chat_id),
        )
        return None

    lock = await _get_chat_lock(chat_id) if chat_id is not None else None
    if lock is not None:
        await lock.acquire()
    try:
        if chat_id is not None:
            await _pace(chat_id)
        try:
            result = await factory()
            if chat_id is not None:
                _touch(chat_id)
            return result
        except TelegramRetryAfter as exc:
            retry_after = int(getattr(exc, "retry_after", 1) or 1)
            await mark_flood(chat_id, retry_after)
            if retry_after <= MAX_WAIT_RETRY:
                logger.warning(
                    "Flood control chat={}, метод повторно через {}с",
                    chat_id,
                    retry_after,
                )
                await asyncio.sleep(retry_after)
                try:
                    result = await factory()
                    if chat_id is not None:
                        _touch(chat_id)
                    return result
                except TelegramRetryAfter as exc2:
                    await mark_flood(chat_id, getattr(exc2, "retry_after", retry_after))
                    logger.warning(
                        "Flood control не снят для чата {}: retry after {}с",
                        chat_id,
                        exc2.retry_after,
                    )
                    return None
            logger.warning(
                "Flood control exceeded chat={}: retry after {}с, отправка пропущена",
                chat_id,
                retry_after,
            )
            return None
        except TelegramForbiddenError:
            logger.warning("Бот заблокирован в чате {}", chat_id)
            return None
        except TelegramBadRequest as exc:
            logger.warning("Telegram bad request chat={}: {}", chat_id, exc)
            return None
    finally:
        if lock is not None:
            lock.release()


async def safe_answer(message: Message, text: str, **kwargs):
    chat_id = getattr(getattr(message, "chat", None), "id", None)

    async def _send():
        return await message.answer(text, **kwargs)

    return await safe_call(chat_id, _send)


async def safe_bot_send(bot, chat_id: int, text: str, **kwargs):
    async def _send():
        return await bot.send_message(chat_id, text, **kwargs)

    return await safe_call(chat_id, _send)


async def safe_edit_text(message: Message | None, text: str, **kwargs):
    if message is None:
        return None
    chat_id = getattr(getattr(message, "chat", None), "id", None)

    async def _send():
        return await message.edit_text(text, **kwargs)

    return await safe_call(chat_id, _send)
