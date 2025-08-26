import asyncio
import shutil
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import io
import re
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, StateFilter
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile
import pytz
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger
import os
import json
import zipfile
import tempfile

from bot.common.filters.user_info import UserInfo
from bot.common.func.func import (
    format_detailed_analysis,
    get_analysis_data,
    get_user_file_name,
)
from bot.common.func.generate_pdf import html_to_pdf_bytes
from bot.common.func.waiting_message import WaitingMessageManager
from bot.common.func.yadisk import save_file_to_yandex_disk
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

batch_auto_analyze_router = Router()


class BatchAnalyzeDialog(StatesGroup):
    choose_type = State()
    uploading_sequential = State()
    uploading_zip = State()
    select_player = State()


@batch_auto_analyze_router.callback_query(
    F.data == "autoanalyze_batch", UserInfo()
)
async def start_batch_auto_analyze(
    callback: CallbackQuery, state: FSMContext, i18n: TranslatorRunner
):
    await callback.message.delete()
    await state.set_state(BatchAnalyzeDialog.choose_type)
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text=i18n.auto.batch.sequential(), callback_data="batch_type:sequential")
    keyboard.button(text=i18n.auto.batch.zip(), callback_data="batch_type:zip")
    keyboard.adjust(1)
    await callback.message.answer(i18n.auto.batch.choose_type(), reply_markup=keyboard.as_markup())


@batch_auto_analyze_router.callback_query(F.data.startswith("batch_type:"), StateFilter(BatchAnalyzeDialog.choose_type))
async def handle_batch_type_selection(
    callback: CallbackQuery, state: FSMContext, i18n: TranslatorRunner
):
    batch_type = callback.data.split(":")[1]
    if batch_type == "sequential":
        await state.set_state(BatchAnalyzeDialog.uploading_sequential)
        await state.update_data(file_paths=[])
        keyboard = ReplyKeyboardBuilder()
        keyboard.button(text=i18n.auto.batch.stop())
        await callback.message.answer(i18n.auto.batch.submit_sequential(), reply_markup=keyboard.as_markup(resize_keyboard=True))
    else:  # zip
        await state.set_state(BatchAnalyzeDialog.uploading_zip)
        await callback.message.answer(i18n.auto.batch.submit_zip(), reply_markup=get_cancel_kb(i18n))
    await callback.answer()
    await callback.message.delete()


@batch_auto_analyze_router.message(F.text.in_(get_all_locales_for_key(translator_hub, "auto-batch-stop")), StateFilter(BatchAnalyzeDialog.uploading_sequential), UserInfo())
async def handle_batch_stop(
    message: Message, state: FSMContext, i18n: TranslatorRunner, user_info: User, session_without_commit: AsyncSession
):
    data = await state.get_data()
    file_paths = data.get("file_paths", [])
    if not file_paths:
        await state.clear()
        await message.answer(i18n.auto.batch.no_files(), reply_markup=MainKeyboard.build(user_info.role, i18n))
        await message.delete()
        return
    await message.delete()
    await process_batch_files(message, state, user_info, i18n, file_paths, session_without_commit)


@batch_auto_analyze_router.message(
    F.text.in_(get_all_locales_for_key(translator_hub, "keyboard-reply-cancel")),
    StateFilter(BatchAnalyzeDialog.uploading_sequential, BatchAnalyzeDialog.uploading_zip),
    UserInfo(),
)
async def cancel_batch_auto_analyze(
    message: Message, state: FSMContext, i18n: TranslatorRunner, user_info: User
):
    await state.clear()
    await message.answer(
        text=i18n.keyboard.reply.cancel(),
        reply_markup=MainKeyboard.build(user_info.role, i18n),
    )


@batch_auto_analyze_router.message(
    F.document, StateFilter(BatchAnalyzeDialog.uploading_sequential), UserInfo()
)
async def handle_sequential_file(
    message: Message,
    state: FSMContext,
    i18n: TranslatorRunner,
    user_info: User,
):
    file = message.document
    if not file.file_name.endswith((".mat", '.txt', '.sgf', '.sgg', '.bkg', '.gam', '.pos', '.fibs', '.tmg')):
        return await message.answer(i18n.auto.analyze.invalid())
    
    files_dir = os.path.join(os.getcwd(), "files")
    os.makedirs(files_dir, exist_ok=True)
    file_name = file.file_name.replace(" ", "").replace('.txt', '.mat')
    file_path = os.path.join(files_dir, file_name)
    await message.bot.download(file.file_id, destination=file_path)
    
    data = await state.get_data()
    file_paths = data.get("file_paths", [])
    file_paths.append(file_path)
    await state.update_data(file_paths=file_paths)
    await message.answer(i18n.auto.batch.added(count = len(file_paths)))


