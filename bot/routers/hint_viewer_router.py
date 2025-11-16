from aiogram import Router, F
from aiogram.types import Message, WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile, CallbackQuery, BufferedInputFile
from aiogram.exceptions import TelegramAPIError
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from loguru import logger
import asyncio
import os
import json
import zipfile
import io
import shutil

from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import StateFilter

from fastapi import APIRouter, Request, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from bot.common.filters.user_info import UserInfo
from bot.common.func.hint_viewer import process_mat_file, random_filename, extract_player_names
from bot.common.func.waiting_message import WaitingMessageManager
from bot.common.kbds.markup.main_kb import MainKeyboard
from bot.common.general_states import GeneralStates
from bot.common.utils.i18n import get_all_locales_for_key
from bot.config import settings

from bot.config import translator_hub
from typing import TYPE_CHECKING

from bot.db.models import User
if TYPE_CHECKING:
    from locales.stub import TranslatorRunner

# Telegram router
hint_viewer_router = Router()

# FastAPI router for web interface
hint_viewer_api_router = APIRouter()
templates = Jinja2Templates(directory="bot/templates")


class HintViewerStates(StatesGroup):
    choose_type = State()
    waiting_file = State()
    uploading_sequential = State()
    uploading_zip = State()


@hint_viewer_router.message(F.text.in_(get_all_locales_for_key(translator_hub, "keyboard-user-reply-hint_viewer")), UserInfo())
async def hint_viewer_start(message: Message, state: FSMContext):
    await state.set_state(HintViewerStates.choose_type)
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="Один файл", callback_data="hint_type:single")
    keyboard.button(text="Пакетный анализ", callback_data="hint_type:batch")
    keyboard.adjust(1)
    await message.answer(
        "Выберите тип анализа:",
        reply_markup=keyboard.as_markup()
    )


@hint_viewer_router.callback_query(F.data.startswith("hint_type:"), StateFilter(HintViewerStates.choose_type))
async def handle_hint_type_selection(callback: CallbackQuery, state: FSMContext):
    hint_type = callback.data.split(":")[1]
    if hint_type == "single":
        await state.set_state(HintViewerStates.waiting_file)
        await callback.message.answer("Пришлите .mat файл для анализа.")
    else:  # batch
        await state.set_state(HintViewerStates.uploading_sequential)
        await state.update_data(file_paths=[])
        keyboard = ReplyKeyboardBuilder()
        keyboard.button(text="Завершить")
        await callback.message.answer(
            "Присылайте .mat файлы по одному. Нажмите 'Завершить' когда закончите.",
            reply_markup=keyboard.as_markup(resize_keyboard=True)
        )
    await callback.answer()
    await callback.message.delete()


@hint_viewer_router.message(F.text == "Завершить", StateFilter(HintViewerStates.uploading_sequential), UserInfo())
async def handle_batch_stop(message: Message, state: FSMContext, user_info:User, i18n):
    data = await state.get_data()
    file_paths = data.get("file_paths", [])
    if not file_paths:
        await message.answer("Нет файлов для обработки.", reply_markup=MainKeyboard.build(user_info.role, i18n))
        await state.clear()
        await state.set_state(GeneralStates.admin_panel)
        return

    await process_batch_hint_files(message, state, file_paths, message.from_user.id, i18n, user_info)


@hint_viewer_router.message(F.document, StateFilter(HintViewerStates.uploading_sequential))
async def handle_sequential_hint_file(message: Message, state: FSMContext):
    doc = message.document
    fname = doc.file_name
    if not fname.lower().endswith(".mat"):
        await message.reply("Пожалуйста, пришлите .mat файл.")
        return

    # Скачиваем файл
    mat_path = f"files/{fname}"
    os.makedirs("files", exist_ok=True)
    file = await message.bot.get_file(doc.file_id)
    with open(mat_path, "wb") as f:
        await message.bot.download_file(file.file_path, f)

    data = await state.get_data()
    file_paths = data.get("file_paths", [])
    file_paths.append(mat_path)
    await state.update_data(file_paths=file_paths)
    await message.answer(f"Файл добавлен. Всего файлов: {len(file_paths)}")


