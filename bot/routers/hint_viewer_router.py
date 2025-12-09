import time
from aiogram import Router, F
from aiogram.filters import Command, CommandObject
from aiogram.types import (
    Message,
    WebAppInfo,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    FSInputFile,
    CallbackQuery,
    BufferedInputFile,
)
from aiogram.exceptions import TelegramAPIError
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from loguru import logger
import asyncio
import os
import json
import zipfile
import io
import shutil
import uuid
import requests
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import StateFilter

from fastapi import APIRouter, Request, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from rq import Queue
from rq.job import Job
from redis import Redis
from bot.common.service.sync_folder_service import SyncthingSync
from bot.db.redis import sync_redis_client, redis_client

from bot.common.filters.user_info import UserInfo
from bot.common.func.hint_viewer import (
    extract_match_length,
    process_mat_file,
    random_filename,
    extract_player_names,
    estimate_processing_time,
)
from bot.common.func.analiz_func import analyze_mat_file
from bot.common.func.func import (
    format_detailed_analysis,
    get_analysis_data as get_data,
)
from bot.common.func.progress_bar import ProgressBarMessageManager
from bot.common.kbds.inline.activate_promo import get_activate_promo_keyboard
from bot.common.kbds.inline.autoanalize import get_download_pdf_kb
from bot.common.kbds.markup.cancel import get_cancel_kb
from bot.routers.autoanalize.autoanaliz import analyze_file_by_path
from bot.common.func.waiting_message import WaitingMessageManager
from bot.common.kbds.markup.main_kb import MainKeyboard
from bot.common.general_states import GeneralStates
from bot.common.utils.i18n import get_all_locales_for_key
from bot.config import settings

from bot.config import translator_hub
from typing import TYPE_CHECKING

from bot.db.dao import UserDAO, DetailedAnalysisDAO
from bot.db.models import ServiceType, User
from bot.db.schemas import SDetailedAnalysis
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

if TYPE_CHECKING:
    from locales.stub import TranslatorRunner
from bot.config import admins
from bot.common.middlewares.single_user_middleware import LimitedUsersMiddleware

# Telegram router
hint_viewer_router = Router()

# FastAPI router for web interface
hint_viewer_api_router = APIRouter()
templates = Jinja2Templates(directory="bot/templates")
message_lock = asyncio.Lock()

redis_rq = Redis.from_url(settings.REDIS_URL, decode_responses=False)
task_queue = Queue("backgammon_analysis", connection=redis_rq, default_timeout=1800)
batch_queue = Queue(
    "backgammon_batch_analysis", connection=redis_rq, default_timeout=1800
)


class HintViewerStates(StatesGroup):
    choose_type = State()
    waiting_file = State()
    uploading_sequential = State()
    stats_player_selection = State()


syncthing_sync = SyncthingSync()


@hint_viewer_router.message(
    F.text.in_(
        get_all_locales_for_key(translator_hub, "keyboard-user-reply-hint_viewer")
    ),
    UserInfo(),
)
async def hint_viewer_start(message: Message, state: FSMContext):
    await state.set_state(HintViewerStates.choose_type)
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="Один файл", callback_data="hint_type:single")
    keyboard.button(text="Пакетный анализ", callback_data="hint_type:batch")
    keyboard.adjust(1)
    await message.answer("Выберите тип анализа:", reply_markup=keyboard.as_markup())


@hint_viewer_router.callback_query(
    F.data.startswith("hint_type:"), StateFilter(HintViewerStates.choose_type)
)
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
            "Присылайте .mat файлы или .zip архивы. Нажмите 'Завершить' когда закончите.",
            reply_markup=keyboard.as_markup(resize_keyboard=True),
        )
    await callback.answer()
    await callback.message.delete()


@hint_viewer_router.message(
    F.text == "Завершить",
    StateFilter(HintViewerStates.uploading_sequential),
    UserInfo(),
)
async def handle_batch_stop(
    message: Message, state: FSMContext, user_info: User, i18n, session_without_commit
):
    data = await state.get_data()
    file_paths = data.get("file_paths", [])
    if not file_paths:
        await message.answer(
            "Нет файлов для обработки.",
            reply_markup=MainKeyboard.build(user_info.role, i18n),
        )
        await state.clear()
        return
    await message.answer(
        "Начинаю обработку",
        reply_markup=MainKeyboard.build(user_info.role, i18n),
    )
    await process_batch_hint_files(
        message,
        state,
        file_paths,
        message.from_user.id,
        i18n,
        user_info,
        session_without_commit,
    )


