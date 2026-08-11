"""Состояние hint-задач в Redis (активные job, статусы батча)."""

from __future__ import annotations

import json
from typing import Any

from loguru import logger

from bot.db.redis import sync_redis_client

BATCH_FILES_KEY = "batch_files:{batch_id}"
BATCH_DONE_FIELD = "__done__"

# Таймаут RQ: ~30 мин на файл, минимум 1 ч, максимум 12 ч
BATCH_TIMEOUT_PER_FILE_SEC = 1800
BATCH_TIMEOUT_MIN_SEC = 3600
BATCH_TIMEOUT_MAX_SEC = 43200


def calc_batch_job_timeout(total_files: int) -> int:
    """Таймаут RQ-задачи батча в секундах."""
    n = max(1, int(total_files))
    return min(
        max(n * BATCH_TIMEOUT_PER_FILE_SEC, BATCH_TIMEOUT_MIN_SEC),
        BATCH_TIMEOUT_MAX_SEC,
    )


def can_enqueue_job(user_id: int) -> bool:
    active_jobs = sync_redis_client.smembers(f"user_active_jobs:{user_id}")
    return len(active_jobs) == 0


def add_active_job(user_id: int, job_id: str, ttl: int = 3600) -> None:
    sync_redis_client.sadd(f"user_active_jobs:{user_id}", job_id)
    sync_redis_client.expire(f"user_active_jobs:{user_id}", max(ttl, 3600))
    logger.info("Added active job: user_id={}, job_id={}", user_id, job_id)


def remove_active_job(user_id: int, job_id: str) -> None:
    sync_redis_client.srem(f"user_active_jobs:{user_id}", job_id)
    logger.info("Removed active job: user_id={}, job_id={}", user_id, job_id)


def publish_batch_file_ready(
    batch_id: str,
    file_index: int,
    payload: dict[str, Any],
    ttl: int = 3600,
) -> None:
    """Воркер публикует готовность файла; бот читает и шлёт сообщения в Telegram."""
    key = BATCH_FILES_KEY.format(batch_id=batch_id)
    sync_redis_client.hset(key, str(file_index), json.dumps(payload, ensure_ascii=False))
    sync_redis_client.expire(key, max(ttl, 3600))


def publish_batch_completed(
    batch_id: str,
    total_files: int,
    ttl: int = 3600,
) -> None:
    """Маркер завершения батча (на случай гибели work-horse после обработки файлов)."""
    key = BATCH_FILES_KEY.format(batch_id=batch_id)
    sync_redis_client.hset(
        key,
        BATCH_DONE_FIELD,
        json.dumps({"status": "completed", "total_files": total_files}),
    )
    sync_redis_client.expire(key, max(ttl, 3600))


def get_batch_file_statuses(batch_id: str) -> dict[str, str]:
    key = BATCH_FILES_KEY.format(batch_id=batch_id)
    raw = sync_redis_client.hgetall(key)
    if not raw:
        return {}
    if isinstance(next(iter(raw.keys()), ""), bytes):
        return {k.decode(): v.decode() for k, v in raw.items()}
    return dict(raw)


def is_batch_effectively_done(batch_id: str, total_files: int) -> bool:
    """True, если воркер уже опубликовал все файлы или маркер завершения."""
    statuses = get_batch_file_statuses(batch_id)
    if BATCH_DONE_FIELD in statuses:
        return True
    file_statuses = {k: v for k, v in statuses.items() if k != BATCH_DONE_FIELD}
    return total_files > 0 and len(file_statuses) >= total_files
