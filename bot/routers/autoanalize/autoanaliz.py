import asyncio
from datetime import datetime
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, StateFilter
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile
import pytz
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger
import os
import json
from bot.common.filters.user_info import UserInfo
from bot.common.func.func import (
    format_detailed_analysis,
    get_analysis_data,
)
from bot.common.func.generate_pdf import html_to_pdf_bytes
from bot.common.func.waiting_message import WaitingMessageManager
from bot.common.func.yadisk import save_file_to_yandex_disk
from bot.common.kbds.inline.activate_promo import get_activate_promo_keyboard
from bot.common.kbds.inline.autoanalize import DownloadPDFCallback, SendToHintViewerCallback, get_download_pdf_kb
from bot.common.kbds.markup.cancel import get_cancel_kb
from bot.common.kbds.markup.main_kb import MainKeyboard
from bot.db.dao import DetailedAnalysisDAO, UserDAO, MessagesTextsDAO
from bot.db.models import PromocodeServiceQuantity, ServiceType, User
from bot.common.func.analiz_func import analyze_mat_file
from bot.db.schemas import SDetailedAnalysis, SUser
from bot.db.redis import redis_client
from bot.common.utils.i18n import get_all_locales_for_key
from bot.config import translator_hub, settings
from typing import TYPE_CHECKING
from fluentogram import TranslatorRunner
from bot.routers.hint_viewer_router import (
    HintViewerStates,
    can_enqueue_job,
    add_active_job,
    task_queue,
    redis_rq,
    get_queue_position_message,
    check_job_status,
)
from bot.common.func.hint_viewer import (
    extract_player_names,
    estimate_processing_time,
    random_filename,
)
from bot.common.service.sync_folder_service import SyncthingSync

if TYPE_CHECKING:
    from locales.stub import TranslatorRunner

auto_analyze_router = Router()


class AutoAnalyzeDialog(StatesGroup):
    file = State()


@auto_analyze_router.callback_query(
    F.data == "autoanalyze_single", UserInfo()
)
async def start_auto_analyze(
    callback: CallbackQuery, state: FSMContext, user_info:User, i18n: TranslatorRunner, session_without_commit:AsyncSession
):
    message_dao = MessagesTextsDAO(session_without_commit)
    await callback.message.delete()
    keyboard = InlineKeyboardBuilder()
    keyboard.button(
        text=await message_dao.get_text('analyze_moneygame', user_info.lang_code), callback_data="auto_type:moneygame"
    )
    keyboard.button(
        text=await message_dao.get_text('analyze_match', user_info.lang_code), callback_data="auto_type:match"
    )
    keyboard.adjust(1)
    await callback.message.answer(
        await message_dao.get_text('analyze_choose_game_type', user_info.lang_code), reply_markup=keyboard.as_markup()
    )


@auto_analyze_router.callback_query(F.data.startswith("auto_type:"), UserInfo())
async def handle_type_selection(
    callback: CallbackQuery,
    state: FSMContext,
    i18n: TranslatorRunner,
    user_info: User,
    session_without_commit: AsyncSession,
):
    message_dao = MessagesTextsDAO(session_without_commit)
    await callback.message.delete()
    analysis_type = callback.data.split(":")[1]
    await state.set_state(AutoAnalyzeDialog.file)
    await state.update_data(analysis_type=analysis_type)
    dao = UserDAO(session_without_commit)
    if analysis_type == "moneygame":
        balance = await dao.get_total_analiz_balance(
            user_info.id, service_type=ServiceType.MONEYGAME
        )
        text = await message_dao.get_text('analyze_submit_moneygame', user_info.lang_code)
    if analysis_type == "match":
        balance = await dao.get_total_analiz_balance(
            user_info.id, service_type=ServiceType.MATCH
        )
        text = await message_dao.get_text('analyze_submit_match', user_info.lang_code)
    if balance is None or balance > 0:
        await callback.message.answer(text, reply_markup=get_cancel_kb(i18n))
        await callback.answer()
    if balance == 0:
        await callback.message.answer(
            await message_dao.get_text('analyze_not_enought_balance', user_info.lang_code),
            reply_markup=get_activate_promo_keyboard(i18n),
        )
        await state.clear()


