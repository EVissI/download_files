"""Утилиты для прокси без зависимостей от БД и config."""

from __future__ import annotations

import re
from urllib.parse import urlparse, urlunparse


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