@hint_viewer_router.message(
    F.document, StateFilter(HintViewerStates.uploading_sequential)
)
async def handle_sequential_hint_file(message: Message, state: FSMContext):
    async with message_lock:
        doc = message.document
        fname = doc.file_name
        if not (fname.lower().endswith(".mat") or fname.lower().endswith(".zip")):
            await message.reply("Пожалуйста, пришлите .mat файл или .zip архив.")
            return

        # Скачиваем файл
        temp_path = f"files/{fname}"
        os.makedirs("files", exist_ok=True)
        file = await message.bot.get_file(doc.file_id)
        with open(temp_path, "wb") as f:
            await message.bot.download_file(file.file_path, f)

        data = await state.get_data()
        file_paths = data.get("file_paths", [])

        if fname.lower().endswith(".zip"):
            # Распаковываем ZIP архив
            try:
                with zipfile.ZipFile(temp_path, "r") as zip_ref:
                    zip_ref.extractall("files")
                    # Добавляем все .mat файлы из распакованного архива
                    for extracted_file in zip_ref.namelist():
                        if extracted_file.lower().endswith(".mat"):
                            extracted_path = f"files/{extracted_file}"
                            if os.path.exists(extracted_path):
                                file_paths.append(extracted_path)
                # Удаляем временный ZIP файл
                os.remove(temp_path)
                await message.answer(
                    f"Архив распакован. Добавлено файлов: {len([p for p in file_paths if p.endswith('.mat')])}"
                )
            except Exception as e:
                logger.error(f"Error extracting ZIP: {e}")
                await message.reply("Ошибка при распаковке архива.")
                os.remove(temp_path)
                return
        else:
            # Обычный .mat файл
            file_paths.append(temp_path)
            await message.answer(f"Файл добавлен. Всего файлов: {len(file_paths)}")

        await state.update_data(file_paths=file_paths)


@hint_viewer_router.message(F.document, StateFilter(HintViewerStates.waiting_file))
async def hint_viewer_menu(
    message: Message, state: FSMContext, i18n, session_without_commit
):
    """Обработка загруженного .mat файла"""

    doc = message.document
    fname = doc.file_name

    if not fname.lower().endswith(".mat"):
        await message.reply("Пожалуйста, пришлите .mat файл.")
        return

    # === Генерируем уникальный ID для этой задачи ===
    game_id = random_filename(ext="")
    mat_path = f"files/{fname}"
    json_path = f"files/{game_id}.json"
    job_id = f"hint_{message.from_user.id}_{uuid.uuid4().hex[:8]}"

    try:
        file = await message.bot.get_file(doc.file_id)
        os.makedirs("files", exist_ok=True)

        with open(mat_path, "wb") as f:
            await message.bot.download_file(file.file_path, f)

        logger.info(f"Файл скачан локально: {mat_path}")

        if not await syncthing_sync.sync_and_wait(max_wait=30):
            logger.warning("Ошибка синхронизации Syncthing")

        if not await syncthing_sync.wait_for_file(mat_path, max_wait=30):
            await message.reply("❌ Файл не найден после синхронизации")
            return

        logger.info(f"✅ Файл готов к обработке: {mat_path}")

        with open(mat_path, "r", encoding="utf-8") as f:
            content = f.read()
        red_player, black_player = extract_player_names(content)
        estimated_time = estimate_processing_time(mat_path)
        job = task_queue.enqueue(
            "bot.workers.hint_worker.analyze_backgammon_job",
            mat_path,
            json_path,
            str(message.from_user.id),
            job_id=job_id,
        )

        # === Сохраняем информацию о задаче в Redis ===
        await redis_client.set(
            f"job_info:{job_id}",
            json.dumps(
                {
                    "game_id": game_id,
                    "mat_path": mat_path,
                    "json_path": json_path,
                    "red_player": red_player,
                    "black_player": black_player,
                    "user_id": message.from_user.id,
                }
            ),
            expire=3600,  # 1 час
        )

        # === Отправляем пользователю уведомление ===
        status_text = (
            f"✅ Файл принят!\n"
            f"Job ID: `{job_id}`\n"
            f"Примерное время: ~{estimated_time} сек\n"
            f"Статус: /status {job_id}"
        )

        await message.answer(status_text, parse_mode="Markdown")

        # === Сохраняем данные в состояние для проверки статуса ===
        await state.update_data(
            job_id=job_id,
            game_id=game_id,
            mat_path=mat_path,
            json_path=json_path,
            red_player=red_player,
            black_player=black_player,
        )

        # === Запускаем фоновую проверку статуса ===
        asyncio.create_task(
            check_job_status(message, job_id, state, i18n, session_without_commit)
        )

    except Exception as e:
        logger.exception(f"Error processing hint viewer file: {e}")
        await message.reply(f"❌ Ошибка при обработке файла: {e}")
        await state.clear()


