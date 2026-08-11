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
import tempfile
import requests
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import StateFilter

from fastapi import APIRouter, Request, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from rq import Queue
from rq.exceptions import NoSuchJobError
from rq.registry import StartedJobRegistry
from rq.job import Job
from redis import Redis
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
from bot.common.service.hint_s3_service import HintS3Storage
from bot.common.hint_job_state import (
    BATCH_DONE_FIELD,
    BATCH_TIMEOUT_MAX_SEC,
    add_active_job,
    calc_batch_job_timeout,
    can_enqueue_job,
    get_batch_file_statuses,
    is_batch_effectively_done,
    remove_active_job,
)
from bot.common.service.webapp_settings_service import (
    get_webapp_fullscreen_enabled,
    get_hint_viewer_screenshot_font_scale_percent,
    set_hint_viewer_screenshot_font_scale_percent,
    clamp_hint_viewer_screenshot_font_scale_percent,
)
from bot.common.func.waiting_message import WaitingMessageManager
from bot.common.kbds.markup.main_kb import MainKeyboard
from bot.common.general_states import GeneralStates
from bot.common.utils.i18n import get_all_locales_for_key
from bot.config import settings, bot, SUPPORT_TG_ID
from bot.config import translator_hub
from bot.common.utils.tg_auth import verify_telegram_webapp_data
from typing import TYPE_CHECKING

from bot.db.dao import UserDAO, DetailedAnalysisDAO, MessagesTextsDAO
from bot.db.database import async_session_maker
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
from bot.common.utils.static_assets import get_static_asset_version as _get_static_v

templates.env.globals["cache_timestamp"] = _get_static_v()
message_lock = asyncio.Lock()

redis_rq = Redis.from_url(settings.REDIS_URL, decode_responses=False)
task_queue = Queue("backgammon_analysis", connection=redis_rq, default_timeout=1800)
batch_queue = Queue(
    "backgammon_batch_analysis",
    connection=redis_rq,
    default_timeout=BATCH_TIMEOUT_MAX_SEC,
)


class HintViewerStates(StatesGroup):
    choose_type = State()
    waiting_file = State()
    uploading_sequential = State()
    stats_player_selection = State()


def load_analysis_json_from_s3(game_id: str, game_num: str | None = None):
    """Синхронно: читает JSON анализа из S3 (для asyncio.to_thread)."""
    s3 = HintS3Storage.from_settings()
    if game_num:
        key = HintS3Storage.game_json_key(game_id, game_num)
        if not s3.exists(key):
            raise FileNotFoundError(
                f"JSON файл для игры {game_num} в {game_id} не найден"
            )
        return json.loads(s3.download_bytes(key).decode("utf-8"))
    key = s3.summary_json_key(game_id)
    if not s3.exists(key):
        raise FileNotFoundError(f"JSON файл для {game_id} не найден")
    return json.loads(s3.download_bytes(key).decode("utf-8"))


async def build_hint_viewer_result_keyboard(
    message_dao: MessagesTextsDAO,
    lang_code: str,
    game_id: str,
    red_player: str,
    black_player: str,
    user_id: int | None = None,
    username: str | None = None,
    mat_ref: str | None = None,
) -> InlineKeyboardMarkup:
    """Кнопки WebApp режимов + статистика; для ROOT_ADMIN — «Анализ матча»."""
    mini_app_url_all = f"{settings.MINI_APP_URL}/hint-viewer?game_id={game_id}&error=0"
    mini_app_url_both_errors = (
        f"{settings.MINI_APP_URL}/hint-viewer?game_id={game_id}&error=1"
    )
    mini_app_url_red_errors = (
        f"{settings.MINI_APP_URL}/hint-viewer?game_id={game_id}&error=2"
    )
    mini_app_url_black_errors = (
        f"{settings.MINI_APP_URL}/hint-viewer?game_id={game_id}&error=3"
    )
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                text=await message_dao.get_text("hint_viewer_all_moves_b", lang_code),
                web_app=WebAppInfo(url=mini_app_url_all),
            ),
        ],
        [
            InlineKeyboardButton(
                text=await message_dao.get_text("hint_viewer_both_errors_b", lang_code),
                web_app=WebAppInfo(url=mini_app_url_both_errors),
            ),
        ],
        [
            InlineKeyboardButton(
                text=await message_dao.get_text(
                    "hint_viewer_player_error_b",
                    lang_code,
                    player=red_player,
                ),
                web_app=WebAppInfo(url=mini_app_url_red_errors),
            ),
        ],
        [
            InlineKeyboardButton(
                text=await message_dao.get_text(
                    "hint_viewer_player_error_b",
                    lang_code,
                    player=black_player,
                ),
                web_app=WebAppInfo(url=mini_app_url_black_errors),
            ),
        ],
        [
            InlineKeyboardButton(
                text=await message_dao.get_text("hint_viewer_show_stat", lang_code),
                callback_data=f"show_stats:{game_id}",
            ),
        ],
    ]
    if user_id is not None and user_id in settings.ROOT_ADMIN_IDS:
        rows.append(
            [
                InlineKeyboardButton(
                    text="Отправить в Анализ матча",
                    callback_data=f"save_match_analysis:{game_id}",
                ),
            ]
        )
    if user_id is not None and mat_ref:
        try:
            from bot.common.func.pro_analysis_order import create_pro_order
            from bot.common.kbds.inline.pro_analysis import PRO_ORDER_CALLBACK_PREFIX
            from bot.config import translator_hub

            is_local = os.path.isfile(mat_ref)
            request_id = await create_pro_order(
                user_id=user_id,
                username=username,
                service="hint_viewer",
                file_path=mat_ref if is_local else None,
                s3_key=None if is_local else mat_ref,
                file_name=os.path.basename(mat_ref) if is_local else f"{game_id}.mat",
            )
            i18n = translator_hub.get_translator_by_locale(lang_code or "ru")
            rows.append(
                [
                    InlineKeyboardButton(
                        text=i18n.pro.analysis.order_button(),
                        callback_data=f"{PRO_ORDER_CALLBACK_PREFIX}{request_id}",
                    ),
                ]
            )
        except Exception as e:
            logger.error(f"Failed to create pro order for hint_viewer {game_id}: {e}")
    return InlineKeyboardMarkup(inline_keyboard=rows)


