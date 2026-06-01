"""Состояние hint-задач в Redis (активные job, статусы батча)."""

from __future__ import annotations

import json
from typing import Any

from loguru import logger

from bot.db.redis import sync_redis_client

BATCH_FILES_KEY = "batch_files:{batch_id}"


def can_enqueue_job(user_id: int) -> bool:
    active_jobs = sync_redis_client.smembers(f"user_active_jobs:{user_id}")
    return len(active_jobs) == 0


def add_active_job(user_id: int, job_id: str) -> None:
    sync_redis_client.sadd(f"user_active_jobs:{user_id}", job_id)
    sync_redis_client.expire(f"user_active_jobs:{user_id}", 3600)
    logger.info("Added active job: user_id={}, job_id={}", user_id, job_id)


def remove_active_job(user_id: int, job_id: str) -> None:
    sync_redis_client.srem(f"user_active_jobs:{user_id}", job_id)
    logger.info("Removed active job: user_id={}, job_id={}", user_id, job_id)


def publish_batch_file_ready(batch_id: str, file_index: int, payload: dict[str, Any]) -> None:
    """Воркер публикует готовность файла; бот читает и шлёт сообщения в Telegram."""
    key = BATCH_FILES_KEY.format(batch_id=batch_id)
    sync_redis_client.hset(key, str(file_index), json.dumps(payload, ensure_ascii=False))
    sync_redis_client.expire(key, 3600)


def get_batch_file_statuses(batch_id: str) -> dict[str, str]:
    key = BATCH_FILES_KEY.format(batch_id=batch_id)
    raw = sync_redis_client.hgetall(key)
    if not raw:
        return {}
    if isinstance(next(iter(raw.keys()), ""), bytes):
        return {k.decode(): v.decode() for k, v in raw.items()}
    return dict(raw)