@hint_viewer_router.callback_query(F.data.startswith("show_stats:"), UserInfo())
async def handle_show_stats(
    callback: CallbackQuery,
    state: FSMContext,
    user_info: User,
    i18n,
    session_without_commit: AsyncSession,
):
    game_id = callback.data.split(":")[1]
    mat_path = await redis_client.get(f"mat_path:{game_id}")

    if not mat_path:
        await callback.answer("Файл не найден.")
        return
    waiting_manager = WaitingMessageManager(callback.from_user.id, callback.bot, i18n)
    try:
        await waiting_manager.start()
        with open(mat_path, "r", encoding="utf-8") as f:
            content = f.read()
        match_length = extract_match_length(content)
        dao = UserDAO(session_without_commit)
        if match_length == 0:
            balance = await dao.get_total_analiz_balance(
                user_info.id, service_type=ServiceType.MONEYGAME
            )
            analysis_type = "moneygame"
        else:
            balance = await dao.get_total_analiz_balance(
                user_info.id, service_type=ServiceType.MATCH
            )
            analysis_type = "match"
        if balance == 0:
            await callback.message.answer(
                i18n.auto.analyze.not_ebought_balance(),
                reply_markup=get_activate_promo_keyboard(i18n),
            )
            return

        await callback.answer()

        result = await analyze_file_by_path(
            mat_path,
            "mat",
            user_info,
            session_without_commit,
            i18n,
            callback,
            analysis_type,
            forward_message=False,
        )

        if isinstance(result, tuple) and len(result) == 3:
            # Multiple players
            analysis_data, new_file_path, player_names = result
            await state.update_data(
                analysis_data=analysis_data,
                file_name=os.path.basename(new_file_path),
                file_path=new_file_path,
                player_names=player_names,
                game_id=game_id,
            )

            keyboard = InlineKeyboardBuilder()
            for player in player_names:
                keyboard.button(text=player, callback_data=f"hint_player:{player}")
            keyboard.adjust(1)
            await callback.message.answer(
                i18n.auto.analyze.complete(),
                reply_markup=keyboard.as_markup(),
            )
        else:
            # Single player
            formatted_analysis, new_file_path = result
            await callback.message.answer(
                f"{formatted_analysis}\n\n",
                parse_mode="HTML",
                reply_markup=MainKeyboard.build(user_info.role, i18n),
            )
            # Удаляем файл
            if os.path.exists(new_file_path):
                os.remove(new_file_path)
            await redis_client.delete(f"mat_path:{game_id}")
        await waiting_manager.stop()

    except Exception as e:
        logger.error(f"Ошибка при показе статистики: {e}")
        await callback.answer("Ошибка при обработке статистики.")