from bot.common.rq_queue_maintenance import WORKER_COUNT_CACHE_KEY, get_live_worker_count

WORKER_CACHE_TTL = 3


async def get_worker_count_cached(redis_conn: Redis, queue_name: str) -> int:
    """
    Кэшированное число живых RQ-воркеров (обе очереди hint, без «мёртвых» записей).
    """
    cached_count = redis_conn.get(WORKER_COUNT_CACHE_KEY)

    if cached_count is not None:
        return int(cached_count)

    count = await asyncio.to_thread(
        get_live_worker_count, redis_conn, cleanup_registry=False
    )

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


@hint_viewer_router.message(
    F.text.in_(
        get_all_locales_for_key(translator_hub, "keyboard-user-reply-hint_viewer")
    ),
    UserInfo(),
)
async def hint_viewer_start(
    message: Message,
    state: FSMContext,
    user_info: User,
    session_without_commit: AsyncSession,
):
    message_dao = MessagesTextsDAO(session_without_commit)
    await state.set_state(HintViewerStates.choose_type)
    keyboard = InlineKeyboardBuilder()
    keyboard.button(
        text=await message_dao.get_text("button_error_single", user_info.lang_code),
        callback_data="hint_type:single",
    )
    keyboard.button(
        text=await message_dao.get_text("button_error_batch", user_info.lang_code),
        callback_data="hint_type:batch",
    )
    keyboard.adjust(1)
    await message.answer(
        await message_dao.get_text("hint_viewer_start", user_info.lang_code),
        reply_markup=keyboard.as_markup(),
    )


@hint_viewer_router.callback_query(
    F.data.startswith("hint_type:"),
    StateFilter(HintViewerStates.choose_type),
    UserInfo(),
)
async def handle_hint_type_selection(
    callback: CallbackQuery,
    state: FSMContext,
    user_info: User,
    session_without_commit: AsyncSession,
):
    message_dao = MessagesTextsDAO(session_without_commit)
    hint_type = callback.data.split(":")[1]
    if hint_type == "single":
        await state.set_state(HintViewerStates.waiting_file)
        await callback.message.answer(
            await message_dao.get_text("hint_viewer_single_upload", user_info.lang_code)
        )
    else:
        await state.set_state(HintViewerStates.uploading_sequential)
        await state.update_data(file_paths=[])
        keyboard = ReplyKeyboardBuilder()
        keyboard.button(
            text=await message_dao.get_text(
                "hint_viewer_batch_upload_stop", user_info.lang_code
            )
        )
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
            await message_dao.get_text(
                "hint_viewer_batch_no_file", user_info.lang_code
            ),
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
    F.document, StateFilter(HintViewerStates.uploading_sequential), UserInfo()
)
async def handle_sequential_hint_file(
    message: Message,
    state: FSMContext,
    user_info: User,
    session_without_commit: AsyncSession,
):
    message_dao = MessagesTextsDAO(session_without_commit)
    async with message_lock:
        doc = message.document
        fname = doc.file_name
        if not (fname.lower().endswith(".mat") or fname.lower().endswith(".zip")):
            await message.reply(
                await message_dao.get_text(
                    "hint_viewer_batch_file_extension_error", user_info.lang_code
                ),
            )
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
            except Exception as e:
                logger.error(f"Error extracting ZIP: {e}")
                await message.reply(
                    await message_dao.get_text(
                        "hint_viewer_batch_file_extracted_error", user_info.lang_code
                    )
                )
                os.remove(temp_path)
                return
            await state.update_data(file_paths=file_paths)
            try:
                await message.answer(
                    await message_dao.get_text(
                        "hint_viewer_batch_file_extracted",
                        user_info.lang_code,
                        zip_size=len([p for p in file_paths if p.endswith(".mat")]),
                    ),
                )
            except Exception as e:
                logger.warning(
                    f"Failed to send batch zip confirmation for user {user_info.id}: {e}"
                )
        else:
            # Обычный .mat файл — сначала сохраняем state, потом подтверждение
            file_paths.append(temp_path)
            await state.update_data(file_paths=file_paths)
            try:
                await message.answer(
                    await message_dao.get_text(
                        "hint_viewer_batch_file_added",
                        user_info.lang_code,
                        file_count=len(file_paths),
                    )
                )
            except Exception as e:
                logger.warning(
                    f"Failed to send batch file confirmation for user {user_info.id}: {e}"
                )

        await asyncio.sleep(0.3)


