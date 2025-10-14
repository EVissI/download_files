from aiogram import Router, F
from aiogram.types import Message, WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.exceptions import TelegramAPIError
from loguru import logger
import asyncio
import tempfile
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

    tmp_in = os.path.join(tempfile.gettempdir(), random_filename(ext=".mat", length=8))
    # Use permanent location for JSON output
    game_id = fname.replace('.mat', '')
    permanent_json_path = f"files/{game_id}.json"

    try:
        await message.reply("Принял файл, начинаю обработку...")
        file = await message.bot.get_file(doc.file_id)
        with open(tmp_in, "wb") as f:
            await message.bot.download_file(file.file_path, f)

        # Process file directly to permanent location
        game_id = fname.replace('.mat', '')
        permanent_json_path = f"files/{game_id}.json"

        await asyncio.to_thread(process_mat_file, tmp_in, permanent_json_path)

        json_document = FSInputFile(path=permanent_json_path, filename=f"{game_id}.json")
        await message.answer_document(
            document=json_document,
            caption="Сгенерированный JSON файл анализа"
        )

        mini_app_url = f"{settings.MINI_APP_URL}/hint-viewer?game_id={game_id}"
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Открыть интерактивную визуализацию", web_app=WebAppInfo(url = mini_app_url))]
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
        try:
            if os.path.exists(tmp_in):
                os.remove(tmp_in)
        except Exception:
            pass
        await state.set_state(GeneralStates.admin_panel)


# FastAPI endpoints for web interface

@hint_viewer_api_router.get("/hint-viewer")
async def get_hint_viewer_web(request: Request, game_id: str = None):
    """
    Serve the hint viewer HTML page for a specific game.
    """
    if not game_id:
        raise HTTPException(status_code=400, detail="game_id parameter is required")
    # For now, return a placeholder; we'll integrate with data later
    return templates.TemplateResponse("hint_viewer.html", {"request": request, "game_id": game_id})

@hint_viewer_api_router.get("/api/analysis/{game_id}")
async def get_analysis_data(game_id: str):
    """
    Return JSON data for the game analysis.
    """
    try:
        data = generate_analysis_data(game_id)
        return data
    except Exception as e:
        logger.error(f"Error fetching analysis data for {game_id}: {e}")
        raise HTTPException(status_code=500, detail="Error generating analysis data")

# Function to generate analysis data (integrate with hint_viewer.py)
def generate_analysis_data(game_id: str):
    """
    Generate or load analysis data for the given game_id.
    This should integrate with process_mat_file or similar.
    """
    import tempfile
    import os

    # For now, assume game_id is a path to .mat file or identifier
    # In real implementation, this would map game_id to file path or DB record
    mat_file_path = f"files/{game_id}.mat"  # Example path

    if not os.path.exists(mat_file_path):
        logger.warning(f"File not found: {mat_file_path}")
        return []

    tmp_out = os.path.join(tempfile.gettempdir(), random_filename(ext=".json", length=8))

    try:
        # Process the .mat file to generate JSON
        process_mat_file(mat_file_path, tmp_out)

        # Load the generated JSON
        with open(tmp_out, "r", encoding="utf-8") as f:
            data = json.load(f)

        return data
    except Exception as e:
        logger.error(f"Error generating analysis data for {game_id}: {e}")
        return []
    finally:
        # Clean up temp file
        if os.path.exists(tmp_out):
            try:
                os.unlink(tmp_out)
            except Exception:
                pass