@hint_viewer_router.callback_query(F.data.startswith("hint_player:"), UserInfo())
async def handle_hint_player_selection(
    callback: CallbackQuery,
    state: FSMContext,
    session_without_commit: AsyncSession,
    user_info: User,
    i18n,
):
    try:
        data = await state.get_data()
        analysis_data = data["analysis_data"]
        file_name = data["file_name"]
        file_path = data["file_path"]
        game_id = data["game_id"]

        selected_player = callback.data.split(":")[1]
        user_dao = UserDAO(session_without_commit)
        if (
            not user_info.player_username
            or user_info.player_username != selected_player
        ):
            await user_dao.update(user_info.id, {"player_username": selected_player})
            logger.info(
                f"Updated player_username for user {user_info.id} to {selected_player}"
            )

        game_id_new = f"auto_{user_info.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        dao = DetailedAnalysisDAO(session_without_commit)

        player_data = {
            "user_id": user_info.id,
            "player_name": selected_player,
            "file_name": file_name,
            "file_path": file_path,
            "game_id": game_id_new,
            **get_data(analysis_data, selected_player),
        }

        await dao.add(SDetailedAnalysis(**player_data))

        formatted_analysis = format_detailed_analysis(get_data(analysis_data), i18n)

        await callback.message.delete()
        await callback.message.answer(
            f"{formatted_analysis}\n\n",
            parse_mode="HTML",
            reply_markup=MainKeyboard.build(user_role=user_info.role, i18n=i18n),
        )
        await callback.message.answer(
            i18n.auto.analyze.ask_pdf(), reply_markup=get_download_pdf_kb(i18n, "solo")
        )
        await session_without_commit.commit()

        await redis_client.delete(f"mat_path:{game_id}")
        await state.clear()

    except Exception as e:
        await session_without_commit.rollback()
        logger.error(f"Ошибка при сохранении выбора игрока: {e}")
        await callback.message.answer(i18n.auto.analyze.error.save())


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
            raise FileNotFoundError(
                f"JSON файл для игры {game_num} в {game_id} не найден"
            )
    else:
        # Загружаем общий файл с информацией о всех играх
        path = f"files/{game_id}.json"
        if not os.path.exists(path):
            raise FileNotFoundError(f"JSON файл для {game_id} не найден")

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Scores будут загружаться по требованию в JavaScript

        return data


