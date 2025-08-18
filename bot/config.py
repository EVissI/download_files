﻿
import os
from loguru import logger
from bot.common.utils.i18n import create_translator_hub
from fluentogram import TranslatorHub
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram import Bot

class Settings(BaseSettings):
    BASE_DIR: str = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    FORMAT_LOG: str = "{time:YYYY-MM-DD at HH:mm:ss} | {level} | {message}"
    LOG_ROTATION: str = "10 MB"

    BOT_TOKEN: str
    ROOT_ADMIN_IDS: List[int]
    YA_API_TOKEN: str
    YO_KASSA_TEL_API_KEY: str
    MINI_APP_URL:str
    
    POSTGRES_USER:str
    POSTGRES_PASSWORD:str
    POSTGRES_DB: str = 'backgammon'

    REDIS_USER: str = 'default'  
    REDIS_PASSWORD: str
    REDIS_USER_PASSWORD:str
    REDIS_HOST: str = 'redis'    
    REDIS_PORT: int = 6379       
    REDIS_DB: int = 0

    @property
    def DB_URL(self):
        return f'postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@db:5432/{self.POSTGRES_DB}'
    
    @property
    def REDIS_URL(self):
        return f'redis://{self.REDIS_USER}:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}'

    model_config = SettingsConfigDict(env_file=f"{BASE_DIR}/.env")

settings = Settings()
translator_hub: TranslatorHub = create_translator_hub()

bot = Bot(
    token=settings.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
admins = settings.ROOT_ADMIN_IDS

def setup_logger(app_name: str):
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "log")
    os.makedirs(log_dir, exist_ok=True)
    
    logger.add(
        os.path.join(log_dir, f"log_{app_name}.txt"),
        format=settings.FORMAT_LOG,
        level="INFO",
        rotation=settings.LOG_ROTATION
    )
    
    logger.add(
        os.path.join(log_dir, f"log_{app_name}_error.txt"),
        format=settings.FORMAT_LOG,
        level="ERROR",
        rotation=settings.LOG_ROTATION
    )
