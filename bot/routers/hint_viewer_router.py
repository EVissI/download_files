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

from rq import Queue, Worker
from rq.registry import StartedJobRegistry
from rq.job import Job
from redis import Redis
from bot.common.service.sync_folder_service import SyncthingSync
from bot.db.redis import sync_redis_client, redis_client
from bot.db.schemas import SUser
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

from bot.db.dao import UserDAO, DetailedAnalysisDAO, MessagesTextsDAO
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


class SupportStates(StatesGroup):
    waiting_reply = State()


syncthing_sync = SyncthingSync()


WORKER_COUNT_CACHE_KEY = "cache:worker_count"
WORKER_CACHE_TTL = 10


async def get_worker_count_cached(redis_conn: Redis, queue_name: str) -> int:
    """
    Версия для синхронного Redis клиента (redis-py).
    """
    cached_count = redis_conn.get(WORKER_COUNT_CACHE_KEY)

    if cached_count is not None:
        return int(cached_count)

    def fetch_workers():
        q = Queue(queue_name, connection=redis_conn)
        return len(Worker.all(queue=q))

    count = await asyncio.to_thread(fetch_workers)

    redis_conn.set(WORKER_COUNT_CACHE_KEY, count, ex=WORKER_CACHE_TTL)

    return count


async def get_queue_position_message(
    redis_conn: Redis, queue_names: list[str], session, user_info: User
) -> str | None:
    """
    Проверяет нагрузку и возвращает сообщение о позиции в очереди.
    Использует кэшированное количество воркеров.
    """
    try:
        total_waiting = 0
        total_active = 0
        message_dao = MessagesTextsDAO(session)
        for q_name in queue_names:
            q = Queue(q_name, connection=redis_conn)
            registry = StartedJobRegistry(queue=q)

            total_waiting += q.count
            total_active += len(registry)

        worker_count = await get_worker_count_cached(redis_conn, queue_names[0])
        logger.debug(
            f"Queue status - Waiting: {total_waiting}, Active: {total_active}, Workers: {worker_count}"
        )
        if worker_count == 0:
            return await message_dao.get_text(
                "hint_viewer_queue_servers_down", user_info.lang_code
            )
        total_q = total_waiting + total_active
        if total_q >= worker_count:

            position = total_waiting + 1
            msg = await message_dao.get_text(
                "hint_viewer_queue_position", user_info.lang_code, position=position
            )
            return msg
        return None

    except Exception as e:
        logger.error(f"Error checking queue: {e}")
        return None


def can_enqueue_job(user_id: int) -> bool:
    """
    Проверяет, может ли пользователь добавить новую задачу в очередь.
    """
    active_jobs = sync_redis_client.smembers(f"user_active_jobs:{user_id}")
    return len(active_jobs) == 0


def add_active_job(user_id: int, job_id: str):
    """
    Добавляет job_id в активные задачи пользователя.
    """
    sync_redis_client.sadd(f"user_active_jobs:{user_id}", job_id)
    sync_redis_client.expire(f"user_active_jobs:{user_id}", 3600)
    logger.info(f"Added active job: user_id={user_id}, job_id={job_id}")


def remove_active_job(user_id: int, job_id: str):
    """
    Удаляет job_id из активных задач пользователя.
    """
    sync_redis_client.srem(f"user_active_jobs:{user_id}", job_id)
    logger.info(f"Removed active job: user_id={user_id}, job_id={job_id}")


@hint_viewer_router.message(
    F.text.in_(
        get_all_locales_for_key(translator_hub, "keyboard-user-reply-hint_viewer")
    ),
    UserInfo(),
)
async def hint_viewer_start(message: Message, state: FSMContext, user_info: User, session_without_commit: AsyncSession):
    message_dao = MessagesTextsDAO(session_without_commit)
    await state.set_state(HintViewerStates.choose_type)
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text=await message_dao.get_text("button_error_single", user_info.lang_code), callback_data="hint_type:single")
    keyboard.button(text=await message_dao.get_text("button_error_batch", user_info.lang_code), callback_data="hint_type:batch")
    keyboard.adjust(1)
    await message.answer(await message_dao.get_text("hint_viewer_start", user_info.lang_code), reply_markup=keyboard.as_markup())


