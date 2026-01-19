import asyncio
from aiogram import Dispatcher, F
from aiogram.types import Message

from bot.config import setup_logger, test_bot, admins
from bot.db.redis import redis_client

setup_logger("test_bot")
from aiogram.types import (
    BotCommand,
    BotCommandScopeDefault,
    WebAppInfo,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from loguru import logger
from bot.config import settings

async def set_commands():
    commands = [BotCommand(command="start", description="Start button")]
    await test_bot.set_my_commands(commands, scope=BotCommandScopeDefault())


dp = Dispatcher()

@dp.message(F.text == "/start")
async def cmd_start(message: Message):
    button = InlineKeyboardButton(
        text="тест",
        web_app=WebAppInfo(
            url=f"{settings.MINI_APP_URL}/pokaz&?chat_id={message.from_user.id}"
        ),
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[button]])
    await message.answer('тест', reply_markup=keyboard)


async def start_bot():
    logger.info("Бот успешно запущен.")


async def stop_bot():
    logger.error("Бот остановлен!")


async def main():
    dp.startup.register(start_bot)
    dp.shutdown.register(stop_bot)
    try:
        await test_bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(test_bot)
    finally:
        await test_bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