@hint_viewer_router.message(
    F.document,
    StateFilter(HintViewerStates.waiting_file),
    UserInfo(),
)
async def hint_viewer_menu(
    message: Message, state: FSMContext, user_info: User, i18n, session_without_commit
):
    """Обработка загруженного .mat файла"""
    message_dao = MessagesTextsDAO(session_without_commit)
    doc = message.document
    fname = doc.file_name

    if not fname.lower().endswith(".mat"):
        await message.reply(
            await message_dao.get_text(
                "hint_viewer_sin_file_ext_error", user_info.lang_code
            )
        )
        return

    # === Генерируем уникальный ID для этой задачи ===
    game_id = random_filename(ext="")
    local_mat = os.path.join("files", f"{game_id}_{fname}")
    job_id = f"hint_{message.from_user.id}_{uuid.uuid4().hex[:8]}"

    try:
        if not can_enqueue_job(message.from_user.id):
            await message.answer(
                await message_dao.get_text(
                    "hint_viewer_sin_active_job_err", user_info.lang_code
                )
            )
            await state.clear()
            return

        file = await message.bot.get_file(doc.file_id)
        os.makedirs("files", exist_ok=True)

        with open(local_mat, "wb") as f:
            await message.bot.download_file(file.file_path, f)

        logger.info(f"Файл скачан локально: {local_mat}")

        with open(local_mat, "r", encoding="utf-8") as f:
            content = f.read()
        red_player, black_player = extract_player_names(content)
        estimated_time = estimate_processing_time(local_mat)

        def _put_mat():
            return HintS3Storage.from_settings().put_source_mat(game_id, local_mat)

        mat_s3_key = await asyncio.to_thread(_put_mat)

        job = task_queue.enqueue(
            "bot.workers.hint_worker.analyze_backgammon_job",
            game_id,
            str(message.from_user.id),
            job_id=job_id,
        )

        await redis_client.set(f"mat_path:{game_id}", mat_s3_key, expire=86400)

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
                    "mat_s3_key": mat_s3_key,
                    "red_player": red_player,
                    "black_player": black_player,
                    "user_id": message.from_user.id,
                }
            ),
            expire=3600,
        )
        queue_warning = await get_queue_position_message(
            redis_rq,
            ["backgammon_analysis", "backgammon_batch_analysis"],
            session_without_commit,
            user_info,
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

        status_text = await message_dao.get_text(
            "hint_viewer_sin_file_accepted",
            user_info.lang_code,
            estimated_time=estimated_time,
        )
        await message.answer(status_text, parse_mode="Markdown")

        # === Сохраняем данные в состояние для проверки статуса ===
        await state.update_data(
            job_id=job_id,
            game_id=game_id,
            mat_s3_key=mat_s3_key,
            red_player=red_player,
            black_player=black_player,
        )

        # === Запускаем фоновую проверку статуса ===
        asyncio.create_task(
            check_job_status(
                message, job_id, state, i18n, session_without_commit, user_info
            )
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
    mat_ref = await redis_client.get(f"mat_path:{game_id}")

    if not mat_ref:
        await callback.answer("Файл не найден.")
        return
    waiting_manager = WaitingMessageManager(callback.from_user.id, callback.bot, i18n)
    temp_mat: str | None = None
    try:
        await waiting_manager.start()
        if os.path.isfile(mat_ref):
            path_for_mat = mat_ref
        else:
            fd, temp_mat = tempfile.mkstemp(suffix=".mat")
            os.close(fd)
            s3 = HintS3Storage.from_settings()
            await asyncio.to_thread(s3.download_file, mat_ref, temp_mat)
            path_for_mat = temp_mat

        with open(path_for_mat, "r", encoding="utf-8") as f:
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
            path_for_mat,
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
            analysis_data, new_file_path, player_names, duration = result
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
        if temp_mat and os.path.isfile(temp_mat):
            try:
                os.remove(temp_mat)
            except OSError:
                pass
        await waiting_manager.stop()


@hint_viewer_router.callback_query(
    F.data.startswith("save_match_analysis:"), UserInfo()
)
async def handle_save_match_analysis(callback: CallbackQuery, user_info: User):
    """Админ: сохранить готовый hint-анализ в кабинет «Анализ матча»."""
    user_id = int(callback.from_user.id)
    if user_id not in settings.ROOT_ADMIN_IDS:
        await callback.answer("Только для администраторов", show_alert=True)
        return

    parts = (callback.data or "").split(":", 1)
    game_id = parts[1].strip() if len(parts) > 1 else ""
    if not game_id:
        await callback.answer("Нет game_id", show_alert=True)
        return

    await callback.answer("Сохраняю…")
    try:
        from bot.routers.match_analysis_router import save_match_analysis_from_game_id

        result = await save_match_analysis_from_game_id(game_id, user_id)
    except FileNotFoundError:
        await callback.message.answer(
            "❌ Анализ не найден в хранилище (истёк или ещё не готов)."
        )
        return
    except Exception as e:
        logger.exception(f"save_match_analysis failed game_id={game_id}: {e}")
        await callback.message.answer(f"❌ Ошибка сохранения: {e}")
        return

    kb = InlineKeyboardBuilder()
    kb.button(
        text="Открыть матч",
        web_app=WebAppInfo(url=result["view_url"]),
    )
    kb.button(
        text="Кабинет «Анализ матча»",
        web_app=WebAppInfo(url=result["cabinet_url"]),
    )
    kb.adjust(1)
    await callback.message.answer(
        f"✅ Сохранено в «Анализ матча» #{result['id']}: <b>{result['title']}</b>",
        parse_mode="HTML",
        reply_markup=kb.as_markup(),
    )


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


@hint_viewer_api_router.get("/hint-viewer")
async def get_hint_viewer_web(request: Request, game_id: str = None):
    """
    Возвращает HTML-страницу интерактивного просмотра подсказок.
    """
    if not game_id:
        raise HTTPException(status_code=400, detail="game_id parameter is required")

    # Стабильный bust для /static (не time.time — иначе кэш браузера бесполезен)
    from bot.common.utils.static_assets import get_static_asset_version

    cache_timestamp = get_static_asset_version()
    webapp_fullscreen_enabled = await get_webapp_fullscreen_enabled("hints")
    hint_viewer_screenshot_font_scale_percent = (
        await get_hint_viewer_screenshot_font_scale_percent()
    )

    response = templates.TemplateResponse(
        "hint_viewer.html",
        {
            "request": request,
            "game_id": game_id,
            "cache_timestamp": cache_timestamp,
            "webapp_fullscreen_enabled": webapp_fullscreen_enabled,
            "hint_viewer_screenshot_font_scale_percent": hint_viewer_screenshot_font_scale_percent,
            "match_analysis_mode": False,
        },
    )

    # Add cache-busting headers to prevent HTML caching
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"

    return response


@hint_viewer_api_router.get("/api/analysis/{game_id}")
async def get_analysis_data(game_id: str, game_num: str = None):
    """
    Возвращает JSON-данные анализа для указанного game_id и номера игры.
    Если game_num не указан, возвращает список всех игр.
    """
    try:
        data = await asyncio.to_thread(load_analysis_json_from_s3, game_id, game_num)
        return data
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Game {game_id} not found")
    except Exception as e:
        logger.error(f"Error fetching analysis data for {game_id}: {e}")
        raise HTTPException(status_code=500, detail="Error generating analysis data")


async def _load_optional_screenshot_audio(form_data) -> tuple[bytes, str] | None:
    """
    Достаёт аудио к скриншоту из form-поля ``audio`` или по ``audio_s3_key``.
    """
    audio_upload = form_data.get("audio")
    if audio_upload is not None and hasattr(audio_upload, "read"):
        audio_bytes = await audio_upload.read()
        if audio_bytes:
            filename = (
                getattr(audio_upload, "filename", None)
                or form_data.get("audio_name")
                or "audio.webm"
            )
            return audio_bytes, str(filename)

    audio_s3_key = form_data.get("audio_s3_key")
    if not audio_s3_key:
        return None
    key = str(audio_s3_key).strip()
    if not key or not HintS3Storage.is_match_analysis_media_key(key):
        logger.warning(f"Invalid audio_s3_key for screenshot: {key!r}")
        return None
    try:
        s3 = HintS3Storage.from_settings()
        if not s3.exists(key):
            logger.warning(f"Screenshot audio S3 key not found: {key}")
            return None
        audio_bytes = s3.download_bytes(key)
    except Exception as e:
        logger.error(f"Failed to download screenshot audio from S3 ({key}): {e}")
        return None
    if not audio_bytes:
        return None
    audio_name = form_data.get("audio_name") or key.rsplit("/", 1)[-1] or "audio.webm"
    return audio_bytes, str(audio_name)


async def _send_screenshot_audio_to_chat(chat_id: int, audio_bytes: bytes, audio_name: str) -> None:
    """
    Шлёт аудио как голосовое сообщение (voice). Для mp3/m4a — как audio-плеер.
    Если Telegram отклоняет формат — fallback в документ.
    """
    name = (audio_name or "audio.webm").strip() or "audio.webm"
    ext = os.path.splitext(name)[1].lower().lstrip(".")

    if ext in {"mp3", "m4a", "mpeg", "mp4"}:
        try:
            await bot.send_audio(
                chat_id=chat_id,
                audio=BufferedInputFile(audio_bytes, filename=name),
                caption="Аудио к ходу",
            )
            return
        except Exception as e:
            logger.warning(f"send_audio failed for screenshot audio ({name}): {e}")

    # Голосовое в TG: OGG/OPUS. webm+opus из MediaRecorder часто принимается как voice.ogg.
    try:
        await bot.send_voice(
            chat_id=chat_id,
            voice=BufferedInputFile(audio_bytes, filename="voice.ogg"),
            caption="Аудио к ходу",
        )
        return
    except Exception as e:
        logger.warning(f"send_voice failed for screenshot audio ({name}): {e}")

    await bot.send_document(
        chat_id=chat_id,
        document=BufferedInputFile(audio_bytes, filename=name),
        caption="Аудио к ходу",
    )


@hint_viewer_api_router.post("/api/send_screenshot")
async def send_screenshot(request: Request):
    """
    Принимает скриншот от веб-приложения и отправляет его в чат пользователя.
    Опционально прикрепляет аудио текущего хода (файл или S3 key).
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

        chat_id_int = int(chat_id)
        logger.info(f"Sending screenshot to chat_id: {chat_id}")

        async with async_session_maker() as session:
            user_dao = UserDAO(session)
            balance = await user_dao.get_total_analiz_balance(
                chat_id_int, ServiceType.SCRINSHOT
            )
            if balance is not None and balance < 1:
                logger.warning(
                    f"Недостаточно баланса SCRINSHOT для пользователя {chat_id}. Баланс: {balance}"
                )
                # Уведомляем саппорт о попытке отправки скриншота без баланса
                support_keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="Ответить",
                                callback_data=f"admin_reply:{chat_id}",
                            )
                        ]
                    ]
                )
                await bot.send_message(
                    chat_id=SUPPORT_TG_ID,
                    text=f"⚠️ Пользователь попытался отправить скриншот, но у него не хватило баланса.\nUser ID: {chat_id}",
                    reply_markup=support_keyboard,
                )
                user = await user_dao.find_one_or_none_by_id(chat_id_int)
                lang_code = (user.lang_code or "en") if user else "en"
                message_dao = MessagesTextsDAO(session)
                msg_text = await message_dao.get_text(
                    "screenshots_not_enough_balance", lang_code
                )
                if msg_text:
                    i18n = translator_hub.get_translator_by_locale(lang_code)
                    await bot.send_message(
                        chat_id=chat_id_int,
                        text=msg_text,
                        reply_markup=get_activate_promo_keyboard(i18n),
                    )
                raise HTTPException(
                    status_code=402,
                    detail="Недостаточно баланса для сохранения скриншота",
                )

            # Читаем файл и отправляем
            photo_bytes = await photo.read()
            logger.debug(f"Screenshot file size: {len(photo_bytes)} bytes")
            photo_file = BufferedInputFile(photo_bytes, filename="screenshot.png")
            await bot.send_photo(chat_id=chat_id_int, photo=photo_file)

            audio_payload = await _load_optional_screenshot_audio(form_data)
            if audio_payload:
                audio_bytes, audio_name = audio_payload
                await _send_screenshot_audio_to_chat(chat_id_int, audio_bytes, audio_name)

            # Списываем баланс SCRINSHOT после успешной отправки
            await user_dao.decrease_analiz_balance(
                user_id=chat_id_int,
                service_type=ServiceType.SCRINSHOT.name,
            )
            await session.commit()

        logger.info(f"Screenshot successfully sent to chat_id: {chat_id}")
        return {"status": "success"}

    except HTTPException:
        raise
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


@hint_viewer_api_router.post("/api/save_screenshot")
async def save_screenshot(request: Request):
    """
    Сохраняет скриншот в буфер для пользователя.
    Опционально сохраняет аудио текущего хода рядом со скрином.
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

        audio_payload = await _load_optional_screenshot_audio(form_data)
        if audio_payload:
            audio_bytes, audio_name = audio_payload
            _, ext = os.path.splitext(audio_name)
            if not ext:
                ext = ".webm"
            audio_filename = f"screenshot_{timestamp}_audio{ext}"
            audio_path = os.path.join(buffer_dir, audio_filename)
            with open(audio_path, "wb") as f:
                f.write(audio_bytes)
            logger.info(f"Screenshot audio saved to buffer: {audio_path}")

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
    Создает ZIP архив из буфера скриншотов (и аудио, если есть) и отправляет в Telegram.
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

        extra_files = [
            f
            for f in os.listdir(buffer_dir)
            if os.path.isfile(os.path.join(buffer_dir, f)) and not f.endswith(".png")
        ]

        chat_id_int = int(chat_id)
        file_count = len(screenshots)

        async with async_session_maker() as session:
            user_dao = UserDAO(session)
            balance = await user_dao.get_total_analiz_balance(
                chat_id_int, ServiceType.SCRINSHOT
            )
            if balance is not None and balance < file_count:
                logger.warning(
                    f"Недостаточно баланса SCRINSHOT для пользователя {chat_id}. "
                    f"Нужно: {file_count}, баланс: {balance}"
                )
                # Уведомляем саппорт о попытке отправки скриншотов без баланса
                support_keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="Ответить",
                                callback_data=f"admin_reply:{chat_id}",
                            )
                        ]
                    ]
                )
                await bot.send_message(
                    chat_id=SUPPORT_TG_ID,
                    text=f"⚠️ Пользователь попытался отправить скриншоты ({file_count} шт.), но у него не хватило баланса.\nUser ID: {chat_id}",
                    reply_markup=support_keyboard,
                )
                user = await user_dao.find_one_or_none_by_id(chat_id_int)
                lang_code = (user.lang_code or "en") if user else "en"
                message_dao = MessagesTextsDAO(session)
                msg_text = await message_dao.get_text(
                    "screenshots_not_enough_balance", lang_code
                )
                if msg_text:
                    i18n = translator_hub.get_translator_by_locale(lang_code)
                    await bot.send_message(
                        chat_id=chat_id_int,
                        text=msg_text,
                        reply_markup=get_activate_promo_keyboard(i18n),
                    )
                raise HTTPException(
                    status_code=402,
                    detail=f"Недостаточно баланса. Нужно {file_count} скриншотов.",
                )

            # Создаем ZIP архив
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                for screenshot in screenshots:
                    filepath = os.path.join(buffer_dir, screenshot)
                    zip_file.write(filepath, screenshot)
                for extra in extra_files:
                    filepath = os.path.join(buffer_dir, extra)
                    zip_file.write(filepath, extra)

            zip_buffer.seek(0)
            zip_data = zip_buffer.getvalue()

            zip_file = BufferedInputFile(zip_data, filename="screenshots.zip")
            caption = f"Архив с {file_count} скриншотами"
            if extra_files:
                caption += f" и {len(extra_files)} аудио"
            await bot.send_document(
                chat_id=chat_id_int,
                document=zip_file,
                caption=caption,
            )

            # Списываем баланс за каждый сохранённый файл (батчевое списание)
            await user_dao.decrease_analiz_balance_batch(
                user_id=chat_id_int,
                service_type=ServiceType.SCRINSHOT.name,
                amount=file_count,
            )
            await session.commit()

        # Очищаем буфер
        shutil.rmtree(buffer_dir)

        logger.info(f"Screenshots ZIP sent to chat_id: {chat_id}, {file_count} files")
        return {"status": "success"}

    except HTTPException:
        raise
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
                await message_dao.get_text(
                    "hint_viewer_batch_active_job_err", user_info.lang_code
                )
            )
            await state.clear()
            return

        total_files = len(file_paths)
        await message.answer(
            await message_dao.get_text(
                "hint_viewer_files_accepted",
                user_info.lang_code,
                total_files=total_files,
            )
        )

        s3 = HintS3Storage.from_settings()

        def upload_batch_inputs():
            keys = []
            for i, local_path in enumerate(file_paths):
                key = s3.batch_input_key(batch_id, i)
                s3.upload_file(local_path, key)
                keys.append(key)
            return keys

        mat_s3_keys = await asyncio.to_thread(upload_batch_inputs)
        original_fnames = [os.path.basename(p) for p in file_paths]
        job_timeout = calc_batch_job_timeout(total_files)

        job = batch_queue.enqueue(
            "bot.workers.hint_worker.analyze_backgammon_batch_job",
            mat_s3_keys,
            str(message.from_user.id),
            batch_id,
            original_fnames,
            job_id=job_id,
            job_timeout=job_timeout,
            result_ttl=86400,
            failure_ttl=86400,
        )

        add_active_job(message.from_user.id, job_id, ttl=job_timeout + 3600)

        await redis_client.set(
            f"job_info:{job_id}",
            json.dumps(
                {
                    "type": "batch",
                    "batch_id": batch_id,
                    "user_id": message.from_user.id,
                    "total_files": total_files,
                }
            ),
            expire=job_timeout + 3600,
        )
        batch_info = {
            "batch_id": batch_id,
            "job_id": job_id,
            "mat_s3_keys": mat_s3_keys,
            "original_fnames": original_fnames,
            "user_id": message.from_user.id,
            "total_files": total_files,
            "status": "queued",
            "job_timeout": job_timeout,
        }
        await redis_client.set(
            f"batch_info:{batch_id}",
            json.dumps(batch_info),
            expire=job_timeout + 3600,
        )
        queue_warning = await get_queue_position_message(
            redis_rq,
            ["backgammon_analysis", "backgammon_batch_analysis"],
            session_without_commit,
            user_info,
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
            f"Batch {batch_id} queued with {total_files} files "
            f"(job_id={job_id}, timeout={job_timeout}s)"
        )

        summary = await message_dao.get_text(
            "hint_viewer_batch_summary",
            user_info.lang_code,
            batch_id=batch_id,
            total_files=total_files,
        )
        await message.answer(summary, parse_mode="HTML")

        asyncio.create_task(
            check_batch_job_status(
                message,
                job_id,
                batch_id,
                user_info,
                session_without_commit,
                total_files=total_files,
            )
        )

        await state.clear()

    except Exception as e:
        logger.exception(f"Error in process_batch_hint_files: {e}")
        await message.answer(f"❌ Ошибка при обработке батча: {e}")
        await state.clear()