@batch_auto_analyze_router.message(
    F.document, StateFilter(BatchAnalyzeDialog.uploading_zip), UserInfo()
)
async def handle_zip_file(
    message: Message,
    state: FSMContext,
    i18n: TranslatorRunner,
    user_info: User,
    session_without_commit: AsyncSession
):
    file = message.document
    if not file.file_name.endswith(".zip"):
        return await message.answer(i18n.auto.batch.invalid_zip())
    
    files_dir = os.path.join(os.getcwd(), "files")
    os.makedirs(files_dir, exist_ok=True)
    zip_path = os.path.join(files_dir, file.file_name.replace(" ", ""))
    await message.bot.download(file.file_id, destination=zip_path)
    
    file_paths = []
    with zipfile.ZipFile(zip_path, 'r') as zipf:
        for member in zipf.namelist():
            if member.endswith(('.mat', '.txt', '.sgf', '.sgg', '.bkg', '.gam', '.pos', '.fibs', '.tmg')):
                extracted_path = zipf.extract(member, files_dir)
                file_paths.append(extracted_path)
    
    # Remove the ZIP file after extraction
    try:
        os.remove(zip_path)
    except Exception as e:
        logger.warning(f"Failed to remove ZIP file {zip_path}: {e}")
    
    if not file_paths:
        await state.clear()
        return await message.answer(i18n.auto.batch.no_valid_files(), reply_markup=MainKeyboard.build(user_info.role, i18n))
    
    await state.update_data(file_paths=file_paths)
    await process_batch_files(message, state, user_info, i18n, file_paths, session_without_commit)


async def process_batch_files(
    message: Message,
    state: FSMContext,
    user_info: User,
    i18n: TranslatorRunner,
    file_paths: list,
    session_without_commit: AsyncSession 
):    
    all_analysis_datas = []
    successful_count = 0
    total = len(file_paths)
    progress_message = await message.answer(i18n.auto.batch.progress(current = 0, total = total))
    data = await state.get_data()
    current_file_idx = data.get('current_file_idx', 1)
    for idx, file_path in enumerate(file_paths, current_file_idx):
        await message.bot.delete_message(chat_id=message.chat.id, message_id=progress_message.message_id)
        progress_message = await message.answer(i18n.auto.batch.progress(current = idx, total = total))
        file_type = os.path.splitext(file_path)[1][1:]
        loop = asyncio.get_running_loop()
        duration, analysis_result = await loop.run_in_executor(None, analyze_mat_file, file_path, file_type)
        
        analysis_data = json.loads(analysis_result)
        player_names = list(analysis_data["chequerplay"].keys())
        if len(player_names) != 2:
            logger.warning(f"Invalid number of players in file: {file_path}")
            continue
        
        # Store analysis data temporarily
        moscow_tz = pytz.timezone("Europe/Moscow")
        current_date = datetime.now(moscow_tz).strftime("%d.%m.%y-%H.%M.%S")
        new_file_name = f"{current_date}:{player_names[0]}:{player_names[1]}.{file_type}"
        new_file_path = os.path.join(os.getcwd(), "files", new_file_name)
        shutil.move(file_path, new_file_path)
        try:
            asyncio.create_task(save_file_to_yandex_disk(new_file_path, new_file_name))
        except Exception as e:
            logger.error(f"Error saving file to Yandex Disk: {e}")
        
        # Check if user is one of the players
        if user_info.player_username and user_info.player_username in player_names:
            selected_player = user_info.player_username
            await process_single_analysis(
                message, state, user_info, i18n, analysis_data, new_file_name, new_file_path,
                selected_player, session=session_without_commit
            )
            all_analysis_datas.append(analysis_data)
            successful_count += 1
        else:
            # Prompt for player selection
            await state.update_data(
                current_file_idx=idx,
                total_files=total,
                file_path=new_file_path,
                file_name=new_file_name,
                analysis_data=analysis_data,
                player_names=player_names,
                all_analysis_datas=all_analysis_datas,
                successful_count=successful_count,
                progress_message_id=progress_message.message_id
            )
            keyboard = InlineKeyboardBuilder()
            for player in player_names:
                keyboard.button(text=player, callback_data=f"batch_player:{player}")
            keyboard.adjust(1)
            await message.answer(
                i18n.auto.analyze.complete(),
                reply_markup=keyboard.as_markup(),
            )
            await state.set_state(BatchAnalyzeDialog.select_player)
            return  # Wait for player selection before continuing
    await message.bot.delete_message(chat_id=message.chat.id, message_id=progress_message.message_id)
    # If no player selection is needed, finalize batch
    await finalize_batch(message, state, user_info, i18n, all_analysis_datas, successful_count, session_without_commit)