@hint_viewer_router.message(F.document, StateFilter(HintViewerStates.waiting_file))
async def hint_viewer_menu(message: Message, state: FSMContext, i18n):
    doc = message.document
    fname = doc.file_name
    if not fname.lower().endswith(".mat"):
        await message.reply("Пожалуйста, пришлите .mat файл.")
        return

    # Скачиваем оригинальный .mat в папку files/
    game_id = random_filename(ext='')
    mat_path = f"files/{fname}"
    json_path = f"files/{game_id}.json"

    try:
        file = await message.bot.get_file(doc.file_id)

        # Сохраняем .mat в постоянную директорию
        os.makedirs("files", exist_ok=True)
        with open(mat_path, "wb") as f:
            await message.bot.download_file(file.file_path, f)
        with open(mat_path, "r", encoding="utf-8") as f:
            content = f.read()
        red_player, black_player = extract_player_names(content)

        # Сохраняем данные в state
        await state.update_data(
            game_id=game_id,
            mat_path=mat_path,
            json_path=json_path,
            red_player=red_player,
            black_player=black_player
        )

        # Начинаем обработку сразу
        waiting_manager = WaitingMessageManager(message.from_user.id, message.bot, i18n)
        await waiting_manager.start()

        try:
            # Обрабатываем .mat → директория с JSON файлами игр
            await asyncio.to_thread(process_mat_file, mat_path, json_path, str(message.from_user.id))

            # Создаем ZIP архив из директории с результатами
            games_dir = json_path.rsplit('.', 1)[0] + "_games"
            if os.path.exists(games_dir):
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                    for root, dirs, files in os.walk(games_dir):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, games_dir)
                            zip_file.write(file_path, arcname)

                zip_buffer.seek(0)
                zip_data = zip_buffer.getvalue()

                # Отправляем ZIP архив пользователю
                from aiogram.types import BufferedInputFile
                zip_file = BufferedInputFile(zip_data, filename=f"{game_id}_analysis.zip")
                await message.answer_document(
                    document=zip_file,
                    caption=f"Архив с анализом игр ({len(os.listdir(games_dir))} файлов)"
                )

                # Кнопка для открытия в мини-приложении (если есть хотя бы одна игра)
                game_files = [f for f in os.listdir(games_dir) if f.endswith('.json')]
                if game_files:
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
                        "Анализ завершен! Нажмите кнопку ниже для просмотра интерактивной визуализации первой игры:",
                        reply_markup=keyboard
                    )
            else:
                if os.path.exists(json_path):
                    json_document = FSInputFile(path=json_path, filename=f"{game_id}.json")
                    await message.answer_document(
                        document=json_document,
                        caption=f"Сгенерированный JSON файл анализа"
                    )

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
            await waiting_manager.stop()
            try:
                if os.path.exists(mat_path):
                    os.remove(mat_path)
            except Exception:
                logger.warning("Не удалось удалить mat файл после обработки.")
            await state.clear()
            await state.set_state(GeneralStates.admin_panel)

    except Exception:
        logger.exception("Ошибка при обработке hint viewer")
        await message.reply("Ошибка при обработке файла.")
        await state.clear()
        await state.set_state(GeneralStates.admin_panel)




# --- FastAPI часть ---

def take_json_info(game_id: str, game_num: str = None):
    """
    Загружает и возвращает JSON с анализом для указанного game_id и номера игры.
    """
    if game_num:
        # Ищем файл конкретной игры
        games_dir = f"files/{game_id}_games"
        game_file = f"{games_dir}/game_{game_num}.json"
        if os.path.exists(game_file):
            with open(game_file, "r", encoding="utf-8") as f:
                return json.load(f)
        else:
            raise FileNotFoundError(f"JSON файл для игры {game_num} в {game_id} не найден")
    else:
        # Загружаем общий файл с информацией о всех играх
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
async def get_analysis_data(game_id: str, game_num: str = None):
    """
    Возвращает JSON-данные анализа для указанного game_id и номера игры.
    Если game_num не указан, возвращает список всех игр.
    """
    try:
        data = take_json_info(game_id, game_num)
        return data
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Game {game_id} not found")
    except Exception as e:
        logger.error(f"Error fetching analysis data for {game_id}: {e}")
        raise HTTPException(status_code=500, detail="Error generating analysis data")


