import os
import re
from loguru import logger
from bot.common.utils.i18n import create_translator_hub
from fluentogram import TranslatorHub
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
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

    S3_URL: str
    BACKET_NAME: str
    S3_ACCESS_KEY: str
    S3_SECRET_ACESS_KEY: str
    S3_REGION: str = "ru"
    S3_ADDRESSING_STYLE: str = "path"

    SYNCTHING_API_KEY: str = ""
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

    # HTTP/SOCKS прокси для api.telegram.org (aiohttp-socks).
    # Основной источник — FAB «Прокси Telegram» (БД). TELEGRAM_PROXY — локальное переопределение.
    TELEGRAM_PROXY: Optional[str] = None

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


_TELEGRAM_BOT_URL_RE = re.compile(
    r"https?://api\.telegram\.org/bot[^\s/]+", re.IGNORECASE
)
_TELEGRAM_BOT_PATH_RE = re.compile(r"/bot[^\s/]+", re.IGNORECASE)


def format_telegram_api_error(exc: BaseException) -> str:
    """Текст ошибки без BOT_TOKEN и без URL api.telegram.org/bot…"""
    msg = str(exc) or repr(exc)
    msg = _TELEGRAM_BOT_URL_RE.sub("https://api.telegram.org/bot***", msg)
    msg = _TELEGRAM_BOT_PATH_RE.sub("/bot***", msg)
    token = settings.BOT_TOKEN
    if token:
        msg = msg.replace(token, "***")
    return f"{type(exc).__name__}: {msg}"


def _build_bot() -> Bot:
    from bot.common.telegram_failover_session import FailoverAiohttpSession

    kwargs = dict(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    if settings.TELEGRAM_PROXY:
        kwargs["session"] = AiohttpSession(proxy=settings.TELEGRAM_PROXY)
    else:
        kwargs["session"] = FailoverAiohttpSession()
    return Bot(**kwargs)


def create_bot_for_sync_context() -> Bot:
    """Отдельный Bot для asyncio.run() из синхронного кода (иный event loop)."""
    return _build_bot()


bot = _build_bot()
admins = settings.ROOT_ADMIN_IDS
SUPPORT_TG_ID = 826161194

jobstores = {"default": SQLAlchemyJobStore(url=settings.DB_URL_SYNC)}

scheduler = AsyncIOScheduler(jobstores=jobstores, timezone=timezone("Europe/Moscow"))


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
