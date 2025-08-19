import os
import uuid  # Добавляем для генерации уникального имени директории

from aiogram import Router, F
from aiogram.types import (
    Message,
    WebAppInfo,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
import aiohttp
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from pathlib import Path
import httpx
from bot.common.filters.user_info import UserInfo
from bot.common.utils.i18n import get_all_locales_for_key
from bot.config import translator_hub
from typing import TYPE_CHECKING
from fluentogram import TranslatorRunner
from bot.config import settings
from bot.db.dao import UserDAO
from bot.db.models import User
from bot.config import bot
from front.src.lib.game_parser import parse_file


class ShortBoardDialog(StatesGroup):
    file = State()


short_board_router = Router()

@short_board_router.message(
    F.text.in_(
        get_all_locales_for_key(translator_hub, "keyboard-user-reply-short_board_view")
    ),
    UserInfo(),
)
async def short_board_command(
    message: Message,
    user_info: User,
    state: FSMContext,
    i18n: TranslatorRunner,
    session_without_commit: AsyncSession,
):
    await message.answer("Отправь файл с игрой для обработки.")
    await state.set_state(ShortBoardDialog.file)


@short_board_router.message(F.document, StateFilter(ShortBoardDialog.file))
async def handle_document(message: Message, state: FSMContext,session_without_commit: AsyncSession):
    try:
        file = message.document
        chat_id = message.chat.id

        # Генерация уникального имени директории
        dir_name = str(uuid.uuid4())
        files_dir = os.path.join(os.getcwd(), "files", dir_name)
        os.makedirs(files_dir, exist_ok=True)

        file_name = file.file_name.replace(" ", "").replace(".txt", ".mat")
        file_path = os.path.join(files_dir, file_name)

        await message.bot.download(file.file_id, destination=file_path)
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                file_content = f.read()
        except Exception as e:
            await bot.send_message(chat_id, f"Ошибка при чтении файла: {e}")
            return
        await bot.send_message(chat_id, "Файл получен. Начинаю обработку...")

        await bot.send_message(
            chat_id, "Файл обработан. Начинаю подготовку к отображению..."
        )
        await parse_file(file_content, dir_name)  # Передаем уникальное имя директории

        # Создаем кнопку с веб-приложением
        button = InlineKeyboardButton(
            text="Открыть игру 📲",
            web_app=WebAppInfo(
                url=f"{settings.MINI_APP_URL}?game={dir_name}&chat_id={chat_id}"
            ),
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[button]])

        await bot.send_message(
            chat_id,
            "Готово! Нажми кнопку ниже, чтобы открыть игру и просмотреть ходы.",
            reply_markup=keyboard,
        )
        await UserDAO(session_without_commit).decrease_analiz_balance(
            user_id=message.from_user.id,
            service_type="SHORT_BOARD"
        )
        logger.info(f"Пользователь {message.from_user.id} использовал Short Board")
    except Exception as e:
        logger.error(f"Ошибка при обработке файла: {e}")
        await bot.send_message(
            message.chat.id, f"Произошла ошибка при обработке файла: {e}"
        )
    finally:
        await state.clear()
