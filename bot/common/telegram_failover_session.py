"""AiohttpSession с переключением на следующий прокси при сетевой ошибке."""

from __future__ import annotations

import ssl
from typing import Optional

import certifi
from aiohttp import TCPConnector
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import TelegramNetworkError
from aiogram.methods.base import TelegramMethod
from aiogram.client.session.base import TelegramType
from loguru import logger

from bot.common.proxy_utils import is_proxy_or_network_error
from bot.common.service.telegram_proxy_service import (
    record_proxy_connection_failure_sync,
    record_proxy_connection_success_sync,
)
from bot.common.telegram_proxy_config import (
    clear_telegram_proxy_cache,
    get_effective_telegram_proxies,
)


class FailoverAiohttpSession(AiohttpSession):
    """Пробует прокси по очереди из БД; если все недоступны — прямое подключение."""

    async def _reset_direct_connector(self) -> None:
        limit = self._connector_init.get("limit", 100)
        self._connector_type = TCPConnector
        self._connector_init = {
            "ssl": ssl.create_default_context(cafile=certifi.where()),
            "limit": limit,
            "ttl_dns_cache": 3600,
        }
        self._proxy = None
        self._should_reset_connector = True
        await self.close()

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

    async def _request_via_proxies(
        self,
        bot,
        method: TelegramMethod[TelegramType],
        timeout: Optional[int],
        *,
        allow_direct_fallback: bool,
    ) -> TelegramType:
        proxies = get_effective_telegram_proxies()
        if not proxies:
            if allow_direct_fallback:
                await self._reset_direct_connector()
            return await super().make_request(bot, method, timeout=timeout)

        last_error: TelegramNetworkError | None = None
        index = 0
        while index < len(proxies):
            proxy_url = proxies[index]
            try:
                if self.proxy != proxy_url:
                    self.proxy = proxy_url
                result = await super().make_request(bot, method, timeout=timeout)
                record_proxy_connection_success_sync(proxy_url)
                return result
            except Exception as exc:
                if not is_proxy_or_network_error(exc):
                    raise
                last_error = self._as_network_error(method, exc)
                self._should_reset_connector = True
                deactivated = record_proxy_connection_failure_sync(proxy_url)
                if deactivated:
                    clear_telegram_proxy_cache()
                    proxies = get_effective_telegram_proxies(refresh=True)
                    index = 0
                    if not proxies:
                        break
                    continue
                index += 1

        if not allow_direct_fallback:
            if last_error is not None:
                raise last_error
            return await super().make_request(bot, method, timeout=timeout)

        logger.warning("All Telegram proxies failed, retrying without proxy")
        try:
            await self._reset_direct_connector()
            return await super().make_request(bot, method, timeout=timeout)
        except Exception as exc:
            if last_error is not None and is_proxy_or_network_error(exc):
                raise last_error from exc
            raise

    async def make_request(
        self,
        bot,
        method: TelegramMethod[TelegramType],
        timeout: Optional[int] = None,
    ) -> TelegramType:
        return await self._request_via_proxies(
            bot,
            method,
            timeout,
            allow_direct_fallback=True,
        )
