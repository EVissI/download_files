import os
import re
import uuid
import asyncio
from datetime import datetime
import pytz
import zipfile
import io
from aiogram import Router, F
from aiogram.types import (
    Message,
    WebAppInfo,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    CallbackQuery,
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
from bot.common.func.game_parser import parse_file, get_names
from bot.common.func.yadisk import save_file_to_yandex_disk

# FastAPI imports
from fastapi import APIRouter, Request, HTTPException
from fastapi.templating import Jinja2Templates
import json


class ShortBoardDialog(StatesGroup):
    file = State()


short_board_router = Router()

# FastAPI router for web interface
short_board_api_router = APIRouter()
templates = Jinja2Templates(directory="bot/templates")


@short_board_router.message(
    F.text.in_(
        get_all_locales_for_key(translator_hub, "keyboard-user-reply-short_board_view")
    ),
    UserInfo(),
)
async def short_board_command(
    message: Message,
    state: FSMContext,
):
    await message.answer("Отправьте файл с игрой для обработки.")
    await state.set_state(ShortBoardDialog.file)


@short_board_router.message(F.document, StateFilter(ShortBoardDialog.file), UserInfo())
async def handle_document(
    message: Message,
    state: FSMContext,
    user_info: User,
    session_without_commit
):
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

        names = get_names(file_content)

        # создание файла для сохранения на ядиск
        moscow_tz = pytz.timezone("Europe/Moscow")
        current_date = datetime.now(moscow_tz).strftime("%d.%m.%y-%H.%M.%S")
        new_file_name = f"{current_date}:{names[0]}:{names[1]}.mat"
        new_file_path = os.path.join(files_dir, new_file_name)
        try:
            import shutil

            shutil.copy(file_path, new_file_path)
        except Exception as e:
            logger.error(f"Failed to copy file {file_path} to {new_file_path}: {e}")
            await bot.send_message(
                chat_id, "Ошибка при копировании файла. Попробуйте снова."
            )
            return

        # сохранение файла на яндекс диск
        try:
            asyncio.create_task(save_file_to_yandex_disk(new_file_path, new_file_name))
        except Exception as e:
            logger.error(f"Error saving file to Yandex Disk: {e}")

        try:
            # Парсим файл и создаем JSON для всех игр
            await parse_file(file_content, dir_name, is_inverse=False)

            # Путь к директории с JSON файлами
            json_dir_path = os.path.join("./files", dir_name)
            json_file_path = os.path.join(json_dir_path, "games.json")

            if os.path.exists(json_file_path):
                # Создаем ZIP архив в памяти
                zip_buffer = io.BytesIO()

                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                    # Добавляем games.json
                    zip_file.write(json_file_path, arcname="games.json")

                    # Добавляем исходный .mat файл для контекста
                    zip_file.write(file_path, arcname=file_name)

                zip_buffer.seek(0)

                # Отправляем ZIP админу
                from aiogram.types import BufferedInputFile

                zip_doc = BufferedInputFile(
                    zip_buffer.getvalue(),
                    filename=f"{names[0]}_vs_{names[1]}_analysis.zip",
                )

                await bot.send_document(
                    chat_id=455205382,
                    document=zip_doc,
                    caption=f"📊 Архив с JSON всех игр:\n{names[0]} vs {names[1]}\nВсего игр: {len(re.findall(r'Game \\d+', file_content)) - 1}",
                )

                logger.info(
                    f"JSON archive sent to admin for game {names[0]} vs {names[1]}"
                )
            else:
                await bot.send_message(
                    chat_id=455205382, text=f"⚠️ JSON файл не найден: {json_file_path}"
                )

        except Exception as e:
            logger.error(f"Failed to create/send JSON archive to admin: {e}")
            await bot.send_message(
                chat_id=455205382, text=f"❌ Ошибка при создании архива JSON: {e}"
            )

        # Создаем кнопку с веб-приложением
        button = InlineKeyboardButton(
            text="Открыть игру 📲",
            web_app=WebAppInfo(
                url=f"{settings.MINI_APP_URL}/board-viewer?game_id={dir_name}&chat_id={chat_id}"
            ),
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[button]])

        await bot.send_message(
            chat_id,
            "Готово! Нажми кнопку ниже, чтобы открыть игру и просмотреть ходы.",
            reply_markup=keyboard,
        )

        await UserDAO(session_without_commit).decrease_analiz_balance(
            user_id=user_info.id, service_type="SHORT_BOARD"
        )
        logger.info(f"Пользователь {user_info.id} использовал Short Board")
        await session_without_commit.commit()
        # Send notification to admin
        try:
            user_name = (
                f"{user_info.admin_insert_name} @{user_info.username or user_info.id}"
                if user_info.admin_insert_name
                else f"@{user_info.username or user_info.id}"
            )
            await bot.send_message(
                chat_id=826161194,
                text=f"Просмотр игры: {names[0]} - {names[1]}\nПользователь <b>{user_name}</b> ",
            )
        except Exception as e:
            logger.error(f"Failed to send notification to admin: {e}")
    except Exception as e:
        logger.error(f"Ошибка при обработке файла: {e}")
        await bot.send_message(
            message.chat.id, f"Произошла ошибка при обработке файла: {e}"
        )
    finally:
        await state.clear()


