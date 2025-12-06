from typing import Any, Awaitable, Callable, Dict, Set
from aiogram import BaseMiddleware, Bot
from aiogram.types import Message, CallbackQuery, TelegramObject
import asyncio

from loguru import logger


class LimitedUsersMiddleware(BaseMiddleware):
    """
    Middleware, которая позволяет ограниченному количеству пользователей
    одновременно использовать роутер.
    После освобождения слота уведомляет ожидающих пользователей.
    """

    # Класс-уровневые переменные для хранения состояния между экземплярами
    _instances: Dict[str, "LimitedUsersMiddleware"] = {}

    def __init__(
        self,
        max_users: int = 1,
        busy_message: str = "Сервис занят. Пожалуйста, подождите. Вы получите уведомление когда освободится слот.",
        free_message: str = "Сервис освободился! Вы можете начать анализ.",
        instance_name: str = "default",
    ):
        self.max_users = max_users
        self.busy_message = busy_message
        self.free_message = free_message
        self.instance_name = instance_name

        # Используем семафор вместо Lock для поддержки нескольких пользователей
        self._semaphore = asyncio.Semaphore(max_users)
        self._active_users: Set[int] = set()
        self._waiting_users: Set[int] = set()
        self._bot_instance: Bot | None = None
        self._lock = asyncio.Lock()  # Для защиты доступа к _active_users

        # Регистрируем экземпляр
        LimitedUsersMiddleware._instances[instance_name] = self

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        # Получаем user_id и bot из события
        user_id = None
        bot = data.get("bot")

        if isinstance(event, Message):
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id

        if user_id is None:
            return await handler(event, data)

        # Сохраняем bot instance для уведомлений
        if bot and self._bot_instance is None:
            self._bot_instance = bot

        # Если пользователь уже активен, пропускаем проверку
        async with self._lock:
            if user_id in self._active_users:
                return await handler(event, data)

        # Проверяем, есть ли свободные слоты
        if self._semaphore.locked() and len(self._active_users) >= self.max_users:
            # Все слоты заняты
            async with self._lock:
                if user_id not in self._waiting_users:
                    self._waiting_users.add(user_id)

            if isinstance(event, Message):
                await event.answer(self.busy_message)
            elif isinstance(event, CallbackQuery):
                await event.answer(self.busy_message, show_alert=True)
            return None

        # Пробуем захватить слот
        async with self._semaphore:
            async with self._lock:
                self._active_users.add(user_id)
                self._waiting_users.discard(user_id)

            try:
                return await handler(event, data)
            finally:
                async with self._lock:
                    self._active_users.discard(user_id)
                # Уведомляем ожидающих пользователей
                await self._notify_waiting_users()

    async def _notify_waiting_users(self):
        """Уведомляет ожидающих пользователей об освобождении слота"""
        if not self._waiting_users or not self._bot_instance:
            return

        # Уведомляем только одного пользователя (первого в очереди)
        async with self._lock:
            if self._waiting_users:
                user_id = next(iter(self._waiting_users))
                self._waiting_users.discard(user_id)

        try:
            await self._bot_instance.send_message(user_id, self.free_message)
        except Exception as e:
            logger.error(f"Не удалось уведомить пользователя {user_id}: {e}")


# Алиас для обратной совместимости
SingleUserMiddleware = LimitedUsersMiddleware
