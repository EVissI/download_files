"""Утилиты для прокси без зависимостей от БД и config."""

from __future__ import annotations

import asyncio
import re
from urllib.parse import urlparse, urlunparse

_VALID_PROXY_SCHEMES = frozenset({"http", "https", "socks4", "socks5", "socks5h"})


def normalize_proxy_url(url: str) -> str | None:
    """
    Нормализует URL прокси для aiohttp-socks.
    Без схемы добавляет socks5:// (user:pass@host:port).
    """
    raw = str(url or "").strip()
    if not raw:
        return None

    candidate = raw if "://" in raw else f"socks5://{raw}"
    parsed = urlparse(candidate)
    scheme = (parsed.scheme or "").strip().lower()
    if scheme not in _VALID_PROXY_SCHEMES:
        return None
    if not parsed.hostname:
        return None
    if parsed.port is None:
        return None
    return candidate


def is_valid_proxy_url(url: str) -> bool:
    return normalize_proxy_url(url) is not None


def mask_proxy_url(url: str) -> str:
    """Скрывает пароль в URL прокси для логов и уведомлений."""
    try:
        parsed = urlparse(url)
        if parsed.password:
            netloc = parsed.hostname or ""
            if parsed.username:
                netloc = f"{parsed.username}:***@{netloc}"
            if parsed.port:
                netloc = f"{netloc}:{parsed.port}"
            return urlunparse(
                (parsed.scheme, netloc, parsed.path, parsed.params, parsed.query, parsed.fragment)
            )
    except Exception:
        pass
    return re.sub(r":([^:@/]+)@", ":***@", url, count=1)


def is_proxy_or_network_error(exc: BaseException) -> bool:
    """Ошибки прокси/сети, в т.ч. ProxyError без обёртки aiogram."""
    from aiogram.exceptions import TelegramNetworkError

    if isinstance(exc, (TelegramNetworkError, asyncio.TimeoutError, ConnectionError, OSError)):
        return True

    name = type(exc).__name__
    if "Proxy" in name or "ClientConnector" in name or "ClientOSError" in name:
        return True

    try:
        from aiohttp import ClientError

        if isinstance(exc, ClientError):
            return True
    except ImportError:
        pass

    return False
