"""AiohttpSession: polling БД для текущего прокси + failover при ошибках подключения."""

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
    """
    Polling актуального прокси из БД.

    Нужен во время long polling getUpdates: иначе смена URL/статуса в FAB
    не применится, пока висит текущий запрос.
    """
    if not isinstance(session, FailoverAiohttpSession):
        return

    while True:
        try:
            await session.sync_from_db()
        except NoActiveTelegramProxyError:
            logger.warning("Telegram proxy DB poll: no active proxies in DB")
        except Exception as exc:
            logger.warning("Telegram proxy DB poll failed: {}", exc)
        await asyncio.sleep(interval)


class FailoverAiohttpSession(AiohttpSession):
    """
    Текущий прокси обновляется polling'ом из БД.
    При ошибках подключения — переключение на другой прокси, пока запрос не пройдёт.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._state_lock = asyncio.Lock()
        self._active_proxy_id: int | None = None
        self._active_proxy_url: str | None = None
        self._consecutive_failures = 0
        self._db_sync_task: asyncio.Task | None = None
        self._proxy_generation = 0

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

    async def _apply_proxy(
        self,
        proxy_id: int,
        proxy_url: str,
        *,
        interrupt_inflight: bool,
    ) -> None:
        """Применяет прокси. При смене URL закрывает сессию, чтобы сорвать long poll."""
        if self._active_proxy_id == proxy_id and self._active_proxy_url == proxy_url:
            return

        self.proxy = proxy_url
        self._active_proxy_id = proxy_id
        self._active_proxy_url = proxy_url
        self._proxy_generation += 1
        self._consecutive_failures = 0

        if interrupt_inflight:
            # Прерываем висящий getUpdates / другие запросы на старом коннекторе.
            await self.close()

    async def sync_from_db(
        self,
        *,
        exclude_ids: set[int] | None = None,
        interrupt_inflight: bool = True,
    ) -> str:
        """
        Polling: читает БД и обновляет текущий прокси.
        - тот же id, новый URL → применяем новые значения;
        - текущий неактивен/истёк → берём следующий из БД.
        """
        clear_telegram_proxy_cache()
        resolved = await asyncio.to_thread(
            resolve_session_proxy_sync,
            self._active_proxy_id,
            self._active_proxy_url,
            exclude_ids=exclude_ids,
        )
        if resolved is None:
            async with self._state_lock:
                changed = (
                    self._active_proxy_id is not None or self._active_proxy_url is not None
                )
                self._active_proxy_id = None
                self._active_proxy_url = None
                if changed and interrupt_inflight:
                    await self.close()
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
                        "Telegram proxy switched from DB poll: id={} {} -> id={} {} ({})",
                        previous_id,
                        mask_proxy_url(previous_url or ""),
                        proxy_id,
                        mask_proxy_url(proxy_url),
                        proxy_name,
                    )
                elif previous_url != proxy_url:
                    logger.warning(
                        "Telegram proxy updated from DB poll: id={} {} -> {} ({})",
                        proxy_id,
                        mask_proxy_url(previous_url or ""),
                        mask_proxy_url(proxy_url),
                        proxy_name,
                    )
            else:
                logger.info(
                    "Telegram proxy selected from DB poll: id={} {} ({})",
                    proxy_id,
                    mask_proxy_url(proxy_url),
                    proxy_name,
                )

            await self._apply_proxy(
                proxy_id,
                proxy_url,
                interrupt_inflight=interrupt_inflight,
            )
            return proxy_url

    async def _switch_to_next_proxy(
        self,
        *,
        exclude_ids: set[int] | None,
    ) -> str | None:
        try:
            return await self.sync_from_db(
                exclude_ids=exclude_ids,
                interrupt_inflight=True,
            )
        except NoActiveTelegramProxyError:
            logger.error(
                "No backup telegram proxy after failures (excluded={})",
                sorted(exclude_ids) if exclude_ids else [],
            )
            return None

    async def make_request(
        self,
        bot,
        method: TelegramMethod[TelegramType],
        timeout: Optional[int] = None,
    ) -> TelegramType:
        """
        Запросы идут через текущий прокси (из polling).
        При ошибках подключения переключаемся на другой из БД, пока запрос не пройдёт.
        """
        last_error: TelegramNetworkError | None = None
        excluded_proxy_ids: set[int] = set()

        while True:
            async with self._state_lock:
                proxy_id = self._active_proxy_id
                proxy_url = self._active_proxy_url
                generation = self._proxy_generation

            if proxy_id is None or proxy_url is None:
                try:
                    await self.sync_from_db(
                        exclude_ids=excluded_proxy_ids or None,
                        interrupt_inflight=False,
                    )
                except NoActiveTelegramProxyError:
                    if last_error is not None:
                        raise last_error
                    raise TelegramNetworkError(
                        method=method,
                        message="No active Telegram proxies configured in DB",
                    )
                continue

            if proxy_id in excluded_proxy_ids:
                next_proxy = await self._switch_to_next_proxy(
                    exclude_ids=excluded_proxy_ids,
                )
                if next_proxy is None:
                    break
                continue

            try:
                result = await super().make_request(bot, method, timeout=timeout)
                async with self._state_lock:
                    if self._active_proxy_id == proxy_id:
                        self._consecutive_failures = 0
                await asyncio.to_thread(
                    record_proxy_connection_success_sync,
                    proxy_url,
                )
                return result
            except ValueError as exc:
                logger.error(
                    "Invalid telegram proxy URL {}: {}",
                    mask_proxy_url(proxy_url),
                    exc,
                )
                last_error = self._as_network_error(method, exc)
                excluded_proxy_ids.add(proxy_id)
                next_proxy = await self._switch_to_next_proxy(
                    exclude_ids=excluded_proxy_ids,
                )
                if next_proxy is None:
                    raise last_error
                continue
            except Exception as exc:
                if not is_proxy_or_network_error(exc):
                    raise

                async with self._state_lock:
                    # Polling уже сменил прокси (в т.ч. сорвав long poll) — просто ретрай.
                    if (
                        self._proxy_generation != generation
                        or self._active_proxy_id != proxy_id
                    ):
                        continue

                last_error = self._as_network_error(method, exc)
                logger.warning(
                    "Telegram proxy connection error: id={} {} — switching to another",
                    proxy_id,
                    mask_proxy_url(proxy_url),
                )
                logger.warning("Telegram proxy error detail: {}", exc)

                deactivated = await asyncio.to_thread(
                    record_proxy_connection_failure_sync,
                    proxy_url,
                )

                async with self._state_lock:
                    if (
                        self._proxy_generation != generation
                        or self._active_proxy_id != proxy_id
                    ):
                        continue
                    self._consecutive_failures += 1
                    if (
                        self._consecutive_failures >= CONSECUTIVE_FAILURES_TO_DEACTIVATE
                        or deactivated
                    ):
                        logger.error(
                            "Telegram proxy id={} reached {} failures — excluded from this cycle",
                            proxy_id,
                            CONSECUTIVE_FAILURES_TO_DEACTIVATE,
                        )

                excluded_proxy_ids.add(proxy_id)
                next_proxy = await self._switch_to_next_proxy(
                    exclude_ids=excluded_proxy_ids,
                )
                if next_proxy is None:
                    raise last_error
                continue

        if last_error is not None:
            raise last_error
        raise TelegramNetworkError(
            method=method,
            message="All Telegram proxies are unavailable",
        )