async def process_single_analysis(
    message: Message,
    state: FSMContext,
    user_info: User,
    i18n: TranslatorRunner,
    analysis_data: dict,
    file_name: str,
    file_path: str,
    selected_player: str,
    session: AsyncSession,
):
    game_id = f"batch_auto_{message.from_user.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    player_data = {
        "user_id": user_info.id,
        "player_name": selected_player,
        "file_name": file_name,
        "file_path": file_path,
        "game_id": game_id,
        **get_analysis_data(analysis_data, selected_player),
    }

    data = await state.get_data()
    pr_values = data.get("pr_values", {})
    players_metrics = get_analysis_data(analysis_data)
    for player in players_metrics.keys():
        pr_values.setdefault(player, []).append(players_metrics[player].get("snowie_error_rate", 0))
    await state.update_data(pr_values=pr_values)

    dao = DetailedAnalysisDAO(session)
    await dao.add(SDetailedAnalysis(**player_data))
    
    formatted_analysis = format_detailed_analysis(get_analysis_data(analysis_data), i18n)
    await message.answer(
        f"{formatted_analysis}\n\n",
        parse_mode="HTML",
        reply_markup=MainKeyboard.build(user_role=user_info.role, i18n=i18n)
    )
    

@batch_auto_analyze_router.callback_query(F.data.startswith("batch_player:"), StateFilter(BatchAnalyzeDialog.select_player), UserInfo())
async def handle_batch_player_selection(
    callback: CallbackQuery,
    state: FSMContext,
    user_info: User,
    i18n: TranslatorRunner,
    session_without_commit: AsyncSession
):
    try:
        data = await state.get_data()
        selected_player = callback.data.split(":")[1]
        analysis_data = data["analysis_data"]
        file_name = data["file_name"]
        file_path = data["file_path"]
        current_file_idx = data["current_file_idx"]
        total_files = data["total_files"]
        all_analysis_datas = data.get("all_analysis_datas", [])
        successful_count = data.get("successful_count", 0)
        progress_message_id = data["progress_message_id"]
        
        # Update user player_username if needed
        user_dao = UserDAO(session_without_commit)
        if not user_info.player_username or user_info.player_username != selected_player:
            user_info.player_username = selected_player
            await user_dao.update(user_info.id, {"player_username": selected_player})
            logger.info(f"Updated player_username for user {user_info.id} to {selected_player}")
        

        await process_single_analysis(
                callback.message, state, user_info, i18n, analysis_data, file_name, file_path,
                selected_player, session=session_without_commit
            )
        
        all_analysis_datas.append(analysis_data)
        successful_count += 1
        
        # Update state for next file
        file_paths = data.get("file_paths", [])[1:]  # Remaining files
        logger.info("FILE PATHS AFTER SELECTION: " + str(file_paths))
        await state.update_data(
            file_paths=file_paths,
            all_analysis_datas=all_analysis_datas,
            successful_count=successful_count
        )
        
        await callback.message.delete()

        await callback.message.bot.delete_message(chat_id=callback.message.chat.id, message_id=progress_message_id)
        progress_message = await callback.message.answer(i18n.auto.batch.progress(current = current_file_idx, total = total_files))
        for idx, file_path in enumerate(file_paths, current_file_idx + 1):
            await callback.message.bot.delete_message(chat_id=callback.message.chat.id, message_id=progress_message.message_id)
            progress_message = await callback.message.answer(i18n.auto.batch.progress(current = idx, total = total_files))
            file_type = os.path.splitext(file_path)[1][1:]
            loop = asyncio.get_running_loop()
            duration, analysis_result = await loop.run_in_executor(None, analyze_mat_file, file_path, file_type)
            
            analysis_data = json.loads(analysis_result)
            player_names = list(analysis_data["chequerplay"].keys())
            if len(player_names) != 2:
                logger.warning(f"Invalid number of players in file: {file_path}")
                continue
            
            # Store analysis data temporarily
            moscow_tz = pytz.timezone("Europe/Moscow")
            current_date = datetime.now(moscow_tz).strftime("%d.%m.%y-%H.%M.%S")
            new_file_name = f"{current_date}:{player_names[0]}:{player_names[1]}.{file_type}"
            new_file_path = os.path.join(os.getcwd(), "files", new_file_name)
            shutil.move(file_path, new_file_path)
            try:
                asyncio.create_task(save_file_to_yandex_disk(new_file_path, new_file_name))
            except Exception as e:
                logger.error(f"Error saving file to Yandex Disk: {e}")
            


            if user_info.player_username and user_info.player_username in player_names:
                selected_player = user_info.player_username
                await process_single_analysis(
                    callback.message, state, user_info, i18n, analysis_data, new_file_name, new_file_path,
                    selected_player, session=session_without_commit
                )
                all_analysis_datas.append(analysis_data)
                successful_count += 1
            else:
                await state.update_data(
                    current_file_idx=idx,
                    total_files=total_files,
                    file_path=new_file_path,
                    file_name=new_file_name,
                    analysis_data=analysis_data,
                    player_names=player_names,
                    all_analysis_datas=all_analysis_datas,
                    successful_count=successful_count,
                    progress_message_id=progress_message.message_id
                )
                keyboard = InlineKeyboardBuilder()
                for player in player_names:
                    keyboard.button(text=player, callback_data=f"batch_player:{player}")

                keyboard.adjust(1)
                await callback.message.answer(
                    i18n.auto.analyze.complete(),
                    reply_markup=keyboard.as_markup(),
                )
                await state.set_state(BatchAnalyzeDialog.select_player)
                return
        
        await callback.message.bot.delete_message(chat_id=callback.message.chat.id, message_id=progress_message.message_id)
        await finalize_batch(
            callback.message, state, user_info, i18n, all_analysis_datas,
            successful_count, session_without_commit
        )
    
    except Exception as e:
        await session_without_commit.rollback()
        logger.error(f"Error in batch player selection: {e}")
        await callback.message.answer(i18n.auto.analyze.error.save())


