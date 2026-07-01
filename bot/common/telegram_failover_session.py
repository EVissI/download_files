"""AiohttpSession с переключением на следующий прокси при сетевой ошибке."""

from __future__ import annotations

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


class FailoverAiohttpSession(AiohttpSession):
    """Пробует прокси по очереди из БД. Без прокси запросы не выполняются."""

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

    async def _switch_proxy(self, proxy_url: str) -> None:
        await self.close()
        self.proxy = proxy_url
        self._should_reset_connector = True

    async def make_request(
        self,
        bot,
        method: TelegramMethod[TelegramType],
        timeout: Optional[int] = None,
    ) -> TelegramType:
        global _last_working_proxy_url

        last_error: TelegramNetworkError | None = None
        tried: set[str] = set()

        while True:
            proxies = _prioritize_proxies(get_effective_telegram_proxies(refresh=True))
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
                await self._switch_proxy(proxy_url)
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
                await self.close()
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
                await self.close()
                if _last_working_proxy_url == proxy_url:
                    _last_working_proxy_url = None
                record_proxy_connection_failure_sync(proxy_url)

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
