"""Список TELEGRAM_PROXY: БД (FAB) с in-memory кэшем, env — локальное переопределение."""

from __future__ import annotations

import time
from typing import Optional

from loguru import logger

from bot.common.proxy_utils import mask_proxy_url
from bot.config import settings

_CACHE_TTL_SECONDS = 30
_UNSET = object()
_proxies_cache: object = _UNSET
_cache_loaded_at: float = 0.0


def get_env_telegram_proxy() -> str | None:
    value = (settings.TELEGRAM_PROXY or "").strip()
    return value or None


def clear_telegram_proxy_cache() -> None:
    global _proxies_cache, _cache_loaded_at
    _proxies_cache = _UNSET
    _cache_loaded_at = 0.0


def warm_telegram_proxy_cache() -> list[str]:
    """Предзагрузка списка прокси из БД (например, при старте бота)."""
    return get_effective_telegram_proxies(refresh=True)


def log_telegram_proxy_config() -> list[str]:
    """Логирует источник и список прокси при старте."""
    env_proxy = get_env_telegram_proxy()
    if env_proxy:
        logger.warning(
            "TELEGRAM_PROXY из env переопределяет БД: {}",
            mask_proxy_url(env_proxy),
        )
        return [env_proxy]

    urls = get_effective_telegram_proxies(refresh=True)
    if urls:
        logger.info(
            "Telegram proxies from DB (count={}): {}",
            len(urls),
            ", ".join(mask_proxy_url(u) for u in urls),
        )
    else:
        logger.info("Telegram proxies: none (direct connection to api.telegram.org)")
    return urls


def get_effective_telegram_proxies(*, refresh: bool = False) -> list[str]:
    """
    Список прокси для Telegram API (порядок = приоритет failover).
    1) TELEGRAM_PROXY в локальном .env (переопределение, один URL)
    2) активные записи telegram_proxies в PostgreSQL
    """
    env_proxy = get_env_telegram_proxy()
    if env_proxy:
        return [env_proxy]

    global _proxies_cache, _cache_loaded_at
    if not refresh and _proxies_cache is not _UNSET:
        if time.monotonic() - _cache_loaded_at < _CACHE_TTL_SECONDS:
            return list(_proxies_cache or [])

    from bot.common.service.telegram_proxy_service import fetch_active_proxy_urls_sync

    try:
        urls = fetch_active_proxy_urls_sync()
        _proxies_cache = urls
        _cache_loaded_at = time.monotonic()
    except Exception as e:
        logger.warning("Failed to load Telegram proxies from DB: {}", e)
        _proxies_cache = []
        return []

    return list(_proxies_cache or [])


def get_effective_telegram_proxy(*, refresh: bool = False) -> Optional[str]:
    proxies = get_effective_telegram_proxies(refresh=refresh)
    return proxies[0] if proxies else None


def telegram_proxy_source() -> str:
    if get_env_telegram_proxy():
        return "env"
    if get_effective_telegram_proxies():
        return "db"
    return "none"


def telegram_requests_proxies(*, refresh: bool = False) -> Optional[dict[str, str]]:
    proxy = get_effective_telegram_proxy(refresh=refresh)
    if not proxy:
        return None
    return {"http": proxy, "https": proxy}
