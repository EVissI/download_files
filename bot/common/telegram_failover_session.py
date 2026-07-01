"""AiohttpSession с переключением на следующий прокси при сетевой ошибке."""

from __future__ import annotations

from typing import Optional

from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import TelegramNetworkError
from aiogram.methods.base import TelegramMethod
from aiogram.client.session.base import TelegramType

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

    async def make_request(
        self,
        bot,
        method: TelegramMethod[TelegramType],
        timeout: Optional[int] = None,
    ) -> TelegramType:
        proxies = get_effective_telegram_proxies()
        if not proxies:
            raise TelegramNetworkError(
                method=method,
                message="No active Telegram proxies configured in DB",
            )

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

        if last_error is not None:
            raise last_error
        raise TelegramNetworkError(
            method=method,
            message="All Telegram proxies are unavailable",
        )