def _batch_next_file_suffix(payload: dict) -> str:
    next_fname = payload.get("next_fname")
    if not next_fname:
        return ""
    return f"\n\n⏭ Следующий: <b>{next_fname}</b>"


async def _notify_batch_file_telegram(
    message: Message,
    message_dao: MessagesTextsDAO,
    user_info: User,
    session_without_commit: AsyncSession,
    payload: dict,
) -> None:
    """Отправляет в Telegram результат одного файла батча (вызывается из бота, не воркера)."""
    fname = payload.get("fname", "file")
    next_suffix = _batch_next_file_suffix(payload)
    if payload.get("status") == "error":
        err = payload.get("error", "Неизвестная ошибка")
        await message.answer(
            f"❌ <b>{fname}</b>: {str(err)[:100]}{next_suffix}",
            parse_mode="HTML",
        )
        return

    await UserDAO(session_without_commit).decrease_analiz_balance(
        user_id=message.from_user.id, service_type="HINTS"
    )

    game_id = payload.get("game_id")
    has_games = payload.get("has_games")
    red_player = payload.get("red_player", "Red")
    black_player = payload.get("black_player", "Black")

    if has_games and game_id:
        await message.answer(
            f"✅ <b>{fname}</b> обработан!\n{red_player} vs {black_player}{next_suffix}",
            parse_mode="HTML",
        )
        mat_ref = payload.get("mat_path") or await redis_client.get(f"mat_path:{game_id}")
        keyboard = await build_hint_viewer_result_keyboard(
            message_dao,
            user_info.lang_code,
            game_id,
            red_player,
            black_player,
            user_id=message.from_user.id,
            username=message.from_user.username or getattr(user_info, "username", None),
            mat_ref=mat_ref,
        )
        finished_text = await message_dao.get_text(
            "hint_viewer_finished",
            user_info.lang_code,
            red_player=red_player,
            black_player=black_player,
        )
        file_index = payload.get("file_index")
        total_files = payload.get("total_files")
        if file_index is not None and total_files:
            counter = f"{file_index}/{total_files}"
            if "Анализ завершен!" in finished_text:
                finished_text = finished_text.replace(
                    "Анализ завершен!", f"Анализ завершен! {counter}", 1
                )
            else:
                finished_text = f"{finished_text} {counter}"
        await message.answer(
            text=finished_text,
            reply_markup=keyboard,
        )
    else:
        await message.answer(
            f"✅ <b>{fname}</b> обработан, но игр не найдено.{next_suffix}",
            parse_mode="HTML",
        )
        mat_ref = payload.get("mat_path")
        if mat_ref:
            from bot.common.func.pro_analysis_order import offer_pro_analysis_order

            await offer_pro_analysis_order(
                message,
                user_id=message.from_user.id,
                username=message.from_user.username or getattr(user_info, "username", None),
                service="hint_viewer",
                lang_code=user_info.lang_code,
                s3_key=mat_ref if not os.path.isfile(mat_ref) else None,
                file_path=mat_ref if os.path.isfile(mat_ref) else None,
                file_name=fname if str(fname).lower().endswith(".mat") else f"{fname}.mat",
            )
    await session_without_commit.commit()