async def finalize_batch(
    message: Message,
    state: FSMContext,
    user_info: User,
    i18n: TranslatorRunner,
    all_analysis_datas: list,
    successful_count: int,
    session_without_commit: AsyncSession
):
    if successful_count > 0:
        # Deduct balance once
        user_dao = UserDAO(session_without_commit)
        await user_dao.decrease_analiz_balance(user_info.id, service_type=ServiceType.MATCH)
        
        # Store in Redis
        await redis_client.set(f"batch_analysis_data:{user_info.id}", json.dumps(all_analysis_datas), expire=3600)
        
        # Calculate and send averages
        data = await state.get_data()
        pr_values = data.get("pr_values", [])
        for player, pr in pr_values.items():
            average_pr = calculate_average_analysis(pr)
            pr_list = ", ".join([f"{pr:.2f}" for pr in pr])
            ru_i18n: TranslatorRunner = translator_hub.get_translator_by_locale(
                'ru'
            )
            await message.bot.send_message(
                settings.CHAT_GROUP_ID,
                ru_i18n.auto.batch.summary_pr(player=player, pr_list=pr_list, average_pr=f"{average_pr:.2f}"),
                parse_mode="HTML"
            )
            await message.answer(
                i18n.auto.batch.summary_pr(player=player, pr_list=pr_list, average_pr=f"{average_pr:.2f}"),
                parse_mode="HTML",
                reply_markup=MainKeyboard.build(user_role=user_info.role, i18n=i18n)
            )
        await message.answer(
            i18n.auto.analyze.ask_pdf(), reply_markup=get_download_pdf_kb(i18n, 'batch')
        )
    else:
        await message.answer(i18n.auto.batch.no_matches(), reply_markup=MainKeyboard.build(user_info.role, i18n))
    
    await session_without_commit.commit()
    await state.clear()

def calculate_average_analysis(pr_values: list) -> float:
    if not pr_values:
        return 0.0
    return sum(pr_values) / len(pr_values)

@batch_auto_analyze_router.callback_query(DownloadPDFCallback.filter(F.context == 'batch'), UserInfo())
async def handle_download_pdf(
    callback: CallbackQuery,
    callback_data: DownloadPDFCallback,
    user_info: User,
    state: FSMContext,
    i18n: TranslatorRunner,
):
    await callback.message.delete()
    if callback_data.action == "yes":
        key = f"batch_analysis_data:{user_info.id}"
        file_name_key = f"file_name:{user_info.id}"
        file_name = await redis_client.get(file_name_key)
        file_type = file_name.split('.')[-1] if file_name else 'pdf'
        file_name = file_name.replace(file_type, 'pdf') if file_name else 'batch_analysis.pdf'
        analysis_data_json = await redis_client.get(key)
        if not analysis_data_json:
            await callback.message.answer(i18n.auto.batch.no_data_pdf())
            return
        analysis_data = json.loads(analysis_data_json)
        html_text = ''
        for data in analysis_data:            
            html_text += format_detailed_analysis(get_analysis_data(data), i18n) + "\n____________________\n"
        pdf_bytes = html_to_pdf_bytes(html_text)
        if not pdf_bytes:
            await callback.message.answer(i18n.auto.analyze.error.parse())
            return
        await callback.message.answer_document(
            document=BufferedInputFile(
                pdf_bytes,
                filename=file_name
            ),
            caption=i18n.auto.analyze.pdf_ready(),
        )
        await redis_client.delete(key)
    else:
        await callback.message.answer(i18n.auto.analyze.no_pdf())