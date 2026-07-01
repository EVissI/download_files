"""AiohttpSession с динамическим failover прокси во время polling."""

from __future__ import annotations

import asyncio
import time
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
    CONSECUTIVE_FAILURES_TO_DEACTIVATE,
    is_proxy_url_active_sync,
    record_proxy_connection_failure_sync,
    record_proxy_connection_success_sync,
    select_next_active_proxy_url_sync,
)
from bot.common.telegram_proxy_config import (
    clear_telegram_proxy_cache,
    get_effective_telegram_proxies,
)

_last_working_proxy_url: str | None = None
_ACTIVE_PROXIES_CHECK_INTERVAL_SECONDS = 5.0


class NoActiveTelegramProxyError(RuntimeError):
    """В БД нет доступных активных прокси."""


def _pick_initial_proxy_url(*, refresh: bool = True) -> str | None:
    proxies = get_effective_telegram_proxies(refresh=refresh)
    for raw_url in proxies:
        proxy_url = normalize_proxy_url(raw_url)
        if proxy_url and is_valid_proxy_url(proxy_url):
            return proxy_url
    return None


def prepare_bot_session_proxy(session: AiohttpSession) -> str | None:
    """Инициализация прокси при старте."""
    global _last_working_proxy_url

    if not isinstance(session, FailoverAiohttpSession):
        return None

    proxy_url = _last_working_proxy_url or _pick_initial_proxy_url(refresh=True)
    if not proxy_url:
        return None

    session.prepare_proxy(proxy_url)
    return proxy_url


class FailoverAiohttpSession(AiohttpSession):
    """Текущий прокси для всех запросов; при 3 ошибках подряд — switch."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._state_lock = asyncio.Lock()
        self._active_proxy_url: str | None = None
        self._consecutive_failures = 0
        self._last_active_check_at = 0.0

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

    async def _ensure_usable_current_proxy(self, *, force_refresh: bool = False) -> str:
        """Проверяет активность текущего прокси в БД; при необходимости переключает."""
        global _last_working_proxy_url

        now = time.monotonic()
        need_refresh = (
            force_refresh
            or self._active_proxy_url is None
            or now - self._last_active_check_at >= _ACTIVE_PROXIES_CHECK_INTERVAL_SECONDS
        )

        current = (
            normalize_proxy_url(self._active_proxy_url or "")
            if self._active_proxy_url
            else None
        )

        if need_refresh:
            self._last_active_check_at = now
            if current and is_proxy_url_active_sync(current):
                return current

            clear_telegram_proxy_cache()
            next_url = select_next_active_proxy_url_sync(exclude_url=current)
            if not next_url:
                self._active_proxy_url = None
                _last_working_proxy_url = None
                raise NoActiveTelegramProxyError(
                    "No active Telegram proxies configured in DB"
                )

            if current and current != next_url:
                logger.warning(
                    "Current telegram proxy inactive in DB ({}), switching to {}",
                    mask_proxy_url(current),
                    mask_proxy_url(next_url),
                )
            elif not current:
                logger.info(
                    "Telegram proxy selected: {}",
                    mask_proxy_url(next_url),
                )

            await self._set_proxy_if_needed(next_url)
            self._consecutive_failures = 0
            _last_working_proxy_url = next_url
            return next_url

        if not current:
            return await self._ensure_usable_current_proxy(force_refresh=True)

        return current

    async def _switch_to_next_proxy(self, *, failed_proxy: str) -> str | None:
        global _last_working_proxy_url

        clear_telegram_proxy_cache()
        next_url = select_next_active_proxy_url_sync(exclude_url=failed_proxy)
        if not next_url:
            logger.error(
                "No backup telegram proxy after failures on {}",
                mask_proxy_url(failed_proxy),
            )
            self._active_proxy_url = None
            _last_working_proxy_url = None
            return None

        logger.warning(
            "Switching telegram proxy: {} -> {}",
            mask_proxy_url(failed_proxy),
            mask_proxy_url(next_url),
        )
        await self._set_proxy_if_needed(next_url)
        self._consecutive_failures = 0
        _last_working_proxy_url = next_url
        return next_url

    async def make_request(
        self,
        bot,
        method: TelegramMethod[TelegramType],
        timeout: Optional[int] = None,
    ) -> TelegramType:
        global _last_working_proxy_url

        last_error: TelegramNetworkError | None = None
        excluded_proxies: set[str] = set()

        while True:
            try:
                async with self._state_lock:
                    proxy_url = await self._ensure_usable_current_proxy(
                        force_refresh=bool(excluded_proxies),
                    )
            except NoActiveTelegramProxyError:
                if last_error is not None:
                    raise last_error
                raise TelegramNetworkError(
                    method=method,
                    message="No active Telegram proxies configured in DB",
                )

            if proxy_url in excluded_proxies:
                break

            await self._set_proxy_if_needed(proxy_url)

            switched_proxy = False
            for attempt in range(1, CONSECUTIVE_FAILURES_TO_DEACTIVATE + 1):
                try:
                    result = await super().make_request(bot, method, timeout=timeout)
                    async with self._state_lock:
                        if self._active_proxy_url == proxy_url:
                            self._consecutive_failures = 0
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
                    excluded_proxies.add(proxy_url)
                    switched_proxy = True
                    break
                except Exception as exc:
                    if not is_proxy_or_network_error(exc):
                        raise
                    last_error = self._as_network_error(method, exc)
                    logger.warning(
                        "Telegram proxy error ({}/{}): {} — {}",
                        attempt,
                        CONSECUTIVE_FAILURES_TO_DEACTIVATE,
                        mask_proxy_url(proxy_url),
                        exc,
                    )

                    async with self._state_lock:
                        if self._active_proxy_url != proxy_url:
                            switched_proxy = True
                            break

                        self._consecutive_failures += 1
                        deactivated = record_proxy_connection_failure_sync(proxy_url)

                        if (
                            self._consecutive_failures
                            >= CONSECUTIVE_FAILURES_TO_DEACTIVATE
                            or deactivated
                        ):
                            excluded_proxies.add(proxy_url)
                            next_proxy = await self._switch_to_next_proxy(
                                failed_proxy=proxy_url,
                            )
                            switched_proxy = True
                            if next_proxy is None:
                                raise last_error
                            break

            if switched_proxy:
                continue

            if last_error is not None:
                raise last_error

        if last_error is not None:
            raise last_error
        raise TelegramNetworkError(
            method=method,
            message="All Telegram proxies are unavailable",
        )
