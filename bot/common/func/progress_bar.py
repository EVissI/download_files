import asyncio
from aiogram.types import Message
from typing import Optional
from fluentogram import TranslatorRunner
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from locales.stub import TranslatorRunner


class ProgressBarMessageManager:
    """
    Менеджер для отображения прогресс-бара с имитацией выполнения процесса.
    """

    def __init__(
        self, 
        chat_id: int, 
        bot, 
        duration_seconds: int,
        bar_length: int = 20,
        prefix: str = "Выполняю...",
        completed_text: str = "✅ Готово!"
    ):
        """
        Args:
            chat_id: ID чата для отправки сообщения
            bot: Экземпляр бота
            duration_seconds: Продолжительность прогресса в секундах
            bar_length: Длина прогресс-бара (кол-во символов)
            prefix: Префикс сообщения
            completed_text: Текст после завершения
        """
        self.chat_id = chat_id
        self.bot = bot
        self.message: Optional[Message] = None
        self.task: Optional[asyncio.Task] = None
        self.active = False
        self.duration_seconds = duration_seconds
        self.bar_length = bar_length
        self.prefix = prefix
        self.completed_text = completed_text
        self.elapsed = 0

    def _generate_progress_bar(self, progress: float) -> str:
        """
        Генерирует строку прогресс-бара.
        
        Args:
            progress: Прогресс от 0 до 1
        
        Returns:
            Строка с прогресс-баром и процентом
        """
        filled = int(self.bar_length * progress)
        empty = self.bar_length - filled
        
        bar = "█" * filled + "░" * empty
        percentage = int(progress * 100)
        
        return f"{self.prefix}\n[{bar}] {percentage}%"

    async def start(self):
        """Запускает прогресс-бар."""
        self.active = True
        self.elapsed = 0
        
        # Отправляем начальное сообщение
        self.message = await self.bot.send_message(
            self.chat_id, 
            self._generate_progress_bar(0)
        )
        
        # Запускаем цикл обновления
        self.task = asyncio.create_task(self._update_loop())

    async def stop(self):
        """Останавливает прогресс-бар и удаляет сообщение."""
        self.active = False
        
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        
        if self.message:
            await self.message.delete()

    async def finish(self):
        """Завершает прогресс-бар с финальным сообщением."""
        self.active = False
        
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        
        if self.message:
            try:
                await self.message.edit_text(self.completed_text)
            except Exception:
                pass

    async def _update_loop(self):
        """Основной цикл обновления прогресс-бара."""
        update_interval = 2 # Обновляем каждые 0.5 секунды
        
        while self.active:
            try:
                await asyncio.sleep(update_interval)
                
                if not self.active:
                    break
                
                self.elapsed += update_interval
                
                # Вычисляем прогресс (от 0 до 1)
                progress = min(self.elapsed / self.duration_seconds, 1.0)
                
                # Обновляем текст сообщения
                new_text = self._generate_progress_bar(progress)
                
                try:
                    await self.message.edit_text(new_text)
                except Exception as e:
                    logger.error(f"Ошибка при обновлении прогресс-бара {e}")
                    pass
                
                # Если прогресс завершен, выходим из цикла
                if progress >= 1.0:
                    self.active = False
                    break
                    
            except asyncio.CancelledError:
                break
            except Exception:
                pass