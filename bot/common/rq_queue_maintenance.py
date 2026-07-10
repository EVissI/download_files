"""Обслуживание очередей RQ: очистка реестров воркеров и мониторинг живых обработчиков."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from redis import Redis
from rq import Queue, Worker
from rq import worker_registration
from rq.defaults import DEFAULT_WORKER_TTL
from rq.registry import StartedJobRegistry, clean_registries
from rq.utils import utcparse

from bot.config import settings

HINT_QUEUE_NAMES = ("backgammon_analysis", "backgammon_batch_analysis")
WORKER_COUNT_CACHE_KEY = "cache:worker_count"
# Запас поверх worker TTL (420 с): heartbeat + job_monitoring_interval.
WORKER_ALIVE_GRACE_SECONDS = 90

QUEUE_TITLES = {
    "backgammon_analysis": "Одиночные игры",
    "backgammon_batch_analysis": "Пакеты игр",
}


@dataclass
class LiveWorkerStats:
    alive_count: int
    total_waiting: int
    total_active: int
    registry_before: int
    registry_after: int
    stale_removed_from_registry: int
    per_queue: dict[str, dict[str, int]] = field(default_factory=dict)
    workers: list[dict] = field(default_factory=list)


def _redis_conn(redis_conn: Redis | None) -> Redis:
    return redis_conn or Redis.from_url(settings.REDIS_URL, decode_responses=False)


def _hint_queue_set() -> set[str]:
    return set(HINT_QUEUE_NAMES)


def _collect_registry_keys(redis_conn: Redis) -> set[str]:
    keys: set[str] = set()
    for qname in HINT_QUEUE_NAMES:
        queue = Queue(qname, connection=redis_conn)
        keys.update(Worker.all_keys(queue=queue))
    return keys


def _worker_serves_hint_queues(worker: Worker) -> bool:
    try:
        names = set(worker.queue_names())
    except Exception:
        return False
    return bool(names & _hint_queue_set())


def _parse_rq_datetime(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = utcparse(value)
        except Exception:
            return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _is_worker_alive(worker: Worker) -> bool:
    if not worker.connection.exists(worker.key):
        return False

    worker.refresh()
    raw = worker.connection.hgetall(worker.key)
    if not raw:
        return False

    heartbeat = _parse_rq_datetime(worker.last_heartbeat)
    birth = _parse_rq_datetime(worker.birth_date)
    reference = heartbeat or birth
    if reference is None:
        return False

    ttl = getattr(worker, "worker_ttl", None) or DEFAULT_WORKER_TTL
    max_age = timedelta(seconds=int(ttl) + WORKER_ALIVE_GRACE_SECONDS)
    return datetime.now(timezone.utc) - reference <= max_age


def _purge_worker_keys_from_registries(redis_conn: Redis, worker_keys: set[str]) -> int:
    if not worker_keys:
        return 0

    keys = list(worker_keys)
    with redis_conn.pipeline() as pipeline:
        for key in keys:
            pipeline.srem("rq:workers", key)
            for qname in HINT_QUEUE_NAMES:
                pipeline.srem(f"rq:workers:{qname}", key)
        pipeline.execute()
    return len(keys)


def _serialize_worker(worker: Worker) -> dict:
    worker.refresh()
    hb = _parse_rq_datetime(worker.last_heartbeat)
    return {
        "name": worker.name,
        "hostname": worker.hostname or "—",
        "pid": worker.pid or "—",
        "state": worker.get_state(),
        "queues": ", ".join(worker.queue_names()) if worker.queue_names() else "—",
        "last_heartbeat": hb.strftime("%d.%m.%Y %H:%M:%S UTC") if hb else "—",
    }


def get_live_worker_stats(
    redis_conn: Redis | None = None,
    *,
    cleanup_registry: bool = False,
    include_worker_details: bool = False,
) -> LiveWorkerStats:
    """
    Возвращает актуальное число живых RQ-воркеров для очередей hint/batch.

    Живой воркер: ключ существует в Redis, есть heartbeat/birth и он не старше TTL+grace.
    Уникальные воркеры собираются по объединению реестров обеих очередей (без двойного счёта).
    """
    redis_conn = _redis_conn(redis_conn)
    registry_before = len(_collect_registry_keys(redis_conn))

    if cleanup_registry:
        redis_conn.delete(WORKER_COUNT_CACHE_KEY)
        for qname in HINT_QUEUE_NAMES:
            worker_registration.clean_worker_registry(Queue(qname, connection=redis_conn))

    registry_keys = _collect_registry_keys(redis_conn)
    alive_workers: dict[str, Worker] = {}
    stale_keys: set[str] = set()

    for key in registry_keys:
        worker = Worker.find_by_key(key, connection=redis_conn)
        if worker is None:
            stale_keys.add(key)
            continue
        if not _worker_serves_hint_queues(worker):
            stale_keys.add(key)
            continue
        if _is_worker_alive(worker):
            alive_workers[key] = worker
        else:
            stale_keys.add(key)

    stale_removed = 0
    if stale_keys:
        stale_removed = _purge_worker_keys_from_registries(redis_conn, stale_keys)

    registry_after = len(_collect_registry_keys(redis_conn))

    per_queue: dict[str, dict[str, int]] = {}
    total_waiting = 0
    total_active = 0
    for qname in HINT_QUEUE_NAMES:
        queue = Queue(qname, connection=redis_conn)
        registry = StartedJobRegistry(queue=queue)
        waiting = int(queue.count)
        active = len(registry)
        total_waiting += waiting
        total_active += active
        per_queue[qname] = {
            "waiting": waiting,
            "active": active,
            "registered_workers": len(Worker.all_keys(queue=queue)),
        }

    workers_details: list[dict] = []
    if include_worker_details:
        workers_details = [_serialize_worker(w) for w in alive_workers.values()]

    return LiveWorkerStats(
        alive_count=len(alive_workers),
        total_waiting=total_waiting,
        total_active=total_active,
        registry_before=registry_before,
        registry_after=registry_after,
        stale_removed_from_registry=stale_removed,
        per_queue=per_queue,
        workers=workers_details,
    )


def get_live_worker_count(redis_conn: Redis | None = None, *, cleanup_registry: bool = False) -> int:
    return get_live_worker_stats(
        redis_conn, cleanup_registry=cleanup_registry
    ).alive_count


def cleanup_rq_queues(redis_conn: Redis | None = None) -> dict:
    """
    Удаляет кэш числа воркеров, чистит реестры RQ и убирает «мёртвые» записи воркеров.
    """
    redis_conn = _redis_conn(redis_conn)

    stats_before = get_live_worker_stats(redis_conn, cleanup_registry=False)
    cache_deleted = bool(redis_conn.delete(WORKER_COUNT_CACHE_KEY))

    per_queue_cleanup: dict[str, dict[str, int]] = {}
    for qname in HINT_QUEUE_NAMES:
        queue = Queue(qname, connection=redis_conn)
        before = len(Worker.all_keys(queue=queue))
        worker_registration.clean_worker_registry(queue)
        clean_registries(queue)
        after = len(Worker.all_keys(queue=queue))
        per_queue_cleanup[qname] = {"before": before, "after": after}

    stats_after = get_live_worker_stats(redis_conn, cleanup_registry=False)

    return {
        "cache_deleted": cache_deleted,
        "workers_before_global": stats_before.registry_before,
        "workers_after_global": stats_after.registry_after,
        "alive_before": stats_before.alive_count,
        "alive_after": stats_after.alive_count,
        "stale_removed_from_registry": stats_after.stale_removed_from_registry,
        "per_queue": per_queue_cleanup,
        "per_queue_live": stats_after.per_queue,
    }


def periodic_rq_registry_cleanup() -> None:
    """Периодическая очистка реестров RQ (APScheduler, sync)."""
    redis_conn = _redis_conn(None)
    cleanup_rq_queues(redis_conn)