async def check_batch_job_status(
    message: Message,
    job_id: str,
    batch_id: str,
    user_info: User,
    session_without_commit: AsyncSession,
    total_files: int = 0,
):
    """
    Фоновая проверка батч-задачи: читает статусы файлов из Redis (воркер)
    и отправляет уведомления в Telegram через бота.
    """
    notified_indices: set[str] = set()
    try:
        message_dao = MessagesTextsDAO(session_without_commit)

        async def drain_batch_notifications() -> None:
            statuses = await asyncio.to_thread(get_batch_file_statuses, batch_id)
            for idx_str, raw_json in statuses.items():
                if idx_str == BATCH_DONE_FIELD or idx_str in notified_indices:
                    continue
                try:
                    payload = json.loads(raw_json)
                except json.JSONDecodeError:
                    logger.warning("Invalid batch file status JSON: {}", raw_json)
                    continue
                await _notify_batch_file_telegram(
                    message,
                    message_dao,
                    user_info,
                    session_without_commit,
                    payload,
                )
                notified_indices.add(idx_str)

        while True:
            try:
                await drain_batch_notifications()

                # Файлы уже опубликованы — не ждём RQ, если horse убит на финише
                if total_files and await asyncio.to_thread(
                    is_batch_effectively_done, batch_id, total_files
                ):
                    await drain_batch_notifications()
                    logger.info(
                        f"Batch job {job_id} effectively done "
                        f"({len(notified_indices)}/{total_files} files notified)"
                    )
                    break

                job = Job.fetch(job_id, connection=redis_rq)

                if job.is_finished:
                    await drain_batch_notifications()
                    logger.info(f"Batch job {job_id} completed")
                    break

                if job.is_failed:
                    await drain_batch_notifications()
                    if total_files and await asyncio.to_thread(
                        is_batch_effectively_done, batch_id, total_files
                    ):
                        logger.warning(
                            f"Batch job {job_id} marked failed in RQ, "
                            "but all file statuses are present — treating as completed"
                        )
                        break
                    await message.answer(
                        "❌ Пакетный анализ завершился с критической ошибкой"
                    )
                    break

                await asyncio.sleep(3)

            except NoSuchJobError:
                await drain_batch_notifications()
                if total_files and await asyncio.to_thread(
                    is_batch_effectively_done, batch_id, total_files
                ):
                    logger.warning(
                        f"Batch job {job_id} missing in Redis, "
                        "but all file statuses are present — treating as completed"
                    )
                    break
                logger.warning(
                    f"Batch job {job_id} no longer exists in Redis, removing active job"
                )
                remove_active_job(message.from_user.id, job_id)
                break
            except Exception as e:
                logger.warning(f"Error checking batch job status: {e}")
                await asyncio.sleep(5)

    except Exception as e:
        logger.exception(f"Error in check_batch_job_status for {job_id}")
        await message.answer("❌ Ошибка при проверке статуса пакетной задачи")
    finally:
        remove_active_job(message.from_user.id, job_id)


