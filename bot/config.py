import os
from loguru import logger
from bot.common.utils.i18n import create_translator_hub
from fluentogram import TranslatorHub
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from pytz import timezone


class Settings(BaseSettings):
    BASE_DIR: str = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    FORMAT_LOG: str = "{time:YYYY-MM-DD at HH:mm:ss} | {level} | {message}"
    LOG_ROTATION: str = "10 MB"

    BOT_TOKEN: str
    CHAT_GROUP_ID: int
    ROOT_ADMIN_IDS: List[int]
    YA_API_TOKEN: str
    YO_KASSA_TEL_API_KEY: str

    SYNCTHING_API_KEY: str
    SYNCTHING_FOLDER: str = "backgammon-files"
    SYNCTHING_HOST: str = "localhost:8384"

    MINI_APP_URL: str

    SECRET_KEY: str = "dev-secret-key-change-in-production"

    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str = "backgammon"
    POSTGRES_HOST: str = "db"

    REDIS_USER: str = "default"
    REDIS_PASSWORD: str
    REDIS_USER_PASSWORD: str
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REMOTE_REDIS_HOST: str = "localhost"
    WORKERS_COUNT: int = 1

    @property
    def DB_URL(self):
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:5432/{self.POSTGRES_DB}"
    @property
    def DB_URL_SYNC(self):
        """Синхронный URL для APScheduler (psycopg2 вместо asyncpg)"""
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:5432/{self.POSTGRES_DB}"
    @property
    def REDIS_URL(self):
        return f"redis://{self.REDIS_USER}:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    model_config = SettingsConfigDict(env_file=f"{BASE_DIR}/.env")


settings = Settings()
translator_hub: TranslatorHub = create_translator_hub()

bot = Bot(
    token=settings.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
test_bot = Bot(
    token=settings.TEST_BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
admins = settings.ROOT_ADMIN_IDS
SUPPORT_TG_ID = 826161194

jobstores = {
    'default': SQLAlchemyJobStore(url=settings.DB_URL_SYNC)
}

scheduler = AsyncIOScheduler(
    jobstores=jobstores,
    timezone=timezone("Europe/Moscow")
)


def setup_logger(app_name: str):
    log_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "log"
    )
    os.makedirs(log_dir, exist_ok=True)

    logger.add(
        os.path.join(log_dir, f"log_{app_name}.txt"),
        format=settings.FORMAT_LOG,
        level="INFO",
        rotation=settings.LOG_ROTATION,
    )

    logger.add(
        os.path.join(log_dir, f"log_{app_name}_error.txt"),
        format=settings.FORMAT_LOG,
        level="ERROR",
        rotation=settings.LOG_ROTATION,
    )