@hint_viewer_api_router.get("/hint-viewer")
async def get_hint_viewer_web(request: Request, game_id: str = None):
    """
    Возвращает HTML-страницу интерактивного просмотра подсказок.
    """
    if not game_id:
        raise HTTPException(status_code=400, detail="game_id parameter is required")

    return templates.TemplateResponse(
        "hint_viewer.html", {"request": request, "game_id": game_id}
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
        logger.error(
            f"Error sending screenshot to chat_id {chat_id if 'chat_id' in locals() else 'unknown'}: {e}"
        )
        raise HTTPException(status_code=500, detail="Error sending screenshot")


@hint_viewer_api_router.post("/api/save_screenshot")
async def save_screenshot(request: Request):
    """
    Сохраняет скриншот в буфер для пользователя.
    """
    try:
        form_data = await request.form()
        photo = form_data.get("photo")

        if not photo:
            logger.warning("Save screenshot request received without photo")
            raise HTTPException(status_code=400, detail="No photo provided")

        chat_id = request.query_params.get("chat_id")
        if not chat_id:
            chat_id = form_data.get("chat_id")

        if not chat_id:
            logger.warning("Save screenshot request received without chat_id")
            raise HTTPException(status_code=400, detail="No chat_id provided")

        # Создаем директорию для буфера скриншотов
        buffer_dir = f"files/screenshots/{chat_id}"
        os.makedirs(buffer_dir, exist_ok=True)

        # Сохраняем файл с timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"screenshot_{timestamp}.png"
        filepath = os.path.join(buffer_dir, filename)

        photo_bytes = await photo.read()
        with open(filepath, "wb") as f:
            f.write(photo_bytes)

        logger.info(f"Screenshot saved to buffer: {filepath}")
        return {"status": "success"}

    except Exception as e:
        logger.error(
            f"Error saving screenshot for chat_id {chat_id if 'chat_id' in locals() else 'unknown'}: {e}"
        )
        raise HTTPException(status_code=500, detail="Error saving screenshot")


@hint_viewer_api_router.post("/api/upload_screenshots")
async def upload_screenshots(request: Request):
    """
    Создает ZIP архив из буфера скриншотов и отправляет в Telegram.
    """
    try:
        chat_id = request.query_params.get("chat_id")
        if not chat_id:
            raise HTTPException(status_code=400, detail="No chat_id provided")

        buffer_dir = f"files/screenshots/{chat_id}"
        if not os.path.exists(buffer_dir):
            raise HTTPException(status_code=404, detail="No screenshots in buffer")

        screenshots = [f for f in os.listdir(buffer_dir) if f.endswith(".png")]
        if not screenshots:
            raise HTTPException(status_code=404, detail="No screenshots in buffer")

        # Создаем ZIP архив
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for screenshot in screenshots:
                filepath = os.path.join(buffer_dir, screenshot)
                zip_file.write(filepath, screenshot)

        zip_buffer.seek(0)
        zip_data = zip_buffer.getvalue()

        # Отправляем ZIP в Telegram
        from aiogram.types import BufferedInputFile
        from bot.config import bot

        zip_file = BufferedInputFile(zip_data, filename="screenshots.zip")
        await bot.send_document(
            chat_id=int(chat_id),
            document=zip_file,
            caption=f"Архив с {len(screenshots)} скриншотами",
        )

        # Очищаем буфер
        shutil.rmtree(buffer_dir)

        logger.info(
            f"Screenshots ZIP sent to chat_id: {chat_id}, {len(screenshots)} files"
        )
        return {"status": "success"}

    except Exception as e:
        logger.error(
            f"Error uploading screenshots for chat_id {chat_id if 'chat_id' in locals() else 'unknown'}: {e}"
        )
        raise HTTPException(status_code=500, detail="Error uploading screenshots")


async def check_batch_job_status(
    message: Message,
    job_ids: list,  # Список ID задач
    batch_id: str,  # ID батча для отслеживания
    i18n,
    session_without_commit,
):
    """
    Фоновая задача для проверки статуса анализа батча файлов.
    Проверяет все задачи и отправляет результаты по мере завершения.
    """
    completed_jobs = {}
    failed_jobs = {}
    total_jobs = len(job_ids)

    try:
        logger.info(
            f"Starting batch monitor for {total_jobs} files, batch_id={batch_id}"
        )

        while True:
            try:
                all_finished = True
                finished_count = 0
                failed_count = 0

                for job_id in job_ids:
                    if job_id in completed_jobs or job_id in failed_jobs:
                        finished_count += 1
                        if job_id in failed_jobs:
                            failed_count += 1
                        continue

                    try:
                        job = Job.fetch(job_id, connection=redis_rq)

                        if job.is_finished:
                            # Получаем информацию о задаче
                            job_info_json = await redis_client.get(f"job_info:{job_id}")
                            if job_info_json:
                                job_info = json.loads(job_info_json)
                            else:
                                job_info = {}

                            # === FIX: Правильная обработка результата ===
                            result_raw = job.result

                            if result_raw is None:
                                logger.error(f"Job {job_id} returned None result")
                                failed_jobs[job_id] = "Пустой результат"
                                finished_count += 1
                                failed_count += 1
                                continue

                            # Преобразуем результат в dict если нужно
                            if isinstance(result_raw, dict):
                                result = result_raw
                            elif isinstance(result_raw, bytes):
                                try:
                                    result = json.loads(result_raw.decode("utf-8"))
                                except (json.JSONDecodeError, UnicodeDecodeError) as e:
                                    logger.error(
                                        f"Failed to parse job result bytes: {e}"
                                    )
                                    failed_jobs[job_id] = (
                                        f"Ошибка обработки: {str(e)[:50]}"
                                    )
                                    finished_count += 1
                                    failed_count += 1
                                    continue
                            elif isinstance(result_raw, str):
                                try:
                                    result = json.loads(result_raw)
                                except json.JSONDecodeError as e:
                                    logger.error(
                                        f"Failed to parse job result string: {e}"
                                    )
                                    failed_jobs[job_id] = (
                                        f"Ошибка обработки: {str(e)[:50]}"
                                    )
                                    finished_count += 1
                                    failed_count += 1
                                    continue
                            else:
                                logger.error(
                                    f"Unexpected result type: {type(result_raw)}"
                                )
                                failed_jobs[job_id] = "Неожиданный тип результата"
                                finished_count += 1
                                failed_count += 1
                                continue

                            # Теперь result гарантированно dict
                            if result.get("status") == "success":
                                logger.info(
                                    f"Batch job {job_id} completed successfully"
                                )
                                completed_jobs[job_id] = {
                                    "result": result,
                                    "job_info": job_info,
                                }
                                finished_count += 1

                                # Отправляем результат пользователю
                                game_id = job_info.get("game_id", "unknown")
                                red_player = job_info.get("red_player", "Red")
                                black_player = job_info.get("black_player", "Black")
                                fname = os.path.basename(
                                    job_info.get("mat_path", "unknown")
                                )

                                if result.get("has_games"):
                                    mini_app_url_all = f"{settings.MINI_APP_URL}/hint-viewer?game_id={game_id}&error=0"
                                    mini_app_url_both_errors = f"{settings.MINI_APP_URL}/hint-viewer?game_id={game_id}&error=1"
                                    mini_app_url_red_errors = f"{settings.MINI_APP_URL}/hint-viewer?game_id={game_id}&error=2"
                                    mini_app_url_black_errors = f"{settings.MINI_APP_URL}/hint-viewer?game_id={game_id}&error=3"

                                    keyboard = InlineKeyboardMarkup(
                                        inline_keyboard=[
                                            [
                                                InlineKeyboardButton(
                                                    text="Просмотр всех ходов",
                                                    web_app=WebAppInfo(
                                                        url=mini_app_url_all
                                                    ),
                                                ),
                                            ],
                                            [
                                                InlineKeyboardButton(
                                                    text="Только ошибки (оба игрока)",
                                                    web_app=WebAppInfo(
                                                        url=mini_app_url_both_errors
                                                    ),
                                                ),
                                            ],
                                            [
                                                InlineKeyboardButton(
                                                    text=f"Только ошибки ({red_player})",
                                                    web_app=WebAppInfo(
                                                        url=mini_app_url_red_errors
                                                    ),
                                                ),
                                            ],
                                            [
                                                InlineKeyboardButton(
                                                    text=f"Только ошибки ({black_player})",
                                                    web_app=WebAppInfo(
                                                        url=mini_app_url_black_errors
                                                    ),
                                                ),
                                            ],
                                            [
                                                InlineKeyboardButton(
                                                    text="Показать статистику игры",
                                                    callback_data=f"show_stats:{game_id}",
                                                ),
                                            ],
                                        ]
                                    )

                                    await message.answer(
                                        f"✅ **{fname}** обработан!\n{red_player} vs {black_player}",
                                        parse_mode="Markdown",
                                    )
                                    await message.answer(
                                        "Выберите вариант просмотра ошибок:",
                                        reply_markup=keyboard,
                                    )
                                else:
                                    await message.answer(
                                        f"✅ **{fname}** обработан, но игр не найдено.",
                                        parse_mode="Markdown",
                                    )
                            else:
                                # Ошибка при обработке
                                error_msg = result.get("error", "Неизвестная ошибка")
                                failed_jobs[job_id] = error_msg
                                finished_count += 1
                                failed_count += 1

                                fname = os.path.basename(
                                    job_info.get("mat_path", "unknown")
                                )
                                await message.answer(
                                    f"❌ **{fname}**: {error_msg}",
                                    parse_mode="Markdown",
                                )

                        elif job.is_failed:
                            logger.error(f"Batch job {job_id} failed: {job.exc_info}")
                            failed_jobs[job_id] = "Критическая ошибка"
                            finished_count += 1
                            failed_count += 1

                            job_info_json = await redis_client.get(f"job_info:{job_id}")
                            if job_info_json:
                                job_info = json.loads(job_info_json)
                                fname = os.path.basename(
                                    job_info.get("mat_path", "unknown")
                                )
                                await message.answer(
                                    f"❌ **{fname}**: Критическая ошибка обработки",
                                    parse_mode="Markdown",
                                )
                        else:
                            all_finished = False

                    except Exception as e:
                        logger.warning(
                            f"Error checking batch job {job_id}: {e}", exc_info=True
                        )
                        all_finished = False

                # Проверяем прогресс
                progress = f"{finished_count}/{total_jobs} файлов обработано"
                logger.info(f"Batch progress: {progress} (failed: {failed_count})")

                # Если все задачи завершены
                if all_finished:
                    logger.info(
                        f"Batch {batch_id} completed. Finished: {finished_count}, Failed: {failed_count}"
                    )

                    summary_msg = (
                        f"🎉 **Пакетная обработка завершена!**\n\n"
                        f"✅ Успешно: {finished_count - failed_count}\n"
                        f"❌ Ошибок: {failed_count}\n"
                        f"📊 Всего: {total_jobs}"
                    )
                    await message.answer(summary_msg, parse_mode="Markdown")
                    break

                await asyncio.sleep(5)  # Проверяем каждые 5 секунд

            except Exception as e:
                logger.warning(f"Error in batch monitor loop: {e}", exc_info=True)
                await asyncio.sleep(5)
                continue

    except Exception as e:
        logger.exception(f"Error in check_batch_job_status for batch {batch_id}")
        await message.answer("❌ Ошибка при мониторинге батча")


async def process_batch_hint_files(
    message: Message,
    state: FSMContext,
    file_paths: list,
    chat_id,
    i18n,
    user_info: User,
    session_without_commit,
):
    """
    Обрабатывает пакет файлов, отправляя каждый на анализ в RQ queue.
    """
    batch_id = f"batch_{chat_id}_{uuid.uuid4().hex[:8]}"
    job_ids = []

    try:
        total_files = len(file_paths)
        await message.answer(f"📋 Начинаю отправку {total_files} файлов на анализ...")

        # Отправляем все файлы в очередь
        for idx, mat_path in enumerate(file_paths):
            fname = os.path.basename(mat_path)

            try:
                # === Генерируем уникальный ID для этой задачи ===
                game_id = random_filename(ext="")
                json_path = f"files/{game_id}.json"
                job_id = f"batch_{batch_id}_{idx}_{uuid.uuid4().hex[:8]}"

                # Извлекаем имена игроков
                with open(mat_path, "r", encoding="utf-8") as f:
                    content = f.read()
                if not await syncthing_sync.sync_and_wait(max_wait=30):
                    logger.warning("Ошибка синхронизации Syncthing")

                if not await syncthing_sync.wait_for_file(mat_path, max_wait=30):
                    await message.reply("❌ Файл не найден после синхронизации")
                    return

                red_player, black_player = extract_player_names(content)

                # === Отправляем задачу в очередь ===
                job = batch_queue.enqueue(
                    "bot.workers.hint_worker.analyze_backgammon_job",
                    mat_path,
                    json_path,
                    str(message.from_user.id),
                    job_id=job_id,
                )

                job_ids.append(job_id)

                # === Сохраняем информацию о задаче в Redis ===
                await redis_client.set(
                    f"job_info:{job_id}",
                    json.dumps(
                        {
                            "batch_id": batch_id,
                            "game_id": game_id,
                            "mat_path": mat_path,
                            "json_path": json_path,
                            "red_player": red_player,
                            "black_player": black_player,
                            "user_id": message.from_user.id,
                            "file_index": idx + 1,
                            "total_files": total_files,
                        }
                    ),
                    expire=3600,  # 1 час
                )

                logger.info(
                    f"Batch file {idx + 1}/{total_files} queued: {fname} (job_id={job_id})"
                )

            except Exception as e:
                logger.error(f"Error queuing batch file {fname}: {e}")
                await message.answer(
                    f"⚠️ Ошибка при отправке файла **{fname}**: {e}",
                    parse_mode="Markdown",
                )
                continue

        if not job_ids:
            await message.answer("❌ Не удалось отправить ни один файл на анализ")
            await state.clear()
            return

        # === Отправляем сводку ===
        summary = (
            f"📤 Отправлено на анализ: **{len(job_ids)}/{total_files}** файлов\n\n"
        )
        summary += "⏳ Мониторю прогресс...\n"
        summary += "💡 Результаты будут отправлены по мере готовности"

        await message.answer(summary, parse_mode="Markdown")

        # === Запускаем фоновый мониторинг статуса ===
        asyncio.create_task(
            check_batch_job_status(
                message, job_ids, batch_id, i18n, session_without_commit
            )
        )

        await state.clear()

    except Exception as e:
        logger.exception(f"Error in process_batch_hint_files: {e}")
        await message.answer(f"❌ Ошибка при обработке батча: {e}")
        await state.clear()


async def check_job_status(
    message: Message, job_id: str, state: FSMContext, i18n, session_without_commit
):
    """
    Фоновая задача для проверки статуса анализа.
    Проверяет Redis каждые 3 секунды и отправляет результат когда готов.
    """
    try:
        # Получаем информацию о задаче
        job_info_json = await redis_client.get(f"job_info:{job_id}")
        if not job_info_json:
            await message.answer("❌ Информация о задаче не найдена")
            return

        job_info = json.loads(job_info_json)

        # Начинаем проверку
        while True:
            try:
                job = Job.fetch(job_id, connection=redis_rq)

                if job.is_finished:
                    # === ЗАДАЧА ЗАВЕРШЕНА ===
                    result = job.result

                    if result["status"] == "success":
                        logger.info(f"Job {job_id} completed successfully")

                        # Уменьшаем баланс пользователя
                        await UserDAO(session_without_commit).decrease_analiz_balance(
                            user_id=message.from_user.id, service_type="HINTS"
                        )
                        await session_without_commit.commit()

                        # Сохраняем mat_path для статистики
                        game_id = job_info["game_id"]
                        await redis_client.set(
                            f"mat_path:{game_id}", result["mat_path"], expire=3600
                        )

                        # Создаём ZIP архив если есть игры
                        games_dir = result["games_dir"]
                        if os.path.exists(games_dir) and result["has_games"]:
                            # Создаём ZIP
                            zip_buffer = io.BytesIO()
                            with zipfile.ZipFile(zip_buffer, "w") as zip_file:
                                for root, _, files in os.walk(games_dir):
                                    for file in files:
                                        file_path = os.path.join(root, file)
                                        arcname = os.path.relpath(file_path, games_dir)
                                        zip_file.write(file_path, arcname)

                            zip_buffer.seek(0)

                            # Отправляем ZIP если пользователь админ
                            if message.from_user.id in admins:
                                from aiogram.types import BufferedInputFile

                                zip_file = BufferedInputFile(
                                    zip_buffer.getvalue(),
                                    filename=f"{game_id}_analysis.zip",
                                )
                                await message.answer_document(
                                    document=zip_file, caption="Архив с анализом игр"
                                )

                            # Отправляем кнопки для просмотра
                            red_player = job_info["red_player"]
                            black_player = job_info["black_player"]

                            mini_app_url_all = f"{settings.MINI_APP_URL}/hint-viewer?game_id={game_id}&error=0"
                            mini_app_url_both_errors = f"{settings.MINI_APP_URL}/hint-viewer?game_id={game_id}&error=1"
                            mini_app_url_red_errors = f"{settings.MINI_APP_URL}/hint-viewer?game_id={game_id}&error=2"
                            mini_app_url_black_errors = f"{settings.MINI_APP_URL}/hint-viewer?game_id={game_id}&error=3"

                            keyboard = InlineKeyboardMarkup(
                                inline_keyboard=[
                                    [
                                        InlineKeyboardButton(
                                            text="Просмотр всех ходов",
                                            web_app=WebAppInfo(url=mini_app_url_all),
                                        ),
                                    ],
                                    [
                                        InlineKeyboardButton(
                                            text="Только ошибки (оба игрока)",
                                            web_app=WebAppInfo(
                                                url=mini_app_url_both_errors
                                            ),
                                        ),
                                    ],
                                    [
                                        InlineKeyboardButton(
                                            text=f"Только ошибки ({red_player})",
                                            web_app=WebAppInfo(
                                                url=mini_app_url_red_errors
                                            ),
                                        ),
                                    ],
                                    [
                                        InlineKeyboardButton(
                                            text=f"Только ошибки ({black_player})",
                                            web_app=WebAppInfo(
                                                url=mini_app_url_black_errors
                                            ),
                                        ),
                                    ],
                                    [
                                        InlineKeyboardButton(
                                            text="Показать статистику игры",
                                            callback_data=f"show_stats:{game_id}",
                                        ),
                                    ],
                                ]
                            )

                            await message.answer(
                                f"✅ Анализ завершен!\n{red_player} vs {black_player}\n"
                                f"Выберите вариант просмотра ошибок:",
                                reply_markup=keyboard,
                            )
                        else:
                            await message.answer(
                                "✅ Анализ завершен, но игр не найдено."
                            )

                    else:
                        # === ОШИБКА ===
                        error_msg = result.get("error", "Неизвестная ошибка")
                        await message.answer(f"❌ Ошибка при анализе: {error_msg}")

                    await state.clear()
                    break

                elif job.is_failed:
                    # === ЗАДАЧА ПРОВАЛИЛАСЬ ===
                    await message.answer("❌ Анализ завершился с критической ошибкой")
                    await state.clear()
                    break

                elif job.is_queued:
                    # === ЗАДАЧА В ОЧЕРЕДИ ===
                    position = job.get_position()
                    await asyncio.sleep(3)
                    continue

                elif job.is_started:
                    # === ЗАДАЧА ВЫПОЛНЯЕТСЯ ===
                    await asyncio.sleep(5)  # Проверяем чаще когда выполняется
                    continue

                else:
                    await asyncio.sleep(3)
                    continue

            except Exception as e:
                logger.warning(f"Error checking job status: {e}")
                await asyncio.sleep(5)
                continue

    except Exception as e:
        logger.exception(f"Error in check_job_status for {job_id}")
        await message.answer("❌ Ошибка при проверке статуса задачи")
