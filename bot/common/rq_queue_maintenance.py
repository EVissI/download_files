"""Обслуживание очередей RQ: очистка реестров воркеров и кэша мониторинга."""

from __future__ import annotations

from redis import Redis
from rq import Queue, Worker
from rq import worker_registration
from rq.registry import clean_registries

from bot.config import settings

HINT_QUEUE_NAMES = ("backgammon_analysis", "backgammon_batch_analysis")
WORKER_COUNT_CACHE_KEY = "cache:worker_count"


def cleanup_rq_queues(redis_conn: Redis | None = None) -> dict:
    """
    Удаляет кэш числа воркеров и чистит реестры RQ:
    - worker_registration.clean_worker_registry — убирает «мёртвые» ключи из rq:workers*
    - clean_registries — Started/Finished/Failed/Deferred job registries
    """
    redis_conn = redis_conn or Redis.from_url(
        settings.REDIS_URL, decode_responses=False
    )

    cache_deleted = bool(redis_conn.delete(WORKER_COUNT_CACHE_KEY))
    workers_before_global = len(Worker.all(connection=redis_conn))

    per_queue: dict[str, dict[str, int]] = {}
    for qname in HINT_QUEUE_NAMES:
        queue = Queue(qname, connection=redis_conn)
        before = len(Worker.all(queue=queue))
        worker_registration.clean_worker_registry(queue)
        clean_registries(queue)
        after = len(Worker.all(queue=queue))
        per_queue[qname] = {"before": before, "after": after}

    workers_after_global = len(Worker.all(connection=redis_conn))

    return {
        "cache_deleted": cache_deleted,
        "workers_before_global": workers_before_global,
        "workers_after_global": workers_after_global,
        "per_queue": per_queue,
    }
