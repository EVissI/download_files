import asyncio
import random
from aiogram.types import Message
from typing import Optional
from fluentogram import TranslatorRunner
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from locales.stub import TranslatorRunner

class WaitingMessageManager:
    def __init__(self, chat_id, bot, i18n: TranslatorRunner):
        self.chat_id = chat_id
        self.bot = bot
        self.message: Optional[Message] = None
        self.task: Optional[asyncio.Task] = None
        self.active = False
        self.i18n = i18n

    async def start(self):
        self.active = True
        self.message = await self.bot.send_message(self.chat_id, self.i18n.waiting.think1())
        self.task = asyncio.create_task(self._update_loop())

    async def stop(self):
        self.active = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        if self.message:
            await self.message.delete()

    async def _update_loop(self):
        idx = 1
        while self.active:
            try:
                await asyncio.sleep(1.5)
                if not self.active:
                    break
                new_text = getattr(self.i18n.waiting, f"think{idx % 3 + 1}")()
                await self.message.edit_text(new_text)
                idx += 1
            except Exception:
                # Игнорируем ошибки редактирования
                pass