"""AiohttpSession с переключением на следующий прокси при сетевой ошибке."""

from __future__ import annotations

from typing import Optional

from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import TelegramNetworkError
from aiogram.methods.base import TelegramMethod
from aiogram.client.session.base import TelegramType
from loguru import logger

from bot.common.proxy_utils import mask_proxy_url
from bot.common.telegram_proxy_config import get_effective_telegram_proxies
from bot.config import settings


class FailoverAiohttpSession(AiohttpSession):
    """Пробует прокси по очереди из Redis/БД при ошибках соединения."""

    async def make_request(
        self,
        bot,
        method: TelegramMethod[TelegramType],
        timeout: Optional[int] = None,
    ) -> TelegramType:
        if settings.TELEGRAM_PROXY:
            return await super().make_request(bot, method, timeout=timeout)

        proxies = get_effective_telegram_proxies()
        if not proxies:
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

        if last_error is not None:
            raise last_error
        return await super().make_request(bot, method, timeout=timeout)
