import asyncio
import time
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject


class MinimumUpdateProcessTimeMiddleware(BaseMiddleware):
    def __init__(self, min_process_seconds: float = 0.3):
        self._min_process_seconds = max(0.0, float(min_process_seconds))

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        start = time.monotonic()
        try:
            return await handler(event, data)
        finally:
            elapsed = time.monotonic() - start
            need = self._min_process_seconds - elapsed
            if need > 0:
                await asyncio.sleep(need)
