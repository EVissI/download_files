import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram.fsm.storage.redis import RedisStorage, DefaultKeyBuilder
from aiogram import Bot, Dispatcher
from apscheduler.triggers.cron import CronTrigger

from bot.common.func.aps_sheldure import schedule_gift_job_from_db
from bot.common.middlewares.database_middleware import (
    DatabaseMiddlewareWithCommit,
    DatabaseMiddlewareWithoutCommit,
)
from bot.common.middlewares.i18n import TranslatorRunnerMiddleware
from bot.common.tasks.deactivate import expire_analiz_balances
from bot.common.tasks.gift import check_and_notify_gift
from bot.common.tasks.cleanup_screenshots import cleanup_screenshots
from bot.db.pg_backup import backup_postgres_to_yandex_disk
from bot.routers.admin.notify import resume_scheduled_broadcasts
from bot.routers.setup import setup_router
from bot.config import settings, setup_logger
from bot.db.redis import redis_client

setup_logger("bot")
from aiogram.types import BotCommand, BotCommandScopeDefault
from bot.config import translator_hub
from loguru import logger
from bot.config import bot, admins, scheduler


async def set_commands():
    commands = [BotCommand(command="start", description="Start button")]
    await bot.set_my_commands(commands, scope=BotCommandScopeDefault())


def setup_expire_scheduler():
    scheduler.add_job(expire_analiz_balances, "interval", hours=1)
    scheduler.add_job(backup_postgres_to_yandex_disk, CronTrigger(hour=0, minute=0))
    scheduler.add_job(cleanup_screenshots, "interval", minutes=30)


async def start_bot():
    await set_commands()
    setup_expire_scheduler()
    await resume_scheduled_broadcasts()
    await schedule_gift_job_from_db()
    scheduler.start()
    for admin_id in admins:
        try:
            await bot.send_message(admin_id, f"Я запущен🥳.")
        except:
            pass
    logger.info("Бот успешно запущен.")


async def stop_bot():
    await redis_client.close()
    try:
        for admin_id in admins:
            await bot.send_message(admin_id, "Бот остановлен. За что?😔")
    except:
        pass
    logger.error("Бот остановлен!")


async def main():
    await redis_client.connect()
    storage = RedisStorage(
        redis_client.redis,
        key_builder=DefaultKeyBuilder(with_bot_id=True, with_destiny=True),
    )
    dp = Dispatcher(storage=storage)
    dp.startup.register(start_bot)
    dp.shutdown.register(stop_bot)
    dp.update.middleware.register(DatabaseMiddlewareWithoutCommit())
    dp.update.middleware.register(DatabaseMiddlewareWithCommit())
    dp.update.middleware.register(TranslatorRunnerMiddleware())
    dp.include_router(setup_router)
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot, _translator_hub=translator_hub)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
