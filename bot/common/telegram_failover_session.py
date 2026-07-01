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

from bot.common.proxy_utils import mask_proxy_url
from bot.common.telegram_proxy_config import get_effective_telegram_proxies, get_env_telegram_proxy


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

    async def make_request(
        self,
        bot,
        method: TelegramMethod[TelegramType],
        timeout: Optional[int] = None,
    ) -> TelegramType:
        env_proxy = get_env_telegram_proxy()
        if env_proxy:
            if self.proxy != env_proxy:
                self.proxy = env_proxy
            return await super().make_request(bot, method, timeout=timeout)

        proxies = get_effective_telegram_proxies()
        if not proxies:
            await self._reset_direct_connector()
            return await super().make_request(bot, method, timeout=timeout)

        last_error: TelegramNetworkError | None = None
        for index, proxy_url in enumerate(proxies):
            try:
                if self.proxy != proxy_url:
                    self.proxy = proxy_url
                return await super().make_request(bot, method, timeout=timeout)
            except TelegramNetworkError as exc:
                last_error = exc
                logger.warning(
                    "Telegram proxy failed ({}/{}): {} — {}",
                    index + 1,
                    len(proxies),
                    mask_proxy_url(proxy_url),
                    exc,
                )
                self._should_reset_connector = True

        logger.warning(
            "All {} Telegram proxies failed, retrying without proxy",
            len(proxies),
        )
        try:
            await self._reset_direct_connector()
            return await super().make_request(bot, method, timeout=timeout)
        except TelegramNetworkError:
            if last_error is not None:
                raise last_error
            raise