# --- FastAPI часть ---


def take_games_json_info(game_id: str, game_num: str = None):
    """
    Загружает и возвращает JSON с играми из game_parser для указанного game_id и номера игры.
    """
    path = f"files/{game_id}/games.json"
    if not os.path.exists(path):
        raise FileNotFoundError(f"JSON файл для {game_id} не найден")

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in {path}: {e}")
        raise HTTPException(status_code=500, detail=f"Invalid JSON file: {e}")

    # Если запросили конкретную игру
    if game_num:
        game_num_int = int(game_num)
        for game in data:
            game_number = (
                game.get("game_info", {}).get("game_number")
                or game.get("game_number")
            )
            if game_number == game_num_int:
                return game
        raise FileNotFoundError(f"Игра {game_num} не найдена в {game_id}")

    # Если game_num не передан — возвращаем список игр и общую инфу
    try:
        games_list = []
        for idx, game in enumerate(data):
            game_info = game.get("game_info", {})

            # Если game_info нет — собираем его из first/second
            if not game_info:
                game_info = {
                    "game_number": game.get("game_number", idx + 1),
                    "first_player": game.get("first", {}).get("name", "Player 1"),
                    "second_player": game.get("second", {}).get("name", "Player 2"),
                }

            games_list.append(
                {
                    "game_number": game_info.get("game_number", idx + 1),
                    "first_player": game_info.get(
                        "first_player",
                        game.get("first", {}).get("name", "Player 1"),
                    ),
                    "second_player": game_info.get(
                        "second_player",
                        game.get("second", {}).get("name", "Player 2"),
                    ),
                }
            )

        main_game_info = data[0].get("game_info", {}) if data else {}
        return {
            "games": games_list,
            "game_info": main_game_info,
        }
    except KeyError as e:
        logger.error(f"Missing key in game data: {e}")
        raise HTTPException(
            status_code=500, detail=f"Invalid game data structure: {e}"
        )

@short_board_api_router.get("/board-viewer")
async def get_board_viewer_web(request: Request, game_id: str = None):
    """
    Возвращает HTML-страницу интерактивного просмотра доски.

    Параметры:
    - game_id: ID игры (обязателен)

    Пример:
    GET /board-viewer?game_id=abc123
    """
    if not game_id:
        raise HTTPException(status_code=400, detail="game_id parameter is required")

    return templates.TemplateResponse(
        "board_viewer.html",
        {
            "request": request,
            "game_id": game_id,
        },
    )

@short_board_api_router.get("/api/games/{game_id}")
async def get_games_data(game_id: str, game_num: str = None):
    """
    Возвращает JSON-данные игр из game_parser для указанного game_id.

    Параметры:
    - game_id (path): ID игры (обязательный)
    - game_num (query): номер конкретной игры (опциональный)

    Возвращает:
    - При наличии game_num: данные конкретной игры (со всеми turns)
    - Без game_num: список всех игр + общая информация

    Примеры:
    - GET /api/games/abc123
    - GET /api/games/abc123?game_num=1
    """
    try:
        data = take_games_json_info(game_id, game_num)
        return data
    except FileNotFoundError as e:
        # сюда попадают:
        # - нет JSON файла
        # - нет такой игры game_num
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error fetching games data for {game_id}: {e}")
        raise HTTPException(status_code=500, detail="Error generating games data")