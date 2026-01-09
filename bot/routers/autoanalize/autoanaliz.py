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
from bot.common.kbds.inline.autoanalize import DownloadPDFCallback, get_download_pdf_kb
from bot.common.kbds.markup.cancel import get_cancel_kb
from bot.common.kbds.markup.main_kb import MainKeyboard
from bot.db.dao import DetailedAnalysisDAO, UserDAO
from bot.db.models import PromocodeServiceQuantity, ServiceType, User
from bot.common.func.analiz_func import analyze_mat_file
from bot.db.schemas import SDetailedAnalysis, SUser
from bot.db.redis import redis_client

from bot.common.utils.i18n import get_all_locales_for_key
from bot.config import translator_hub
from typing import TYPE_CHECKING
from fluentogram import TranslatorRunner
from bot.config import settings

if TYPE_CHECKING:
    from locales.stub import TranslatorRunner

auto_analyze_router = Router()


class AutoAnalyzeDialog(StatesGroup):
    file = State()


@auto_analyze_router.callback_query(
    F.data == "autoanalyze_single", UserInfo()
)
async def start_auto_analyze(
    callback: CallbackQuery, state: FSMContext, i18n: TranslatorRunner
):
    await callback.message.delete()
    keyboard = InlineKeyboardBuilder()
    keyboard.button(
        text=i18n.auto.analyze.moneygame(), callback_data="auto_type:moneygame"
    )
    keyboard.button(
        text=i18n.auto.analyze.games_match(), callback_data="auto_type:match"
    )
    keyboard.adjust(1)
    await callback.message.answer(
        i18n.auto.analyze.choose_type(), reply_markup=keyboard.as_markup()
    )


@auto_analyze_router.callback_query(F.data.startswith("auto_type:"), UserInfo())
async def handle_type_selection(
    callback: CallbackQuery,
    state: FSMContext,
    i18n: TranslatorRunner,
    user_info: User,
    session_without_commit: AsyncSession,
):
    await callback.message.delete()
    analysis_type = callback.data.split(":")[1]
    await state.set_state(AutoAnalyzeDialog.file)
    await state.update_data(analysis_type=analysis_type)
    dao = UserDAO(session_without_commit)
    if analysis_type == "moneygame":
        balance = await dao.get_total_analiz_balance(
            user_info.id, service_type=ServiceType.MONEYGAME
        )
        text = i18n.auto.analyze.submit_moneygame()
    if analysis_type == "match":
        balance = await dao.get_total_analiz_balance(
            user_info.id, service_type=ServiceType.MATCH
        )
        text = i18n.auto.analyze.submit_match()
    if balance is None or balance > 0:
        await callback.message.answer(text, reply_markup=get_cancel_kb(i18n))
        await callback.answer()
    if balance == 0:
        await callback.message.answer(
            i18n.auto.analyze.not_ebought_balance(),
            reply_markup=get_activate_promo_keyboard(i18n),
        )
        await state.clear()


@auto_analyze_router.message(
    F.text.in_(get_all_locales_for_key(translator_hub, "keyboard-reply-cancel")),
    StateFilter(AutoAnalyzeDialog.file),
    UserInfo(),
)
async def cancel_auto_analyze(
    message: Message, state: FSMContext, i18n: TranslatorRunner, user_info: User
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
            try:
                waiting_manager = WaitingMessageManager(message.chat.id, message.bot, i18n)
                file = message.document
                if not file.file_name.endswith(
                    (".mat", ".txt", ".sgf", ".sgg", ".bkg", ".gam", ".pos", ".fibs", ".tmg")
                ):
                    return await message.answer(i18n.auto.analyze.invalid())

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
                        i18n.auto.analyze.complete(),
                        reply_markup=keyboard.as_markup(),
                    )
                else:
                    # Single player
                    formatted_analysis, new_file_path = result
                    await waiting_manager.stop()
                    await message.answer(
                        f"{formatted_analysis}\n\n",
                        parse_mode="HTML",
                        reply_markup=MainKeyboard.build(user_role=user_info.role, i18n=i18n),
                    )
                    await message.answer(
                        i18n.auto.analyze.ask_pdf(), reply_markup=get_download_pdf_kb(i18n, 'solo')
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
        await callback.message.answer(
            f"{formatted_analysis}\n\n",
            parse_mode="HTML",
            reply_markup=MainKeyboard.build(user_role=user_info.role, i18n=i18n),
        )
        await callback.message.answer(
            i18n.auto.analyze.ask_pdf(), reply_markup=get_download_pdf_kb(i18n, 'solo')
        )
        await session_without_commit.commit()

    except Exception as e:
        await session_without_commit.rollback()
        logger.error(f"Ошибка при ѝохранении выбора игрока: {e}")
        await callback.message.answer(i18n.auto.analyze.error.save())


@auto_analyze_router.callback_query(DownloadPDFCallback.filter(F.context == 'solo'), UserInfo())
async def handle_download_pdf(
    callback: CallbackQuery,
    callback_data: DownloadPDFCallback,
    user_info: User,
    state: FSMContext,
    i18n: TranslatorRunner,
):
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
            caption=i18n.auto.analyze.pdf_ready(),
        )
        # Deletion removed as per user request
        # await redis_client.delete(key)

    else:
        await callback.message.answer(i18n.auto.analyze.no_pdf())
