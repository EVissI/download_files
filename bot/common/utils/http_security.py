"""HTTP-защита FastAPI: сканеры секретов, заголовки, лимиты, безопасные id."""

from __future__ import annotations

import ipaddress
import re
from urllib.parse import unquote

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

_SENSITIVE_NAME_RE = re.compile(
    r"(?:"
    r"\.env(?:\.[^/]*)?"
    r"|\.git"
    r"|\.svn"
    r"|\.htaccess"
    r"|\.htpasswd"
    r"|docker-compose[^/]*"
    r"|id_rsa"
    r"|id_ed25519"
    r"|authorized_keys"
    r"|wp-admin"
    r"|wp-login\.php"
    r"|phpinfo"
    r"|web\.config"
    r"|application-\w+\.(?:yml|yaml|properties)"
    r"|credentials"
    r"|backup[^/]*\.(?:sql|zip|tar|gz|rar)"
    r"|dump\.sql"
    r")",
    re.IGNORECASE,
)

_SAFE_PUBLIC_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,80}$")
_SAFE_GAME_NUM_RE = re.compile(r"^[0-9]{1,8}$")

_PROBE_LOG_TTL_SEC = 300


def _is_proxy_peer(host: str) -> bool:
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return bool(ip.is_private or ip.is_loopback)


def client_ip(request: Request) -> str:
    peer = request.client.host if request.client and request.client.host else ""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded and _is_proxy_peer(peer):
        return forwarded.split(",")[0].strip() or peer or "unknown"
    return peer or "unknown"


def has_forwarded_client_ip(request: Request) -> bool:
    peer = request.client.host if request.client and request.client.host else ""
    return bool(request.headers.get("x-forwarded-for") and _is_proxy_peer(peer))


def cookies_should_be_secure(request: Request) -> bool:
    proto = (
        request.headers.get("x-forwarded-proto") or request.url.scheme or ""
    ).split(",")[0].strip().lower()
    return proto == "https"


def is_secret_probe(path: str) -> bool:
    raw = unquote(path or "").replace("\\", "/")
    if ".." in raw:
        return True
    for part in raw.split("/"):
        name = part.strip()
        if not name or name in (".",):
            continue
        if name.startswith(".") or _SENSITIVE_NAME_RE.fullmatch(name):
            return True
        if _SENSITIVE_NAME_RE.search(name):
            return True
    return False


def require_public_id(value: str | None, *, name: str = "id") -> str:
    raw = (value or "").strip()
    if not _SAFE_PUBLIC_ID_RE.fullmatch(raw):
        raise HTTPException(status_code=404, detail=f"{name} not found")
    return raw


def require_game_num(value: str | None) -> str | None:
    if value is None or str(value).strip() == "":
        return None
    raw = str(value).strip()
    if not _SAFE_GAME_NUM_RE.fullmatch(raw):
        raise HTTPException(status_code=404, detail="game not found")
    return raw


async def rate_limit_blocked(key: str, limit: int) -> bool:
    from bot.db.redis import redis_client

    current = await redis_client.get(key)
    return current is not None and int(current) >= limit


async def rate_limit_hit(key: str, window_sec: int) -> int:
    from bot.db.redis import redis_client

    count = await redis_client.incr(key)
    if int(count) == 1:
        await redis_client.expire(key, window_sec)
    return int(count)


async def rate_limit_exceeded(key: str, limit: int, window_sec: int) -> bool:
    return await rate_limit_hit(key, window_sec) > limit


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path or ""
        if is_secret_probe(path):
            await _log_probe_throttled(request, path)
            return Response(status_code=404)
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy", "camera=(), microphone=(), geolocation=()"
        )
        # Mini App в web.telegram.org открывается во iframe — глобальный
        # X-Frame-Options: SAMEORIGIN его сломает. Только админка.
        if path.startswith("/admin"):
            response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        if cookies_should_be_secure(request):
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        return response


async def _log_probe_throttled(request: Request, path: str) -> None:
    from loguru import logger

    ip = client_ip(request)
    key = f"sec_probe_log:{ip}"
    try:
        from bot.db.redis import redis_client

        first = await redis_client.set_nx(key, "1", expire=_PROBE_LOG_TTL_SEC)
        if first:
            logger.warning("Blocked secret-file probe from {} path={}", ip, path)
    except Exception:
        logger.warning("Blocked secret-file probe from {} path={}", ip, path)