@hint_viewer_router.callback_query(
    F.data.startswith("hint_type:"), StateFilter(HintViewerStates.choose_type), UserInfo()
)
async def handle_hint_type_selection(callback: CallbackQuery, state: FSMContext, user_info: User, session_without_commit: AsyncSession):
    message_dao = MessagesTextsDAO(session_without_commit)
    hint_type = callback.data.split(":")[1]
    if hint_type == "single":
        await state.set_state(HintViewerStates.waiting_file)
        await callback.message.answer(await message_dao.get_text("hint_viewer_single_upload", user_info.lang_code))
    else:
        await state.set_state(HintViewerStates.uploading_sequential)
        await state.update_data(file_paths=[])
        keyboard = ReplyKeyboardBuilder()
        keyboard.button(text=await message_dao.get_text("hint_viewer_batch_upload_stop", user_info.lang_code))
        await callback.message.answer(
            await message_dao.get_text("hint_viewer_batch_upload", user_info.lang_code),
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
    message_dao = MessagesTextsDAO(session_without_commit)
    data = await state.get_data()
    file_paths = data.get("file_paths", [])
    if not file_paths:
        await message.answer(
            await message_dao.get_text("hint_viewer_batch_no_file", user_info.lang_code),
            reply_markup=MainKeyboard.build(user_info.role, i18n),
        )
        await state.clear()
        return
    await message.answer(
        await message_dao.get_text("hint_viewer_batch_start", user_info.lang_code),
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
async def handle_sequential_hint_file(message: Message, state: FSMContext, user_info: User, session_without_commit: AsyncSession):
    message_dao = MessagesTextsDAO(session_without_commit)
    async with message_lock:
        doc = message.document
        fname = doc.file_name
        if not (fname.lower().endswith(".mat") or fname.lower().endswith(".zip")):
            await message.reply(await message_dao.get_text("hint_viewer_batch_file_extension_error", user_info.lang_code),)
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
                    await message_dao.get_text("hint_viewer_batch_file_extracted", user_info.lang_code, zip_size=len([p for p in file_paths if p.endswith('.mat')])),
                )
            except Exception as e:
                logger.error(f"Error extracting ZIP: {e}")
                await message.reply(await message_dao.get_text("hint_viewer_batch_file_extracted_error", user_info.lang_code))
                os.remove(temp_path)
                return
        else:
            # Обычный .mat файл
            file_paths.append(temp_path)
            await message.answer(await message_dao.get_text("hint_viewer_batch_file_added", user_info.lang_code, file_count=len(file_paths)))

        await state.update_data(file_paths=file_paths)


@hint_viewer_router.message(F.document, StateFilter(HintViewerStates.waiting_file), UserInfo(),)
async def hint_viewer_menu(
    message: Message, state: FSMContext, user_info: User, i18n, session_without_commit
):
    """Обработка загруженного .mat файла"""
    message_dao = MessagesTextsDAO(session_without_commit)
    doc = message.document
    fname = doc.file_name

    if not fname.lower().endswith(".mat"):
        await message.reply(await message_dao.get_text("hint_viewer_sin_file_ext_error", user_info.lang_code))
        return

    # === Генерируем уникальный ID для этой задачи ===
    game_id = random_filename(ext="")
    mat_path = f"files/{fname}"
    json_path = f"files/{game_id}.json"
    job_id = f"hint_{message.from_user.id}_{uuid.uuid4().hex[:8]}"

    try:
        if not can_enqueue_job(message.from_user.id):
            await message.answer(
                await message_dao.get_text("hint_viewer_sin_active_job_err", user_info.lang_code)
            )
            await state.clear()
            return

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
            game_id=game_id,
        )

        # Сохраняем mat_path сразу
        await redis_client.set(f"mat_path:{game_id}", mat_path, expire=86400)

        add_active_job(message.from_user.id, job_id)
        logger.info(
            f"Added active job: user_id={message.from_user.id}, job_id={job_id}"
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
            expire=3600,
        )
        queue_warning = await get_queue_position_message(
            redis_rq, ["backgammon_analysis", "backgammon_batch_analysis"], session_without_commit, user_info
        )
        if queue_warning:
            user_dao = UserDAO(session_without_commit)
            admins = await user_dao.find_all(filters=SUser(role=User.Role.ADMIN.value))
            for admin in admins:
                try:
                    await message.bot.send_message(
                        chat_id=admin.id,
                        text=f"Пользователь в очереди на анализ ошибок. Его сообщение:{queue_warning}\n",
                    )
                except Exception as e:
                    logger.error(
                        f"Не удалось отправить уведомление админу {admin.id}: {e}"
                    )
            await message.answer(queue_warning)

        status_text = await message_dao.get_text("hint_viewer_sin_file_accepted", user_info.lang_code, estimated_time=estimated_time)
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
            check_job_status(message, job_id, state, i18n, session_without_commit, user_info)
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

        if isinstance(result, tuple) and len(result) == 4:
            # Multiple players
            analysis_data, new_file_path, player_names,duration = result
            await state.update_data(
                analysis_data=analysis_data,
                file_name=os.path.basename(new_file_path),
                file_path=new_file_path,
                player_names=player_names,
                duration=duration,
                game_id=game_id,
            )

            # Update mat_path in Redis with the new file path
            await redis_client.set(f"mat_path:{game_id}", new_file_path, expire=7200)

            keyboard = InlineKeyboardBuilder()
            for player in player_names:
                keyboard.button(text=player, callback_data=f"hint_player:{player}")
            keyboard.adjust(1)
            await callback.message.answer(
                i18n.auto.analyze.complete(),
                reply_markup=keyboard.as_markup(),
            )
        else:
            formatted_analysis, new_file_path = result
            # Update mat_path in Redis with the new file path
            await redis_client.set(f"mat_path:{game_id}", new_file_path, expire=7200)
            await callback.message.answer(
                f"{formatted_analysis}\n\n",
                parse_mode="HTML",
                reply_markup=MainKeyboard.build(user_info.role, i18n),
            )
            await callback.message.answer(
                i18n.auto.analyze.ask_pdf(),
                reply_markup=get_download_pdf_kb(i18n, "solo"),
            )

    except Exception as e:
        logger.error(f"Ошибка при показе статистики: {e}")
        await callback.answer("Ошибка при обработке статистики.")
    finally:
        await waiting_manager.stop()


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
        path = f"files/{game_id}.json"
        if not os.path.exists(path):
            raise FileNotFoundError(f"JSON файл для {game_id} не найден")

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

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