# DEBUG: блок для отладки — zip с JSON игры админу при одиночном анализе (удалить когда не нужно)
def _debug_is_admin_uploader(user_info, user_id: int) -> bool:
    if user_id in admins:
        return True
    return getattr(user_info, "role", None) == User.Role.ADMIN.value


def _debug_build_single_analysis_json_zip(game_id: str) -> bytes | None:
    """DEBUG: собирает zip со сводным JSON, JSON игр и stdout.log каждой игры из S3."""
    s3 = HintS3Storage.from_settings()
    zip_buffer = io.BytesIO()
    added = 0
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        summary_key = s3.summary_json_key(game_id)
        if s3.exists(summary_key):
            zf.writestr(f"{game_id}.json", s3.download_bytes(summary_key))
            added += 1

        prefix = s3.games_prefix(game_id)
        resp = s3._client.list_objects_v2(Bucket=s3._bucket, Prefix=prefix)
        for obj in resp.get("Contents") or []:
            key = (obj.get("Key") or "").strip()
            if not (
                key.endswith(".json")
                or key.endswith(".stdout.log")
            ):
                continue
            rel = key[len(prefix) :].lstrip("/")
            if not rel:
                continue
            zf.writestr(f"games/{rel}", s3.download_bytes(key))
            added += 1

    if added == 0:
        return None
    zip_buffer.seek(0)
    return zip_buffer.getvalue()


