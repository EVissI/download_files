"""Список прокси Telegram: только БД (FAB) с in-memory кэшем."""

from __future__ import annotations

import os
import time
from typing import Optional

from loguru import logger

from bot.common.proxy_utils import mask_proxy_url

_CACHE_TTL_SECONDS = 5
_UNSET = object()
_proxies_cache: object = _UNSET
_cache_loaded_at: float = 0.0


def clear_telegram_proxy_cache() -> None:
    global _proxies_cache, _cache_loaded_at
    _proxies_cache = _UNSET
    _cache_loaded_at = 0.0


def warm_telegram_proxy_cache() -> list[str]:
    """Предзагрузка списка прокси из БД (например, при старте бота)."""
    return get_effective_telegram_proxies(refresh=True)


def log_telegram_proxy_config() -> list[str]:
    """Логирует список прокси при старте."""
    legacy_env = (os.getenv("TELEGRAM_PROXY") or "").strip()
    if legacy_env:
        logger.warning(
            "TELEGRAM_PROXY в окружении ({}) игнорируется — прокси берутся только из БД (FAB)",
            mask_proxy_url(legacy_env),
        )

    urls = get_effective_telegram_proxies(refresh=True)
    if urls:
        logger.info(
            "Telegram proxies from DB (count={}): {}",
            len(urls),
            ", ".join(mask_proxy_url(u) for u in urls),
        )
    else:
        logger.warning("Telegram proxies: none configured in DB (bot requires proxy)")
    return urls


def get_effective_telegram_proxies(*, refresh: bool = False) -> list[str]:
    """Активные прокси из telegram_proxies, порядок = приоритет failover."""
    global _proxies_cache, _cache_loaded_at
    if not refresh and _proxies_cache is not _UNSET:
        if time.monotonic() - _cache_loaded_at < _CACHE_TTL_SECONDS:
            return list(_proxies_cache or [])

    from bot.common.service.telegram_proxy_service import fetch_active_proxy_urls_sync

    try:
        urls = fetch_active_proxy_urls_sync()
        _proxies_cache = urls
        _cache_loaded_at = time.monotonic()
        if urls:
            logger.debug(
                "Loaded telegram proxies from DB (count={}): {}",
                len(urls),
                ", ".join(mask_proxy_url(u) for u in urls),
            )
    except Exception as e:
        logger.warning("Failed to load Telegram proxies from DB: {}", e)
        _proxies_cache = []
        return []

    return list(_proxies_cache or [])


def get_effective_telegram_proxy(*, refresh: bool = False) -> Optional[str]:
    proxies = get_effective_telegram_proxies(refresh=refresh)
    return proxies[0] if proxies else None


def telegram_proxy_source() -> str:
    if get_effective_telegram_proxies():
        return "db"
    return "none"


def telegram_requests_proxies(*, refresh: bool = False) -> Optional[dict[str, str]]:
    proxy = get_effective_telegram_proxy(refresh=refresh)
    if not proxy:
        return None
    return {"http": proxy, "https": proxy}
