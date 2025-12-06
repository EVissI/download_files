from typing import Any, Awaitable, Callable, Dict, Set
from aiogram import BaseMiddleware, Bot
from aiogram.types import Message, CallbackQuery, TelegramObject
import asyncio

# Глобальная блокировка для hint_viewer роутера
_hint_viewer_lock = asyncio.Lock()
_current_user_id: int | None = None
_waiting_users: Set[int] = set()
_bot_instance: Bot | None = None


class SingleUserMiddleware(BaseMiddleware):
    """
    Middleware, которая позволяет только одному пользователю
    одновременно использовать роутер.
    После освобождения сервиса уведомляет ожидающих пользователей.
    """

    def __init__(
        self,
        busy_message: str = "Сервис занят другим пользователем. Пожалуйста, подождите. Вы получите уведомление когда сервис освободится.",
        free_message: str = "Сервис освободился! Вы можете начать анализ.",
    ):
        self.busy_message = busy_message
        self.free_message = free_message

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        global _current_user_id, _bot_instance

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
        if bot and _bot_instance is None:
            _bot_instance = bot

        # Если текущий пользователь уже работает с роутером, пропускаем
        if _current_user_id == user_id:
            return await handler(event, data)

        # Пробуем захватить блокировку без ожидания
        if _hint_viewer_lock.locked():
            # Блокировка занята другим пользователем
            # Добавляем в очередь ожидающих
            if user_id not in _waiting_users:
                _waiting_users.add(user_id)

            if isinstance(event, Message):
                await event.answer(self.busy_message)
            elif isinstance(event, CallbackQuery):
                await event.answer(self.busy_message, show_alert=True)
            return None

        async with _hint_viewer_lock:
            _current_user_id = user_id
            # Убираем текущего пользователя из ожидающих, если он там был
            _waiting_users.discard(user_id)
            try:
                return await handler(event, data)
            finally:
                _current_user_id = None
                # Уведомляем ожидающих пользователей
                await self._notify_waiting_users()

    async def _notify_waiting_users(self):
        """Уведомляет всех ожидающих пользователей об освобождении сервиса"""
        global _waiting_users, _bot_instance

        if not _waiting_users or not _bot_instance:
            return

        users_to_notify = _waiting_users.copy()
        _waiting_users.clear()

        for user_id in users_to_notify:
            try:
                await _bot_instance.send_message(user_id, self.free_message)
            except Exception:
                # Игнорируем ошибки отправки (пользователь заблокировал бота и т.д.)
                pass