async def _debug_send_admin_single_analysis_json_zip(
    message: Message,
    game_id: str,
    red_player: str | None,
    black_player: str | None,
    user_info,
) -> None:
    """DEBUG: отправляет zip с JSON админу, если одиночный анализ запускал админ."""
    user_id = message.from_user.id
    if not _debug_is_admin_uploader(user_info, user_id):
        return
    try:
        zip_data = await asyncio.to_thread(
            _debug_build_single_analysis_json_zip, game_id
        )
        if not zip_data:
            logger.warning(
                "DEBUG admin json zip: JSON файлы не найдены для game_id={}", game_id
            )
            return

        safe_name = lambda s: "".join(
            c if c.isalnum() or c in "._-" else "_" for c in (s or "player")
        )
        filename = (
            f"debug_{game_id}_{safe_name(red_player)}_vs_{safe_name(black_player)}_jsons.zip"
        )
        doc = BufferedInputFile(zip_data, filename=filename)
        await message.bot.send_document(
            chat_id=user_id,
            document=doc,
            caption=(
                f"[DEBUG] JSON + stdout архив одиночного анализа\n"
                f"{red_player or '—'} vs {black_player or '—'}"
            ),
        )
        logger.info(
            "DEBUG admin json zip sent: user_id={} game_id={}", user_id, game_id
        )
    except Exception as e:
        logger.exception(
            "DEBUG failed to send admin json zip game_id={}: {}", game_id, e
        )