@hint_viewer_api_router.post("/api/send_to_support")
async def send_to_support(request: Request):
    """
    Принимает скриншот и описание проблемы, отправляет в техподдержку с рейлимитом.
    """
    try:
        form_data = await request.form()
        photo = form_data.get("photo")
        text = form_data.get("text", "Без описания")
        chat_id = request.query_params.get("chat_id") or form_data.get("chat_id")

        if not chat_id:
            logger.warning("Support request received without chat_id")
            raise HTTPException(status_code=400, detail="No chat_id provided")

        if not photo:
            logger.warning("Support request received without photo")
            raise HTTPException(status_code=400, detail="No photo provided")

        # Рейлимит: 5 запросов за 10 минут (600 секунд)
        rate_limit_key = f"rate_limit:support:{chat_id}"
        current_requests = await redis_client.get(rate_limit_key)

        if current_requests and int(current_requests) >= 5:
            ttl = await redis_client.ttl(rate_limit_key)
            minutes = ttl // 60
            seconds = ttl % 60
            raise HTTPException(
                status_code=429,
                detail={
                    "message": "Слишком много запросов",
                    "retry_after": ttl,
                    "wait_text": (
                        f"{minutes} мин {seconds} сек"
                        if minutes > 0
                        else f"{seconds} сек"
                    ),
                },
            )

        # Читаем файл
        photo_bytes = await photo.read()

        from aiogram.types import BufferedInputFile
        from bot.config import bot, SUPPORT_TG_ID

        photo_file = BufferedInputFile(photo_bytes, filename="support_screenshot.png")

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Ответить",
                        callback_data=f"support_reply:{chat_id}",
                    )
                ]
            ]
        )

        await bot.send_photo(
            chat_id=SUPPORT_TG_ID,
            photo=photo_file,
            caption=f"🆘 Сообщение в техподдержку\nUser ID: {chat_id}\n\n{text}",
            reply_markup=keyboard,
        )

        # Обновляем счетчик в Redis
        if not current_requests:
            await redis_client.set(rate_limit_key, 1, expire=600)
        else:
            await redis_client.incr(rate_limit_key)

        logger.info(f"Support request sent to {SUPPORT_TG_ID} from {chat_id}")
        return {"status": "success"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending support request: {e}")
        raise HTTPException(status_code=500, detail="Error sending support request")


@hint_viewer_router.callback_query(F.data.startswith("support_reply:"))
async def support_reply_start(callback: CallbackQuery, state: FSMContext):
    """
    Хендлер для кнопки 'Ответить' в сообщении техподдержки.
    Переводит оператора в состояние ожидания текста ответа и сохраняет user_id.
    """
    await callback.answer()
    user_id = int(callback.data.split(":", 1)[1])

    await state.set_state(SupportStates.waiting_reply)
    await state.update_data(reply_user_id=user_id)

    await callback.message.answer(
        f"Напишите ответ пользователю {user_id}. Сообщение будет отправлено от бота."
    )


@hint_viewer_router.message(StateFilter(SupportStates.waiting_reply))
async def support_reply_send(message: Message, state: FSMContext):
    """
    Получает текст ответа от оператора и отправляет его пользователю из состояния FSM.
    """
    from bot.config import bot

    data = await state.get_data()
    reply_user_id = data.get("reply_user_id")

    if not reply_user_id:
        await message.answer("Не удалось определить пользователя для ответа.")
        await state.clear()
        return

    await bot.send_message(
        chat_id=int(reply_user_id),
        text=f"✉️ Ответ от техподдержки:\n\n{message.text}",
    )

    await message.answer("Ответ отправлен пользователю.")
    await state.clear()


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
    Обрабатывает пакет файлов, отправляя весь батч на анализ в одну RQ задачу.
    """
    batch_id = f"batch_{chat_id}_{uuid.uuid4().hex[:8]}"
    job_id = f"batch_job_{batch_id}"
    message_dao = MessagesTextsDAO(session_without_commit)

    try:
        # Проверяем, может ли пользователь добавить задачу
        if not can_enqueue_job(message.from_user.id):
            await message.answer(
                await message_dao.get_text("hint_viewer_batch_active_job_err", user_info.lang_code)
            )
            await state.clear()
            return

        total_files = len(file_paths)
        await message.answer(await message_dao.get_text("hint_viewer_files_accepted", user_info.lang_code, file_count=total_files))

        for mat_path in file_paths:
            if not await syncthing_sync.sync_and_wait(max_wait=30):
                logger.warning("Ошибка синхронизации Syncthing")
            if not await syncthing_sync.wait_for_file(mat_path, max_wait=30):
                await message.reply(
                    f"❌ Файл {os.path.basename(mat_path)} не найден после синхронизации"
                )
                return

        job = batch_queue.enqueue(
            "bot.workers.hint_worker.analyze_backgammon_batch_job",
            file_paths,
            str(message.from_user.id),
            batch_id,
            job_id,
            job_id=job_id,
            lang_code=user_info.lang_code,
        )

        add_active_job(message.from_user.id, job_id)

        # === Сохраняем информацию о батче в Redis ===
        batch_info = {
            "batch_id": batch_id,
            "job_id": job_id,
            "file_paths": file_paths,
            "user_id": message.from_user.id,
            "total_files": total_files,
            "status": "queued",
        }
        await redis_client.set(
            f"batch_info:{batch_id}",
            json.dumps(batch_info),
            expire=3600,  # 1 час
        )
        queue_warning = await get_queue_position_message(
            redis_rq, ["backgammon_analysis", "backgammon_batch_analysis"], session_without_commit, user_info
        )
        if queue_warning:
            user_dao = UserDAO(session_without_commit)
            admins = await user_dao.find_all(filters=SUser(role=User.Role.ADMIN.value))
            for admin in admins:
                try:
                    await message.bot.send_message(
                        chat_id=admin.id,
                        text=f"Пользователь в очереди на анализ ошибок. Его сообщение:{queue_warning}\n",
                    )
                except Exception as e:
                    logger.error(
                        f"Не удалось отправить уведомление админу {admin.id}: {e}"
                    )
            await message.answer(queue_warning, parse_mode="Markdown")
        logger.info(
            f"Batch {batch_id} queued with {total_files} files (job_id={job_id})"
        )

        summary = await message_dao.get_text("hint_viewer_batch_summary", user_info.lang_code, batch_id=batch_id, total_files=total_files)
        await message.answer(summary, parse_mode="HTML")

        await state.clear()

    except Exception as e:
        logger.exception(f"Error in process_batch_hint_files: {e}")
        await message.answer(f"❌ Ошибка при обработке батча: {e}")
        await state.clear()


async def check_job_status(
    message: Message, job_id: str, state: FSMContext, i18n, session_without_commit, user_info
):
    """
    Фоновая задача для проверки статуса анализа.
    Проверяет Redis каждые 3 секунды и отправляет результат когда готов.
    """
    try:
        message_dao = MessagesTextsDAO(session_without_commit)
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
                        
                        # Сохраняем mat_path для статистики
                        game_id = job_info["game_id"]
                        await redis_client.set(
                            f"mat_path:{game_id}", result["mat_path"], expire=7200
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
                                            text=await message_dao.get_text("hint_viewer_all_moves_b", user_info.lang_code),
                                            web_app=WebAppInfo(url=mini_app_url_all),
                                        ),
                                    ],
                                    [
                                        InlineKeyboardButton(
                                            text=await message_dao.get_text("hint_viewer_both_errors_b", user_info.lang_code),
                                            web_app=WebAppInfo(
                                                url=mini_app_url_both_errors
                                            ),
                                        ),
                                    ],
                                    [
                                        InlineKeyboardButton(
                                            text=await message_dao.get_text("hint_viewer_player_error_b", user_info.lang_code, player=red_player),
                                            web_app=WebAppInfo(
                                                url=mini_app_url_red_errors
                                            ),
                                        ),
                                    ],
                                    [
                                        InlineKeyboardButton(
                                            text=await message_dao.get_text("hint_viewer_player_error_b", user_info.lang_code, player=black_player),
                                            web_app=WebAppInfo(
                                                url=mini_app_url_black_errors
                                            ),
                                        ),
                                    ],
                                    [
                                        InlineKeyboardButton(
                                            text=await message_dao.get_text("hint_viewer_show_stat", user_info.lang_code),
                                            callback_data=f"show_stats:{game_id}",
                                        ),
                                    ],
                                ]
                            )

                            await message.answer(
                                text = await message_dao.get_text("hint_viewer_finished", user_info.lang_code, red_player=red_player, black_player=black_player),
                                reply_markup=keyboard,
                            )
                            await session_without_commit.commit()
                    else:
                        error_msg = result.get("error", "Неизвестная ошибка")
                        await message.answer(f"❌ Ошибка при анализе: {error_msg}")

                    break

                elif job.is_failed:
                    await message.answer("❌ Анализ завершился с критической ошибкой")
                    break

                elif job.is_queued:
                    position = job.get_position()
                    await asyncio.sleep(3)
                    continue

                elif job.is_started:
                    await asyncio.sleep(5)
                    continue

                else:
                    await asyncio.sleep(3)
                    continue

            except Exception as e:
                logger.warning(f"Error checking job status: {e}")
                remove_active_job(message.from_user.id, job_id)
                await asyncio.sleep(5)
                continue

    except Exception as e:
        logger.exception(f"Error in check_job_status for {job_id}")
        remove_active_job(message.from_user.id, job_id)
        await message.answer("❌ Ошибка при проверке статуса задачи")
    finally:
        remove_active_job(message.from_user.id, job_id)
