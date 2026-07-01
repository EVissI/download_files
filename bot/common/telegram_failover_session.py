"""AiohttpSession с динамическим failover прокси во время polling."""

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
    CONSECUTIVE_FAILURES_TO_DEACTIVATE,
    record_proxy_connection_failure_sync,
    record_proxy_connection_success_sync,
    resolve_session_proxy_sync,
)
from bot.common.telegram_proxy_config import clear_telegram_proxy_cache

DB_SYNC_INTERVAL_SECONDS = 5.0


class NoActiveTelegramProxyError(RuntimeError):
    """В БД нет доступных активных прокси."""


def prepare_bot_session_proxy(session: AiohttpSession) -> str | None:
    """Инициализация прокси при старте."""
    if not isinstance(session, FailoverAiohttpSession):
        return None

    resolved = resolve_session_proxy_sync(None, None)
    if not resolved:
        return None

    proxy_id, proxy_url, _name = resolved
    session.prepare_proxy(proxy_id, proxy_url)
    return proxy_url


async def run_telegram_proxy_db_sync_loop(
    session: AiohttpSession,
    *,
    interval: float = DB_SYNC_INTERVAL_SECONDS,
) -> None:
    """Фоновая синхронизация прокси с БД (важно во время long polling getUpdates)."""
    if not isinstance(session, FailoverAiohttpSession):
        return

    while True:
        try:
            await session.sync_from_db()
        except NoActiveTelegramProxyError:
            logger.warning("Telegram proxy DB sync: no active proxies in DB")
        except Exception as exc:
            logger.warning("Telegram proxy DB sync failed: {}", exc)
        await asyncio.sleep(interval)


class FailoverAiohttpSession(AiohttpSession):
    """Текущий прокси для всех запросов; при 3 ошибках подряд — switch."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._state_lock = asyncio.Lock()
        self._active_proxy_id: int | None = None
        self._active_proxy_url: str | None = None
        self._consecutive_failures = 0
        self._db_sync_task: asyncio.Task | None = None

    def start_db_sync_task(self) -> None:
        if self._db_sync_task is not None and not self._db_sync_task.done():
            return
        self._db_sync_task = asyncio.create_task(
            run_telegram_proxy_db_sync_loop(self),
            name="telegram_proxy_db_sync",
        )

    def stop_db_sync_task(self) -> None:
        if self._db_sync_task is None:
            return
        self._db_sync_task.cancel()
        self._db_sync_task = None

    def prepare_proxy(self, proxy_id: int, proxy_url: str) -> None:
        normalized = normalize_proxy_url(proxy_url)
        if not normalized:
            return
        self.proxy = normalized
        self._active_proxy_id = proxy_id
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

    async def _apply_proxy(self, proxy_id: int, proxy_url: str) -> None:
        if self._active_proxy_id == proxy_id and self._active_proxy_url == proxy_url:
            return
        self.proxy = proxy_url
        self._active_proxy_id = proxy_id
        self._active_proxy_url = proxy_url

    async def sync_from_db(
        self,
        *,
        exclude_ids: set[int] | None = None,
    ) -> str:
        """Читает актуальное состояние прокси из БД и переключает сессию при необходимости."""
        clear_telegram_proxy_cache()
        resolved = await asyncio.to_thread(
            resolve_session_proxy_sync,
            self._active_proxy_id,
            self._active_proxy_url,
            exclude_ids=exclude_ids,
        )
        if resolved is None:
            async with self._state_lock:
                self._active_proxy_id = None
                self._active_proxy_url = None
            raise NoActiveTelegramProxyError(
                "No active Telegram proxies configured in DB"
            )

        proxy_id, proxy_url, proxy_name = resolved
        async with self._state_lock:
            previous_id = self._active_proxy_id
            previous_url = self._active_proxy_url
            if previous_id == proxy_id and previous_url == proxy_url:
                return proxy_url

            if previous_id is not None:
                if previous_id != proxy_id:
                    logger.warning(
                        "Telegram proxy switched from DB: id={} {} -> id={} {} ({})",
                        previous_id,
                        mask_proxy_url(previous_url or ""),
                        proxy_id,
                        mask_proxy_url(proxy_url),
                        proxy_name,
                    )
                elif previous_url != proxy_url:
                    logger.warning(
                        "Telegram proxy URL updated from DB: id={} {} -> {} ({})",
                        proxy_id,
                        mask_proxy_url(previous_url or ""),
                        mask_proxy_url(proxy_url),
                        proxy_name,
                    )
            else:
                logger.info(
                    "Telegram proxy selected from DB: id={} {} ({})",
                    proxy_id,
                    mask_proxy_url(proxy_url),
                    proxy_name,
                )

            await self._apply_proxy(proxy_id, proxy_url)
            self._consecutive_failures = 0
            return proxy_url

    async def _switch_to_next_proxy(self, *, failed_proxy_id: int | None) -> str | None:
        clear_telegram_proxy_cache()
        exclude_ids = {failed_proxy_id} if failed_proxy_id is not None else None
        try:
            return await self.sync_from_db(exclude_ids=exclude_ids)
        except NoActiveTelegramProxyError:
            logger.error(
                "No backup telegram proxy after failures on id={}",
                failed_proxy_id,
            )
            return None

    async def make_request(
        self,
        bot,
        method: TelegramMethod[TelegramType],
        timeout: Optional[int] = None,
    ) -> TelegramType:
        last_error: TelegramNetworkError | None = None
        excluded_proxy_ids: set[int] = set()

        while True:
            try:
                await self.sync_from_db(
                    exclude_ids=excluded_proxy_ids or None,
                )
            except NoActiveTelegramProxyError:
                if last_error is not None:
                    raise last_error
                raise TelegramNetworkError(
                    method=method,
                    message="No active Telegram proxies configured in DB",
                )

            proxy_id = self._active_proxy_id
            proxy_url = self._active_proxy_url
            if proxy_id is None or proxy_url is None:
                break
            if proxy_id in excluded_proxy_ids:
                break

            switched_proxy = False
            for attempt in range(1, CONSECUTIVE_FAILURES_TO_DEACTIVATE + 1):
                try:
                    result = await super().make_request(bot, method, timeout=timeout)
                    async with self._state_lock:
                        if self._active_proxy_id == proxy_id:
                            self._consecutive_failures = 0
                        record_proxy_connection_success_sync(proxy_url)
                    return result
                except ValueError as exc:
                    logger.error(
                        "Invalid telegram proxy URL {}: {}",
                        mask_proxy_url(proxy_url),
                        exc,
                    )
                    last_error = self._as_network_error(method, exc)
                    excluded_proxy_ids.add(proxy_id)
                    switched_proxy = True
                    break
                except Exception as exc:
                    if not is_proxy_or_network_error(exc):
                        raise
                    last_error = self._as_network_error(method, exc)
                    logger.warning(
                        "Telegram proxy error ({}/{}): id={} {} — {}",
                        attempt,
                        CONSECUTIVE_FAILURES_TO_DEACTIVATE,
                        proxy_id,
                        mask_proxy_url(proxy_url),
                        exc,
                    )

                    async with self._state_lock:
                        if self._active_proxy_id != proxy_id:
                            switched_proxy = True
                            break

                        self._consecutive_failures += 1
                        deactivated = record_proxy_connection_failure_sync(proxy_url)

                        if (
                            self._consecutive_failures
                            >= CONSECUTIVE_FAILURES_TO_DEACTIVATE
                            or deactivated
                        ):
                            excluded_proxy_ids.add(proxy_id)
                            next_proxy = await self._switch_to_next_proxy(
                                failed_proxy_id=proxy_id,
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