# DEBUG: конец блока отладки одиночного анализа


async def check_job_status(
    message: Message,
    job_id: str,
    state: FSMContext,
    i18n,
    session_without_commit,
    user_info,
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

                        if result["has_games"]:
                            red_player = job_info["red_player"]
                            black_player = job_info["black_player"]

                            keyboard = await build_hint_viewer_result_keyboard(
                                message_dao,
                                user_info.lang_code,
                                game_id,
                                red_player,
                                black_player,
                                user_id=message.from_user.id,
                                username=message.from_user.username
                                or getattr(user_info, "username", None),
                                mat_ref=result.get("mat_path"),
                            )

                            await message.answer(
                                text=await message_dao.get_text(
                                    "hint_viewer_finished",
                                    user_info.lang_code,
                                    red_player=red_player,
                                    black_player=black_player,
                                ),
                                reply_markup=keyboard,
                            )
                            await session_without_commit.commit()
                        else:
                            await message.answer(
                                await message_dao.get_text(
                                    "hint_viewer_finished",
                                    user_info.lang_code,
                                    red_player=job_info["red_player"],
                                    black_player=job_info["black_player"],
                                )
                            )
                            mat_ref = result.get("mat_path")
                            if mat_ref:
                                from bot.common.func.pro_analysis_order import (
                                    offer_pro_analysis_order,
                                )

                                await offer_pro_analysis_order(
                                    message,
                                    user_id=message.from_user.id,
                                    username=message.from_user.username
                                    or getattr(user_info, "username", None),
                                    service="hint_viewer",
                                    i18n=i18n,
                                    s3_key=mat_ref
                                    if not os.path.isfile(mat_ref)
                                    else None,
                                    file_path=mat_ref
                                    if os.path.isfile(mat_ref)
                                    else None,
                                    file_name=f"{game_id}.mat",
                                )
                            await session_without_commit.commit()

                        # # DEBUG: zip с JSON игры админу-загрузчику (удалить вместе с _debug_* выше)
                        # await _debug_send_admin_single_analysis_json_zip(
                        #     message,
                        #     game_id,
                        #     job_info.get("red_player"),
                        #     job_info.get("black_player"),
                        #     user_info,
                        # )
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

            except NoSuchJobError:
                logger.warning(
                    f"Job {job_id} no longer exists in Redis, removing active job"
                )
                remove_active_job(message.from_user.id, job_id)
                break
            except Exception as e:
                logger.warning(f"Error checking job status: {e}")
                await asyncio.sleep(5)
                continue

    except Exception as e:
        logger.exception(f"Error in check_job_status for {job_id}")
        remove_active_job(message.from_user.id, job_id)
        await message.answer("❌ Ошибка при проверке статуса задачи")
    finally:
        remove_active_job(message.from_user.id, job_id)
        await state.clear()


@hint_viewer_api_router.post("/api/check_admin")
async def check_admin_status(request: Request):
    """
    Проверяет, является ли пользователь администратором на основе данных Telegram WebApp.
    """
    try:
        data = await request.json()
        init_data = data.get("initData")

        if not init_data:
            raise HTTPException(status_code=400, detail="Missing initData")

        user_data = verify_telegram_webapp_data(init_data)
        if not user_data:
            raise HTTPException(status_code=401, detail="Invalid Telegram data")

        user_id = user_data.get("user", {}).get("id")
        if not user_id:
            raise HTTPException(status_code=400, detail="Invalid user data")

        is_admin = user_id in settings.ROOT_ADMIN_IDS

        return {"is_admin": is_admin, "user_id": user_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking admin status: {e}")
        raise HTTPException(status_code=500, detail="Error checking admin status")


@hint_viewer_api_router.post("/api/hint_viewer_screenshot_font_scale")
async def update_hint_viewer_screenshot_font_scale(request: Request):
    """Сохраняет глобальный масштаб шрифта для скриншотов hint_viewer (только ROOT_ADMIN)."""
    try:
        data = await request.json()
        init_data = data.get("initData")
        if not init_data:
            raise HTTPException(status_code=400, detail="Missing initData")

        user_data = verify_telegram_webapp_data(init_data)
        if not user_data:
            raise HTTPException(status_code=401, detail="Invalid Telegram data")

        user_id = user_data.get("user", {}).get("id")
        if not user_id:
            raise HTTPException(status_code=400, detail="Invalid user data")
        if user_id not in settings.ROOT_ADMIN_IDS:
            raise HTTPException(status_code=403, detail="Forbidden")

        font_scale_percent = clamp_hint_viewer_screenshot_font_scale_percent(
            data.get("fontScalePercent", 100)
        )
        saved = await set_hint_viewer_screenshot_font_scale_percent(font_scale_percent)
        return {"fontScalePercent": saved}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating hint viewer screenshot font scale: {e}")
        raise HTTPException(
            status_code=500, detail="Error updating screenshot font scale"
        )