@auto_analyze_router.message(
    F.text.in_(get_all_locales_for_key(translator_hub, "keyboard-reply-cancel")),
    StateFilter(AutoAnalyzeDialog.file),
    UserInfo(),
)
async def cancel_auto_analyze(
    message: Message, state: FSMContext, i18n: TranslatorRunner, user_info: User, session_without_commit
):
    await state.clear()
    await message.answer(
        text=i18n.keyboard.reply.cancel(),
        reply_markup=MainKeyboard.build(user_info.role, i18n),
    )

async def analyze_file_by_path(
    file_path: str,
    file_type: str,
    user_info: User,
    session_without_commit: AsyncSession,
    i18n: TranslatorRunner,
    message_or_callback=None,
    analysis_type=None,
    forward_message=False,
):
    """
    Analyzes a file by path, used for both uploaded files and existing files.
    """
    loop = asyncio.get_running_loop()
    duration, analysis_result = await loop.run_in_executor(
        None, analyze_mat_file, file_path, file_type
    )
    if forward_message and duration > 0 and hasattr(message_or_callback, 'bot') and hasattr(message_or_callback, 'chat') and hasattr(message_or_callback, 'message_id'):
        try:
            await message_or_callback.bot.forward_message(
                chat_id=settings.CHAT_GROUP_ID,
                from_chat_id=message_or_callback.chat.id,
                message_id=message_or_callback.message_id
            )
        except Exception as e:
            logger.error(f"Failed to forward message for user {user_info.id}: {e}")
    analysis_data = await loop.run_in_executor(None, json.loads, analysis_result)
    await redis_client.set(
        f"analysis_data:{user_info.id}", json.dumps(analysis_data), expire=3600
    )

    player_names = list(analysis_data["chequerplay"].keys())
    if len(player_names) != 2:
        raise ValueError("Incorrect number of players in analysis")

    if analysis_type == "moneygame" and (duration is not None and duration != 0):
        raise ValueError("Wrong type: match instead of moneygame")
    if analysis_type == "match" and (duration is None or duration == 0):
        raise ValueError("Wrong type: moneygame instead of match")

    # Generate new filename
    moscow_tz = pytz.timezone("Europe/Moscow")
    current_date = datetime.now(moscow_tz).strftime("%d.%m.%y-%H.%M.%S")
    new_file_name = f"{current_date}:{player_names[0]}:{player_names[1]}.mat"
    files_dir = os.path.dirname(file_path)
    new_file_path = os.path.join(files_dir, new_file_name)
    try:
        os.rename(file_path, new_file_path)
    except Exception as e:
        logger.error(f"Failed to rename file {file_path} to {new_file_path}: {e}")
        raise
    try:
        asyncio.create_task(save_file_to_yandex_disk(new_file_path, new_file_name))
    except Exception as e:
        logger.error(f"Error saving file to Yandex Disk: {e}")


    logger.info(f"Processing file for user {user_info.player_username}, players: {player_names}")
    if user_info.player_username and user_info.player_username in player_names:
        selected_player = user_info.player_username
        game_id = f"auto_{user_info.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        player_data = {
            "user_id": user_info.id,
            "player_name": selected_player,
            "file_name": new_file_name,
            "file_path": new_file_path,
            "game_id": game_id,
            **get_analysis_data(analysis_data, selected_player),
        }

        dao = DetailedAnalysisDAO(session_without_commit)
        await dao.add(SDetailedAnalysis(**player_data))
        user_dao = UserDAO(session_without_commit)
        formated_data = get_analysis_data(analysis_data)
        if duration is None or duration == 0:
            await user_dao.decrease_analiz_balance(
                user_info.id, service_type=ServiceType.MONEYGAME
            )
        else:
            await user_dao.decrease_analiz_balance(
                user_info.id, service_type=ServiceType.MATCH
            )
        formatted_analysis = format_detailed_analysis(
            formated_data, i18n
        )
        player_names_list = list(formated_data)
        player1_name, player2_name = player_names_list
        p1 = formated_data.get(player1_name)
        p2 = formated_data.get(player2_name)
        current_date_str = datetime.now().strftime("%d.%m.%Y_%H.%M")
        players_str = f'{player1_name} ({abs(p1["snowie_error_rate"])}) - {player2_name} ({abs(p2["snowie_error_rate"])})'
        file_name_to_pdf = f"{players_str}_{current_date_str}.pdf".replace(":", ".").replace(" ", "")
        await redis_client.set(
            f"file_name:{user_info.id}", file_name_to_pdf, expire=3600
        )
        if duration is not None and duration != 0:
            try:
                # Генерация PDF
                html_text = format_detailed_analysis(formated_data, i18n)
                pdf_bytes = html_to_pdf_bytes(html_text)

                if not pdf_bytes:
                    logger.error("Ошибка при генерации PDF.")
                    await message_or_callback.bot.send_message(
                        settings.CHAT_GROUP_ID,
                        f"<b>Автоматический анализ игры от {current_date_str}</b>\n\n{players_str} Матч до {duration}\n\n",
                        parse_mode="HTML",
                    )
                    return

                # Отправка сообщения с PDF
                await message_or_callback.bot.send_document(
                    chat_id=settings.CHAT_GROUP_ID,
                    document=BufferedInputFile(pdf_bytes, filename=file_name_to_pdf),
                    caption=f"<b>Автоматический анализ игры от {current_date_str}</b>\n\n{players_str} Матч до {duration}\n\n",
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.error(f"Ошибка при отправке сообщения с PDF в группу: {e}")
        return formatted_analysis, new_file_path

    else:
        return analysis_data, new_file_path, player_names, duration


mat_file_lock = asyncio.Lock()

@auto_analyze_router.message(
    F.document, StateFilter(AutoAnalyzeDialog.file), UserInfo()
)
async def handle_mat_file(
    message: Message,
    state: FSMContext,
    session_without_commit: AsyncSession,
    i18n: TranslatorRunner,
    user_info: User,
):
    """
    Handles single file uploads for analysis, ensuring only one file is processed at a time.
    """
    # Try to acquire the lock non-blocking
    if not mat_file_lock.locked():
        async with mat_file_lock:
            message_dao = MessagesTextsDAO(session_without_commit)
            try:
                waiting_manager = WaitingMessageManager(message.chat.id, message.bot, i18n)
                file = message.document
                if not file.file_name.endswith(
                    (".mat", ".txt", ".sgf", ".sgg", ".bkg", ".gam", ".pos", ".fibs", ".tmg")
                ):
                    return await message.answer(await message_dao.get_text('analyze_type_invalid', user_info.lang_code))

                # Create the 'files' directory if it doesn't exist
                files_dir = os.path.join(os.getcwd(), "files")
                os.makedirs(files_dir, exist_ok=True)
                await waiting_manager.start()
                file_name = file.file_name.replace(" ", "").replace(".txt", ".mat")
                file_path = os.path.join(files_dir, file_name)

                file_type = file_name.split(".")[-1]

                # Download the file
                try:
                    await message.bot.download(file.file_id, destination=file_path)
                except Exception as e:
                    logger.error(f"Failed to download file {file_name} for user {user_info.id}: {e}")
                    await waiting_manager.stop()
                    await message.answer("Ошибка при загрузке файла. Попробуйте снова.")
                    return

                data = await state.get_data()
                analysis_type = data.get("analysis_type")   

                try:
                    result = await analyze_file_by_path(
                        file_path, file_type, user_info, session_without_commit, i18n, message, analysis_type, forward_message=True
                    )
                except ValueError as e:
                    await waiting_manager.stop()
                    await state.clear()
                    return await message.answer(
                        str(e),
                        reply_markup=MainKeyboard.build(user_role=user_info.role, i18n=i18n),
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
                    )

                    keyboard = InlineKeyboardBuilder()
                    for player in player_names:
                        keyboard.button(text=player, callback_data=f"auto_player:{player}")
                    keyboard.adjust(1)
                    await waiting_manager.stop()
                    await message.answer(
                        await message_dao.get_text('analyze_complete_ch_player', user_info.lang_code),
                        reply_markup=keyboard.as_markup(),
                    )
                else:
                    # Single player
                    formatted_analysis, new_file_path = result
                    await waiting_manager.stop()
                    # Сохраняем путь к файлу в Redis для возможности отправки на анализ ошибок
                    await redis_client.set(
                        f"auto_analyze_file_path:{user_info.id}", new_file_path, expire=3600
                    )
                    await message.answer(
                        f"{formatted_analysis}\n\n",
                        parse_mode="HTML",
                        reply_markup=MainKeyboard.build(user_role=user_info.role, i18n=i18n),
                    )
                    await message.answer(
                        await message_dao.get_text('analyze_ask_pdf', user_info.lang_code),
                        reply_markup=get_download_pdf_kb(i18n, 'solo', include_hint_viewer=True)
                    )
                    await session_without_commit.commit()

            except Exception as e:
                await session_without_commit.rollback()
                logger.error(f"Ошибка при автоматическом анализе файла: {e}")
                await waiting_manager.stop()
                await message.answer(i18n.auto.analyze.error.parse())
    else:
        await message.answer("Другой файл уже обрабатывается. Пожалуйста, подождите и попробуйте снова.")
        logger.info(f"Ignored file upload from user {user_info.id} due to ongoing processing")


@auto_analyze_router.callback_query(F.data.startswith("auto_player:"), UserInfo())
async def handle_player_selection(
    callback: CallbackQuery,
    state: FSMContext,
    session_without_commit: AsyncSession,
    user_info: User,
    i18n: TranslatorRunner,
):
    try:
        message_dao = MessagesTextsDAO(session_without_commit)
        data = await state.get_data()
        try:
            duration = int(data.get("duration"))
        except Exception as e:
            logger.error(f"Ошибка при получении значениѝ point match: {e}")
            duration = None
        analysis_data = data["analysis_data"]
        file_name = data["file_name"]
        file_path = data["file_path"]

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

        game_id = (
            f"auto_{callback.from_user.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )

        dao = DetailedAnalysisDAO(session_without_commit)

        player_data = {
            "user_id": callback.from_user.id,
            "player_name": selected_player,
            "file_name": file_name,
            "file_path": file_path,
            "game_id": game_id,
            **get_analysis_data(analysis_data, selected_player),
        }

        await dao.add(SDetailedAnalysis(**player_data))

        if duration is None or duration == 0:
            await user_dao.decrease_analiz_balance(
                user_info.id, service_type=ServiceType.MONEYGAME
            )
        else:
            await user_dao.decrease_analiz_balance(
                user_info.id, service_type=ServiceType.MATCH
            )

        formatted_analysis = format_detailed_analysis(
            get_analysis_data(analysis_data), i18n
        )

        await callback.message.delete()
        if duration is not None and duration != 0:
            try:
                formated_data = get_analysis_data(analysis_data)
                player_names = list(formated_data)
                player1_name, player2_name = player_names
                p1 = formated_data.get(player1_name)
                p2 = formated_data.get(player2_name)
                current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                players_str = f'{player1_name} ({abs(p1["snowie_error_rate"])}) - {player2_name} ({abs(p2["snowie_error_rate"])})'
                file_name_to_pdf = f"{players_str}_{current_date}.pdf".replace(":",".").replace(" ","")
                await redis_client.set(
                        f"file_name:{user_info.id}", file_name_to_pdf, expire=3600
                    )
                # Генерация PDF
                html_text = format_detailed_analysis(formated_data, i18n)
                pdf_bytes = html_to_pdf_bytes(html_text)
                if not pdf_bytes:
                    logger.error("Ошибка при генерации PDF.")
                    await callback.bot.send_message(
                        settings.CHAT_GROUP_ID,
                        f"<b>Автоматический анализ игры от {current_date}</b>\n\n {player1_name} ({p1['snowie_error_rate']}) - {player2_name} ({p2['snowie_error_rate']}) Матч до {duration}\n\n",
                        parse_mode="HTML",
                    )
                    return

                # Отправка сообщения с PDF
                await callback.bot.send_document(
                    chat_id=settings.CHAT_GROUP_ID,
                    document=BufferedInputFile(pdf_bytes, filename=file_name_to_pdf),
                    caption=f"<b>Автоматический анализ игры от {current_date}</b>\n\n {player1_name} ({p1['snowie_error_rate']}) - {player2_name} ({p2['snowie_error_rate']}) Матч до {duration}\n\n",
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.error(f"Ошибка при отправке сообщения с PDF в группу: {e}")
        # Сохраняем путь к файлу в Redis для возможности отправки на анализ ошибок
        await redis_client.set(
            f"auto_analyze_file_path:{user_info.id}", file_path, expire=3600
        )
        await callback.message.answer(
            f"{formatted_analysis}\n\n",
            parse_mode="HTML",
            reply_markup=MainKeyboard.build(user_role=user_info.role, i18n=i18n),
        )
        await callback.message.answer(
            await message_dao.get_text('analyze_ask_pdf', user_info.lang_code), 
            reply_markup=get_download_pdf_kb(i18n, 'solo', include_hint_viewer=True)
        )
        await session_without_commit.commit()
        await state.clear()

    except Exception as e:
        await session_without_commit.rollback()
        logger.error(f"Ошибка при ѝохранении выбора игрока: {e}")
        await callback.message.answer(i18n.auto.analyze.error.save())
        await state.clear()


@auto_analyze_router.callback_query(DownloadPDFCallback.filter(F.context == 'solo'), UserInfo())
async def handle_download_pdf(
    callback: CallbackQuery,
    callback_data: DownloadPDFCallback,
    user_info: User,
    state: FSMContext,
    i18n: TranslatorRunner,
    session_without_commit: AsyncSession,
):
    message_dao = MessagesTextsDAO(session_without_commit)
    await callback.message.delete()
    if callback_data.action == "yes":
        key = f"analysis_data:{user_info.id}"
        file_name_key = f"file_name:{user_info.id}"
        file_name = await redis_client.get(file_name_key)
        file_type = file_name.split(".")[-1]
        file_name = file_name.replace(file_type, "pdf") if file_name else "analysis.pdf"
        analysis_data_json = await redis_client.get(key)
        if not analysis_data_json:
            await callback.message.answer("Нет данных длѝ формированиѝ PDF.")
            return
        analysis_data = json.loads(analysis_data_json)
        html_text = format_detailed_analysis(get_analysis_data(analysis_data), i18n)
        pdf_bytes = html_to_pdf_bytes(html_text)
        if not pdf_bytes:
            await callback.message.answer("Ошибка при генерации PDF.")
            return
        await callback.message.answer_document(
            document=BufferedInputFile(pdf_bytes, filename=file_name),
            
            caption=await message_dao.get_text('analyze_pdf_ready', user_info.lang_code),
        )


@auto_analyze_router.callback_query(SendToHintViewerCallback.filter(F.context == 'solo'), UserInfo())
async def handle_send_to_hint_viewer(
    callback: CallbackQuery,
    callback_data: SendToHintViewerCallback,
    user_info: User,
    state: FSMContext,
    i18n: TranslatorRunner,
    session_without_commit: AsyncSession,
):
    """Обрабатывает отправку файла на анализ ошибок после автоанализа"""
    message_dao = MessagesTextsDAO(session_without_commit)
    await callback.message.delete()
    
    if callback_data.action == "yes":
        # Получаем путь к файлу из Redis
        file_path = await redis_client.get(f"auto_analyze_file_path:{user_info.id}")
        
        if not file_path:
            await callback.message.answer(
                await message_dao.get_text('analyze_file_not_found', user_info.lang_code) or 
                "Файл не найден. Пожалуйста, загрузите файл снова."
            )
            return
        
        file_path = file_path.decode('utf-8') if isinstance(file_path, bytes) else file_path
        
        if not os.path.exists(file_path):
            await callback.message.answer(
                await message_dao.get_text('analyze_file_not_found', user_info.lang_code) or 
                "Файл не найден. Пожалуйста, загрузите файл снова."
            )
            await redis_client.delete(f"auto_analyze_file_path:{user_info.id}")
            return
        
        # Удаляем ключ из Redis
        await redis_client.delete(f"auto_analyze_file_path:{user_info.id}")
        
        # Устанавливаем состояние для hint_viewer
        await state.set_state(HintViewerStates.waiting_file)
        
        try:
            # Генерируем уникальный ID для задачи
            game_id = random_filename(ext="")
            json_path = f"files/{game_id}.json"
            job_id = f"hint_{user_info.id}_{uuid.uuid4().hex[:8]}"
            
            # Проверяем возможность добавления задачи
            if not can_enqueue_job(user_info.id):
                await callback.message.answer(
                    await message_dao.get_text("hint_viewer_sin_active_job_err", user_info.lang_code)
                )
                await state.clear()
                return
            
            syncthing_sync = SyncthingSync()
            logger.info(f"Файл готов к обработке: {file_path}")
            
            # Синхронизация с Syncthing (если нужно)
            if not await syncthing_sync.sync_and_wait(max_wait=30):
                logger.warning("Ошибка синхронизации Syncthing")
            
            if not await syncthing_sync.wait_for_file(file_path, max_wait=30):
                await callback.message.answer("❌ Файл не найден после синхронизации")
                await state.clear()
                return
            
            # Читаем содержимое файла
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            red_player, black_player = extract_player_names(content)
            estimated_time = estimate_processing_time(file_path)
            
            # Добавляем задачу в очередь
            job = task_queue.enqueue(
                "bot.workers.hint_worker.analyze_backgammon_job",
                file_path,
                json_path,
                str(user_info.id),
                job_id=job_id,
                game_id=game_id,
            )
            
            # Используем реальный ID job
            actual_job_id = job.id if hasattr(job, 'id') and job.id else job_id
            logger.info(f"Job created: requested_job_id={job_id}, actual_job_id={actual_job_id}")
            
            # Сохраняем mat_path
            await redis_client.set(f"mat_path:{game_id}", file_path, expire=86400)
            
            add_active_job(user_info.id, actual_job_id)
            logger.info(f"Added active job: user_id={user_info.id}, job_id={actual_job_id}")
            
            # Сохраняем информацию о задаче
            await redis_client.set(
                f"job_info:{actual_job_id}",
                json.dumps({
                    "game_id": game_id,
                    "mat_path": file_path,
                    "json_path": json_path,
                    "red_player": red_player,
                    "black_player": black_player,
                    "user_id": user_info.id,
                }),
                expire=3600,
            )
            
            # Проверяем позицию в очереди
            queue_warning = await get_queue_position_message(
                redis_rq, ["backgammon_analysis", "backgammon_batch_analysis"], session_without_commit, user_info
            )
            if queue_warning:
                user_dao = UserDAO(session_without_commit)
                admins = await user_dao.find_all(filters=SUser(role=User.Role.ADMIN.value))
                for admin in admins:
                    try:
                        await callback.bot.send_message(
                            chat_id=admin.id,
                            text=f"Пользователь в очереди на анализ ошибок. Его сообщение:{queue_warning}\n",
                        )
                    except Exception as e:
                        logger.error(f"Не удалось отправить уведомление админу {admin.id}: {e}")
                await callback.message.answer(queue_warning)
            
            status_text = await message_dao.get_text(
                "hint_viewer_sin_file_accepted", user_info.lang_code, estimated_time=estimated_time
            )
            await callback.message.answer(status_text, parse_mode="Markdown")
            
            # Сохраняем данные в состояние для проверки статуса
            await state.update_data(
                job_id=actual_job_id,
                game_id=game_id,
                mat_path=file_path,
                json_path=json_path,
                red_player=red_player,
                black_player=black_player,
            )
            
            # Запускаем проверку статуса
            # Создаем фиктивное сообщение для check_job_status
            class FakeMessage:
                def __init__(self, chat_id, bot, user_id):
                    self.chat = type('obj', (object,), {'id': chat_id})()
                    self.bot = bot
                    self.from_user = type('obj', (object,), {'id': user_id})()
                    self._chat_id = chat_id
                
                async def answer(self, text, **kwargs):
                    """Отправляет сообщение в чат через bot.send_message"""
                    return await self.bot.send_message(chat_id=self._chat_id, text=text, **kwargs)
                
                async def reply(self, text, **kwargs):
                    """Отправляет ответ на сообщение"""
                    return await self.bot.send_message(chat_id=self._chat_id, text=text, **kwargs)
            
            fake_message = FakeMessage(callback.message.chat.id, callback.bot, user_info.id)
            asyncio.create_task(
                check_job_status(fake_message, actual_job_id, state, i18n, session_without_commit, user_info)
            )
            
        except Exception as e:
            logger.error(f"Ошибка при отправке файла на анализ ошибок: {e}")
            await callback.message.answer(
                await message_dao.get_text('analyze_error_sending_to_hints', user_info.lang_code) or
                f"Произошла ошибка при отправке файла на анализ ошибок: {e}"
            )
            await state.clear()
