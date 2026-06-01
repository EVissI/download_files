"""Единый TELEGRAM_PROXY: задаётся в .env основного бота, воркеры читают из Redis."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from loguru import logger

from bot.config import settings

if TYPE_CHECKING:
    from redis import Redis

TELEGRAM_PROXY_REDIS_KEY = "config:telegram_proxy"

_UNSET = object()
_redis_proxy_cache: object = _UNSET


def get_effective_telegram_proxy(
    *,
    redis: Redis | None = None,
    refresh: bool = False,
) -> Optional[str]:
    """
    Прокси для Telegram API.
    1) TELEGRAM_PROXY в локальном .env (переопределение)
    2) ключ config:telegram_proxy в Redis (публикует основной бот при старте)
    """
    if settings.TELEGRAM_PROXY:
        return settings.TELEGRAM_PROXY

    global _redis_proxy_cache
    if not refresh and _redis_proxy_cache is not _UNSET:
        return _redis_proxy_cache or None

    client = redis
    if client is None:
        from bot.db.redis import sync_redis_client

        client = sync_redis_client

    try:
        value = client.get(TELEGRAM_PROXY_REDIS_KEY)
        _redis_proxy_cache = value or ""
    except Exception as e:
        logger.warning("Failed to load Telegram proxy from Redis: {}", e)
        _redis_proxy_cache = ""
        return None

    return value or None


def telegram_proxy_source(*, redis: Redis | None = None) -> str:
    if settings.TELEGRAM_PROXY:
        return "env"
    if get_effective_telegram_proxy(redis=redis):
        return "redis"
    return "none"


def telegram_requests_proxies(
    *, redis: Redis | None = None, refresh: bool = False
) -> Optional[dict[str, str]]:
    proxy = get_effective_telegram_proxy(redis=redis, refresh=refresh)
    if not proxy:
        return None
    return {"http": proxy, "https": proxy}


async def publish_telegram_proxy_to_redis() -> None:
    """Вызывается при старте основного бота — воркеры подхватят прокси из Redis."""
    from bot.db.redis import redis_client

    await redis_client.connect()
    if settings.TELEGRAM_PROXY:
        await redis_client.set(TELEGRAM_PROXY_REDIS_KEY, settings.TELEGRAM_PROXY)
        logger.info("Telegram proxy published to Redis for workers")
    else:
        await redis_client.delete(TELEGRAM_PROXY_REDIS_KEY)
        _clear_redis_proxy_cache()


def _clear_redis_proxy_cache() -> None:
    global _redis_proxy_cache
    _redis_proxy_cache = _UNSET
