import asyncio
from aiogram.fsm.storage.redis import RedisStorage, DefaultKeyBuilder
from aiogram import Bot, Dispatcher
from apscheduler.triggers.cron import CronTrigger

from bot.common.middlewares.database_middleware import (
    DatabaseMiddlewareWithCommit,
    DatabaseMiddlewareWithoutCommit,
)
from bot.common.middlewares.i18n import TranslatorRunnerMiddleware
from bot.common.middlewares.minimum_update_process_time import (
    MinimumUpdateProcessTimeMiddleware,
) 
MIN_UPDATE_PROCESS_SECONDS = 0.3 #сек
from bot.common.func.scheduler_jobs import upsert_scheduler_job
from bot.common.tasks.deactivate import expire_analiz_balances
from bot.common.tasks.cleanup_screenshots import cleanup_screenshots
from bot.common.rq_queue_maintenance import periodic_rq_registry_cleanup
from bot.common.tasks.telegram_proxy_expiry import notify_telegram_proxy_expiry
from bot.db.pg_backup import backup_postgres_to_yandex_disk
from bot.routers.setup import setup_router
from bot.config import setup_logger, bot, admins, scheduler
from bot.common.telegram_proxy_config import log_telegram_proxy_config
from bot.common.telegram_failover_session import (
    FailoverAiohttpSession,
    prepare_bot_session_proxy,
)
from bot.db.redis import redis_client

setup_logger("bot")
from aiogram.types import BotCommand, BotCommandScopeChat, BotCommandScopeDefault
from bot.config import translator_hub
from bot.db.database import async_session_maker
from bot.db.dao import UserDAO
from bot.db.models import User
from bot.db.schemas import SUser
from loguru import logger


DEFAULT_BOT_COMMANDS = [
    BotCommand(command="start", description="Start button"),
]
ADMIN_BOT_COMMANDS = DEFAULT_BOT_COMMANDS + [
    BotCommand(command="admin_menu", description="Веб-админка"),
]


async def set_admin_commands_for_user(user_id: int) -> None:
    """Показывает /admin_menu в меню Telegram только этому админу."""
    await bot.set_my_commands(
        ADMIN_BOT_COMMANDS,
        scope=BotCommandScopeChat(chat_id=user_id),
    )


async def set_commands():
    await bot.set_my_commands(DEFAULT_BOT_COMMANDS, scope=BotCommandScopeDefault())
    try:
        async with async_session_maker() as session:
            admin_users = await UserDAO(session).find_all(
                filters=SUser(role=User.Role.ADMIN.value)
            )
        for admin_user in admin_users:
            try:
                await set_admin_commands_for_user(int(admin_user.id))
            except Exception as e:
                logger.warning(
                    f"Не удалось установить admin-команды для {admin_user.id}: {e}"
                )
    except Exception as e:
        logger.warning(f"Не удалось загрузить админов для set_my_commands: {e}")


def setup_rq_maintenance_scheduler():
    upsert_scheduler_job(
        periodic_rq_registry_cleanup,
        "interval",
        "rq_registry_cleanup",
        minutes=3,
        coalesce=True,
        max_instances=1,
    )


def setup_telegram_proxy_scheduler():
    upsert_scheduler_job(
        notify_telegram_proxy_expiry,
        CronTrigger(hour=10, minute=0),
        "telegram_proxy_expiry_warning",
    )


def setup_expire_scheduler():
    scheduler.add_job(
        expire_analiz_balances,
        "interval",
        hours=1,
        id="expire_analiz_balances",
        replace_existing=True
    )
    scheduler.add_job(
        backup_postgres_to_yandex_disk,
        CronTrigger(hour=0, minute=0),
        id="daily_backup",
        replace_existing=True
    )
    scheduler.add_job(
        cleanup_screenshots,
        "interval",
        minutes=30,
        id="cleanup_screenshots",
        replace_existing=True
    )


async def start_bot():
    await set_commands()
    # setup_expire_scheduler()
    setup_telegram_proxy_scheduler()
    setup_rq_maintenance_scheduler()
    # await schedule_gift_job_from_db()
    scheduler.start()
    if isinstance(bot.session, FailoverAiohttpSession):
        bot.session.start_db_sync_task()
    for admin_id in admins:
        try:
            await bot.send_message(admin_id, f"Я запущен🥳.")
        except:
            pass
    logger.info("Бот успешно запущен.")


async def stop_bot():
    if isinstance(bot.session, FailoverAiohttpSession):
        bot.session.stop_db_sync_task()
    await redis_client.close()
    try:
        for admin_id in admins:
            await bot.send_message(admin_id, "Бот остановлен. За что?😔")
    except:
        pass
    logger.error("Бот остановлен!")


async def main():
    await redis_client.connect()
    log_telegram_proxy_config()
    prepared = prepare_bot_session_proxy(bot.session)
    if prepared:
        logger.info("Telegram session proxy prepared at startup")
    storage = RedisStorage(
        redis_client.redis,
        key_builder=DefaultKeyBuilder(with_bot_id=True, with_destiny=True),
    )
    dp = Dispatcher(storage=storage)
    dp.startup.register(start_bot)
    dp.shutdown.register(stop_bot)
    dp.update.middleware.register(
        MinimumUpdateProcessTimeMiddleware(MIN_UPDATE_PROCESS_SECONDS)
    )
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
