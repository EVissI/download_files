from aiogram import Router, F
from aiogram.types import Message, WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.exceptions import TelegramAPIError
from loguru import logger
import asyncio
import os
import json

from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import StateFilter

from fastapi import APIRouter, Request, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from bot.common.func.hint_viewer import process_mat_file, random_filename
from bot.common.kbds.markup.admin_panel import AdminKeyboard
from bot.common.general_states import GeneralStates
from bot.config import settings

# Telegram router
hint_viewer_router = Router()

# FastAPI router for web interface
hint_viewer_api_router = APIRouter()
templates = Jinja2Templates(directory="bot/templates")


class HintViewerStates(StatesGroup):
    waiting_file = State()


@hint_viewer_router.message(F.text == AdminKeyboard.get_kb_text()["test"])
async def hint_viewer_start(message: Message, state: FSMContext):
    await state.set_state(HintViewerStates.waiting_file)
    await message.answer(
        "Нажата кнопка просмотра подсказок. Пришлите .mat файл для анализа."
    )


@hint_viewer_router.message(F.document, StateFilter(HintViewerStates.waiting_file))
async def hint_viewer_menu(message: Message, state: FSMContext):
    await state.clear()
    doc = message.document
    fname = doc.file_name
    if not fname.lower().endswith(".mat"):
        await message.reply("Пожалуйста, пришлите .mat файл.")
        return

    # Скачиваем оригинальный .mat в папку files/
    game_id = fname.replace(".mat", "")
    mat_path = f"files/{fname}"
    json_path = f"files/{game_id}.json"

    try:
        await message.reply("Принял файл, начинаю обработку...")
        file = await message.bot.get_file(doc.file_id)

        # Сохраняем .mat в постоянную директорию
        os.makedirs("files", exist_ok=True)
        with open(mat_path, "wb") as f:
            await message.bot.download_file(file.file_path, f)

        # Обрабатываем .mat → .json
        await asyncio.to_thread(process_mat_file, mat_path, json_path)

        # Отправляем готовый JSON обратно пользователю
        json_document = FSInputFile(path=json_path, filename=f"{game_id}.json")
        await message.answer_document(
            document=json_document,
            caption="Сгенерированный JSON файл анализа"
        )

        # Кнопка для открытия в мини-приложении
        mini_app_url = f"{settings.MINI_APP_URL}/hint-viewer?game_id={game_id}"
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(
                    text="Открыть интерактивную визуализацию",
                    web_app=WebAppInfo(url=mini_app_url)
                )]
            ]
        )
        await message.answer(
            "Анализ завершен! Нажмите кнопку ниже для просмотра интерактивной визуализации игры:",
            reply_markup=keyboard
        )

    except Exception:
        logger.exception("Ошибка при обработке hint viewer")
        await message.reply("Ошибка при обработке файла.")
    finally:
        # Удаляем только исходный .mat файл, JSON остаётся
        try:
            if os.path.exists(mat_path):
                os.remove(mat_path)
        except Exception:
            logger.warning("Не удалось удалить mat файл после обработки.")
        await state.set_state(GeneralStates.admin_panel)


# --- FastAPI часть ---

def take_json_info(game_id: str):
    """
    Загружает и возвращает JSON с анализом для указанного game_id.
    """
    path = f"files/{game_id}.json"
    if not os.path.exists(path):
        raise FileNotFoundError(f"JSON файл для {game_id} не найден")

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@hint_viewer_api_router.get("/hint-viewer")
async def get_hint_viewer_web(request: Request, game_id: str = None):
    """
    Возвращает HTML-страницу интерактивного просмотра подсказок.
    """
    if not game_id:
        raise HTTPException(status_code=400, detail="game_id parameter is required")

    return templates.TemplateResponse(
        "hint_viewer.html",
        {"request": request, "game_id": game_id}
    )


@hint_viewer_api_router.get("/api/analysis/{game_id}")
async def get_analysis_data(game_id: str):
    """
    Возвращает JSON-данные анализа для указанного game_id.
    """
    try:
        data = take_json_info(game_id)
        return data
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Game {game_id} not found")
    except Exception as e:
        logger.error(f"Error fetching analysis data for {game_id}: {e}")
        raise HTTPException(status_code=500, detail="Error generating analysis data")