"""AiohttpSession с переключением на следующий прокси при сетевой ошибке."""

from __future__ import annotations

import asyncio
from typing import Optional

from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import TelegramNetworkError
from aiogram.methods.base import TelegramMethod
from aiogram.client.session.base import TelegramType
from loguru import logger

from bot.common.proxy_utils import (
    is_proxy_or_network_error,
    is_valid_proxy_url,
    mask_proxy_url,
    normalize_proxy_url,
)
from bot.common.service.telegram_proxy_service import (
    record_proxy_connection_failure_sync,
    record_proxy_connection_success_sync,
)
from bot.common.telegram_proxy_config import get_effective_telegram_proxies

_last_working_proxy_url: str | None = None


def _prioritize_proxies(urls: list[str]) -> list[str]:
    if not urls:
        return urls
    if _last_working_proxy_url and _last_working_proxy_url in urls:
        return [_last_working_proxy_url] + [
            url for url in urls if url != _last_working_proxy_url
        ]
    return list(urls)


def _next_proxy_to_try(proxies: list[str], tried: set[str]) -> str | None:
    for raw_url in proxies:
        proxy_url = normalize_proxy_url(raw_url)
        if not proxy_url or not is_valid_proxy_url(proxy_url):
            continue
        if proxy_url in tried:
            continue
        return proxy_url
    return None


def _pick_initial_proxy_url() -> str | None:
    proxies = _prioritize_proxies(get_effective_telegram_proxies(refresh=False))
    return _next_proxy_to_try(proxies, set())


def prepare_bot_session_proxy(session: AiohttpSession) -> str | None:
    """Синхронная инициализация прокси при старте (без лишних запросов в hot path)."""
    global _last_working_proxy_url

    if not isinstance(session, FailoverAiohttpSession):
        return None

    proxy_url = _last_working_proxy_url or _pick_initial_proxy_url()
    if not proxy_url:
        return None

    session.prepare_proxy(proxy_url)
    return proxy_url


class FailoverAiohttpSession(AiohttpSession):
    """Пробует прокси по очереди из БД. Без прокси запросы не выполняются."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._failover_lock = asyncio.Lock()
        self._active_proxy_url: str | None = None

    def prepare_proxy(self, proxy_url: str) -> None:
        normalized = normalize_proxy_url(proxy_url)
        if not normalized:
            return
        self.proxy = normalized
        self._active_proxy_url = normalized

    @staticmethod
    def _as_network_error(
        method: TelegramMethod[TelegramType],
        exc: BaseException,
    ) -> TelegramNetworkError:
        if isinstance(exc, TelegramNetworkError):
            return exc
        return TelegramNetworkError(
            method=method,
            message=f"{type(exc).__name__}: {exc}",
        )

    async def _set_proxy_if_needed(self, proxy_url: str) -> None:
        if self._active_proxy_url == proxy_url:
            return
        self.proxy = proxy_url
        self._active_proxy_url = proxy_url

    async def make_request(
        self,
        bot,
        method: TelegramMethod[TelegramType],
        timeout: Optional[int] = None,
    ) -> TelegramType:
        proxy_url = self._active_proxy_url or _last_working_proxy_url
        if proxy_url:
            try:
                await self._set_proxy_if_needed(proxy_url)
                return await super().make_request(bot, method, timeout=timeout)
            except Exception as exc:
                if not is_proxy_or_network_error(exc):
                    raise
                return await self._failover_request(
                    bot,
                    method,
                    timeout,
                    failed_proxy=proxy_url,
                    initial_error=exc,
                )

        return await self._failover_request(bot, method, timeout)

    async def _failover_request(
        self,
        bot,
        method: TelegramMethod[TelegramType],
        timeout: Optional[int] = None,
        *,
        failed_proxy: str | None = None,
        initial_error: BaseException | None = None,
    ) -> TelegramType:
        global _last_working_proxy_url

        async with self._failover_lock:
            if (
                failed_proxy
                and self._active_proxy_url
                and self._active_proxy_url != failed_proxy
            ):
                try:
                    await self._set_proxy_if_needed(self._active_proxy_url)
                    return await super().make_request(bot, method, timeout=timeout)
                except Exception as exc:
                    if not is_proxy_or_network_error(exc):
                        raise
                    initial_error = exc
                    failed_proxy = self._active_proxy_url

            last_error = (
                self._as_network_error(method, initial_error)
                if initial_error is not None
                else None
            )
            tried: set[str] = set()
            if failed_proxy:
                normalized_failed = normalize_proxy_url(failed_proxy) or failed_proxy
                tried.add(normalized_failed)
                if _last_working_proxy_url == normalized_failed:
                    _last_working_proxy_url = None
                record_proxy_connection_failure_sync(normalized_failed)

            refresh_db = True
            proxies: list[str] = []

            while True:
                if refresh_db:
                    proxies = _prioritize_proxies(
                        get_effective_telegram_proxies(refresh=True)
                    )
                    refresh_db = False

                if not proxies:
                    raise TelegramNetworkError(
                        method=method,
                        message="No active Telegram proxies configured in DB",
                    )

                proxy_url = _next_proxy_to_try(proxies, tried)
                if proxy_url is None:
                    break

                tried.add(proxy_url)
                logger.info(
                    "Telegram proxy attempt {}/{}: {}",
                    len(tried),
                    len(proxies),
                    mask_proxy_url(proxy_url),
                )

                try:
                    await self._set_proxy_if_needed(proxy_url)
                    result = await super().make_request(bot, method, timeout=timeout)
                    record_proxy_connection_success_sync(proxy_url)
                    _last_working_proxy_url = proxy_url
                    return result
                except ValueError as exc:
                    logger.error(
                        "Invalid telegram proxy URL {}: {}",
                        mask_proxy_url(proxy_url),
                        exc,
                    )
                    last_error = self._as_network_error(method, exc)
                    if _last_working_proxy_url == proxy_url:
                        _last_working_proxy_url = None
                except Exception as exc:
                    if not is_proxy_or_network_error(exc):
                        raise
                    last_error = self._as_network_error(method, exc)
                    logger.warning(
                        "Telegram proxy failed ({}/{}): {} — {}",
                        len(tried),
                        len(proxies),
                        mask_proxy_url(proxy_url),
                        exc,
                    )
                    if _last_working_proxy_url == proxy_url:
                        _last_working_proxy_url = None
                    record_proxy_connection_failure_sync(proxy_url)
                    refresh_db = True

                remaining = _next_proxy_to_try(proxies, tried)
                if remaining:
                    logger.info(
                        "Switching to next telegram proxy: {}",
                        mask_proxy_url(remaining),
                    )
                elif len(proxies) == 1:
                    logger.error(
                        "Failover unavailable: only 1 active proxy in DB. "
                        "Add a second proxy in FAB for switching."
                    )

            if last_error is not None:
                raise last_error
            raise TelegramNetworkError(
                method=method,
                message="All Telegram proxies are unavailable",
            )