@hint_viewer_api_router.post("/api/send_screenshot")
async def send_screenshot(request: Request):
    """
    Принимает скриншот от веб-приложения и отправляет его в чат пользователя.
    """
    try:
        form_data = await request.form()
        photo = form_data.get("photo")

        if not photo:
            logger.warning("Screenshot request received without photo")
            raise HTTPException(status_code=400, detail="No photo provided")

        # Получаем chat_id из параметров запроса или из тела
        chat_id = request.query_params.get("chat_id")
        if not chat_id:
            # Попробуем получить из формы
            chat_id = form_data.get("chat_id")

        if not chat_id:
            logger.warning("Screenshot request received without chat_id")
            raise HTTPException(status_code=400, detail="No chat_id provided")

        logger.info(f"Sending screenshot to chat_id: {chat_id}")

        # Читаем файл
        photo_bytes = await photo.read()
        logger.debug(f"Screenshot file size: {len(photo_bytes)} bytes")

        # Создаем BufferedInputFile из байтов
        from aiogram.types import BufferedInputFile
        photo_file = BufferedInputFile(photo_bytes, filename="screenshot.png")

        # Отправляем фото в Telegram
        from bot.config import bot
        await bot.send_photo(
            chat_id=int(chat_id),
            photo=photo_file,
        )

        logger.info(f"Screenshot successfully sent to chat_id: {chat_id}")
        return {"status": "success"}

    except Exception as e:
        logger.error(f"Error sending screenshot to chat_id {chat_id if 'chat_id' in locals() else 'unknown'}: {e}")
        raise HTTPException(status_code=500, detail="Error sending screenshot")


async def process_batch_hint_files(message: Message, state: FSMContext, file_paths: list, chat_id, i18n, user_info:User):
    waiting_manager = WaitingMessageManager(chat_id, message.bot, i18n)
    await waiting_manager.start()

    try:
        # Обрабатываем все файлы параллельно
        tasks = []
        for mat_path in file_paths:
            task = asyncio.create_task(process_single_hint_file(mat_path, str(chat_id)))
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Отправляем сообщения для каждого успешно обработанного файла
        for idx, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Error processing {file_paths[idx]}: {result}")
                await message.reply(f"Ошибка при обработке файла {os.path.basename(file_paths[idx])}: {result}")
            else:
                game_id, has_games = result
                mat_path = file_paths[idx]
                fname = os.path.basename(mat_path)

                # Отправляем сообщение с ссылкой на веб-приложение
                if has_games:
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
                        f"Анализ файла {fname} завершен! Нажмите кнопку ниже для просмотра интерактивной визуализации:",
                        reply_markup=keyboard
                    )
                else:
                    await message.answer(f"Анализ файла {fname} завершен, но игр не найдено.")


    except Exception as e:
        logger.exception("Ошибка при пакетной обработке hint viewer")
        await message.reply("Ошибка при обработке файлов.", reply_markup=MainKeyboard.build(user_info.role, i18n))
    finally:
        await waiting_manager.stop()
        await state.clear()
        await state.set_state(GeneralStates.admin_panel)


async def process_single_hint_file(mat_path: str, user_id: str):
    """Обрабатывает один файл и возвращает game_id и флаг наличия игр"""
    game_id = random_filename(ext='')
    json_path = f"files/{game_id}.json"

    try:
        await asyncio.to_thread(process_mat_file, mat_path, json_path, user_id)

        # Проверяем наличие игр
        games_dir = json_path.rsplit('.', 1)[0] + "_games"
        has_games = os.path.exists(games_dir) and any(f.endswith('.json') for f in os.listdir(games_dir))

        return game_id, has_games
    except Exception as e:
        logger.error(f"Error processing {mat_path}: {e}")
        raise
    finally:
        # Удаляем оригинальный файл
        if os.path.exists(mat_path):
            os.remove(mat_path)