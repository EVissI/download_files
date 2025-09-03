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
from bot.common.func.generate_pdf import html_to_pdf_bytes, make_page, merge_pages
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
    callback: CallbackQuery, state: FSMContext, i18n: TranslatorRunner, user_info: User, session_without_commit: AsyncSession
):
    await callback.message.delete()
    await state.set_state(BatchAnalyzeDialog.choose_type)
    dao = UserDAO(session_without_commit)
    balance_match = await dao.get_total_analiz_balance(user_info.id, service_type=ServiceType.MATCH)
    balance_money = await dao.get_total_analiz_balance(user_info.id, service_type=ServiceType.MONEYGAME)
    if balance_match == 0 and balance_money == 0:
        await callback.message.answer(i18n.user.static.has_no_sub(), reply_markup=get_activate_promo_keyboard(i18n))
        return
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


sequential_file_lock = asyncio.Lock()

@batch_auto_analyze_router.message(
    F.document, StateFilter(BatchAnalyzeDialog.uploading_sequential), UserInfo()
)
async def handle_sequential_file(
    message: Message,
    state: FSMContext,
    i18n: TranslatorRunner,
    user_info: User,
):
    """
    Handles sequential file uploads, ensuring exclusive access with a lock to prevent race conditions.
    """
    file = message.document
    if not file.file_name.endswith((".mat", '.txt', '.sgf', '.sgg', '.bkg', '.gam', '.pos', '.fibs', '.tmg')):
        return await message.answer(i18n.auto.analyze.invalid())

    async with sequential_file_lock:
        try:
            # Create the 'files' directory if it doesn't exist
            files_dir = os.path.join(os.getcwd(), "files")
            os.makedirs(files_dir, exist_ok=True)

            # Sanitize and normalize filename
            file_name = file.file_name.replace(" ", "").replace('.txt', '.mat')
            file_path = os.path.join(files_dir, file_name)

            # Download the file
            try:
                await message.bot.download(file.file_id, destination=file_path)
            except Exception as e:
                logger.error(f"Failed to download file {file_name} for user {user_info.id}: {e}")
                await message.answer("Ошибка при загрузке файла. Попробуйте снова.")
                return

            # Update state with the new file path
            try:
                data = await state.get_data()
                file_paths = data.get("file_paths", [])
                if file_path not in file_paths:  # Prevent duplicates
                    file_paths.append(file_path)
                    await state.update_data(file_paths=file_paths)
                    logger.info(f"Added file {file_path} for user {user_info.id}, total files: {len(file_paths)}")
                else:
                    logger.warning(f"Duplicate file {file_path} skipped for user {user_info.id}")
            except Exception as e:
                logger.error(f"Failed to update state for user {user_info.id}: {e}")
                await message.answer("Ошибка при обработке файла. Попробуйте снова.")
                return

            # Send confirmation message
            await message.answer(i18n.auto.batch.added(count=len(file_paths)))
        except Exception as e:
            logger.error(f"Unexpected error in handle_sequential_file for user {user_info.id}: {e}")
            await message.answer("Произошла ошибка при обработке файла. Попробуйте снова.")


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
                new_name = member.replace(" ", "")
                # путь, куда будем извлекать
                extracted_path = os.path.join(files_dir, new_name)

                # убедимся, что директории существуют
                os.makedirs(os.path.dirname(extracted_path), exist_ok=True)

                # открыть файл из архива и сохранить под новым именем
                with zipf.open(member) as source, open(extracted_path, "wb") as target:
                    target.write(source.read())

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
            file_paths = file_paths[1:] 
            await state.update_data(file_paths=file_paths)
            selected_player = user_info.player_username
            process_result = await process_single_analysis(
                message, state, user_info, i18n, analysis_data, new_file_name, new_file_path,
                selected_player, session=session_without_commit, duration=duration
            )
            all_analysis_datas.append(analysis_data)
            successful_count += 1
            if not process_result:
                break
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
                progress_message_id=progress_message.message_id,
                duration=duration
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
    duration: int
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
    user_dao = UserDAO(session)
    players_metrics = get_analysis_data(analysis_data)

    if duration > 0:
        descrease_result = await user_dao.decrease_analiz_balance(user_info.id, ServiceType.MATCH)
        try:
            player_names = list(players_metrics)
            player1_name, player2_name = player_names
            p1 = players_metrics.get(player1_name)
            p2 = players_metrics.get(player2_name)
            current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            await message.bot.send_message(
                        settings.CHAT_GROUP_ID,
                        f"<b>Автоматичеѝкий анализ игры от {current_date}</b>\n\n {player1_name} ({p1['snowie_error_rate']}) - {player2_name} ({p2['snowie_error_rate']}) Матч до {duration}\n\n",
                        parse_mode="HTML",
                    )
        except Exception as e:
            logger.error(f"Error sending message to group: {e}")

    if duration == 0:
        descrease_result = await user_dao.decrease_analiz_balance(user_info.id, ServiceType.MONEYGAME)
    if descrease_result:
        data = await state.get_data()
        pr_values = data.get("pr_values", {})
        for player in players_metrics.keys():
            pr_values.setdefault(player, []).append(abs(players_metrics[player].get("snowie_error_rate", 0)))
        await state.update_data(pr_values=pr_values)

        dao = DetailedAnalysisDAO(session)
        await dao.add(SDetailedAnalysis(**player_data))
        
        formatted_analysis = format_detailed_analysis(get_analysis_data(analysis_data), i18n)
        await message.answer(
            f"{formatted_analysis}\n\n",
            parse_mode="HTML",
            reply_markup=MainKeyboard.build(user_role=user_info.role, i18n=i18n)
        )
        return True
    else:
        await message.answer(i18n.auto.analyze.error.balance(), reply_markup=MainKeyboard.build(user_role=user_info.role, i18n=i18n))
        return False
    

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
        duration = data.get("duration", 0)
        
        # Update user player_username if needed
        user_dao = UserDAO(session_without_commit)
        if not user_info.player_username or user_info.player_username != selected_player:
            user_info.player_username = selected_player
            await user_dao.update(user_info.id, {"player_username": selected_player})
            logger.info(f"Updated player_username for user {user_info.id} to {selected_player}")
        

        process_result = await process_single_analysis(
                callback.message, state, user_info, i18n, analysis_data, file_name, file_path,
                selected_player, session=session_without_commit, duration=duration
            )
        
        all_analysis_datas.append(analysis_data)
        successful_count += 1
        
        # Update state for next file
        file_paths = data.get("file_paths", [])[1:]  # Remaining files
        await state.update_data(file_paths=file_paths)
        logger.info("FILE PATHS AFTER SELECTION: " + str(file_paths))
        await state.update_data(
            file_paths=file_paths,
            all_analysis_datas=all_analysis_datas,
            successful_count=successful_count
        )
        
        await callback.message.delete()

        try:
            await callback.message.bot.delete_message(chat_id=callback.message.chat.id, message_id=progress_message_id)
        except:
            pass
        progress_message = await callback.message.answer(i18n.auto.batch.progress(current = current_file_idx, total = total_files))
        if process_result:
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
                    file_paths = file_paths[1:] 
                    await state.update_data(file_paths=file_paths)
                    selected_player = user_info.player_username
                    process_result = await process_single_analysis(
                        callback.message, state, user_info, i18n, analysis_data, new_file_name, new_file_path,
                        selected_player, session=session_without_commit, duration=duration
                    )
                    all_analysis_datas.append(analysis_data)
                    successful_count += 1
                    if not process_result:
                        break
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
                        progress_message_id=progress_message.message_id,
                        duration=duration
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
        try:
            await callback.message.bot.delete_message(chat_id=callback.message.chat.id, message_id=progress_message.message_id)
        except:
            pass
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
        #сохраняем дату в редис для пдф
        await redis_client.set(f"batch_analysis_data:{user_info.id}", json.dumps(all_analysis_datas), expire=3600)
        data = await state.get_data()
        
        #формируем сообщение с пр
        pr_values = data.get("pr_values", [])
        ru_i18n: TranslatorRunner = translator_hub.get_translator_by_locale(
                'ru'
            )
        group_pr_msg = '<b>' + ru_i18n.auto.batch.summary_pr_header(count=successful_count, time=datetime.now().strftime("%H:%M"), date=datetime.now().strftime("%d.%m.%y")) + "</b>\n\n"
        user_pr_msg = '<b>' + i18n.auto.batch.summary_pr_header(count=successful_count, time=datetime.now().strftime("%H:%M"), date=datetime.now().strftime("%d.%m.%y")) + "</b>\n\n"
        players_avg_pr = {
            player: abs(calculate_average_analysis(pr))
            for player, pr in pr_values.items()
        }
        sorted_players = sorted(players_avg_pr.items(), key=lambda x: x[1])

        for player, avg_pr in sorted_players:
            pr_list = ", ".join([f"{val:.2f}" for val in pr_values[player]])
            group_pr_msg += ru_i18n.auto.batch.summary_pr(
                player=player, pr_list=pr_list, average_pr=f"{avg_pr:.2f}"
            ) + '\n\n'
            user_pr_msg += i18n.auto.batch.summary_pr(
                player=player, pr_list=pr_list, average_pr=f"{avg_pr:.2f}"
            ) + '\n\n'
        
        sorted_players = sorted(players_avg_pr.items(), key=lambda x: x[1])
        players_order_str = ",".join([player for player, _ in sorted_players])
        players_order_str = players_order_str + f"({datetime.now().strftime('%d.%m.%y')}_{datetime.now().strftime('%H:%M')}).pdf"
        logger.info('players_order_str')
        await redis_client.set(
            f"pdf_file_name:{user_info.id}",
            players_order_str,
            expire=3600
        )
        await redis_client.set(
            f"user_pr_msg:{user_info.id}",
            user_pr_msg,
            expire=3600
        )
        #отправляем сообщения юзеру и в группу
        try:
            pdf_pages = []
            if user_pr_msg:
                pdf_pages.append(make_page(user_pr_msg, 22))
            for data in all_analysis_datas:            
                pdf_pages.append(make_page(format_detailed_analysis(get_analysis_data(data), i18n), 11))
            pdf_bytes = merge_pages(pdf_pages)
            group_pr_msg += '\n🎲'
            await message.bot.send_document(
                chat_id = settings.CHAT_GROUP_ID,
                document=BufferedInputFile(
                    pdf_bytes,
                    filename=players_order_str
                ),
                caption = group_pr_msg,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Error sending group PR message: {e}")
        await message.answer(
            user_pr_msg,
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
        file_name_key = f"pdf_file_name:{user_info.id}"
        user_pr_msg_key = f"user_pr_msg:{user_info.id}"
        user_pr_msg = await redis_client.get(user_pr_msg_key)
        file_name = await redis_client.get(file_name_key)
        file_type = file_name.split('.')[-1] if file_name else 'pdf'
        file_name = file_name.replace(file_type, 'pdf') if file_name else 'batch_analysis.pdf'
        analysis_data_json = await redis_client.get(key)
        if not analysis_data_json:
            await callback.message.answer(i18n.auto.batch.no_data_pdf())
            return
        analysis_data = json.loads(analysis_data_json)
        pdf_pages = []
        if user_pr_msg:
            pdf_pages.append(make_page(user_pr_msg, 22))
        for data in analysis_data:            
            pdf_pages.append(make_page(format_detailed_analysis(get_analysis_data(data), i18n), 11))
        pdf_bytes = merge_pages(pdf_pages)
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
        await redis_client.delete(file_name_key)
        await redis_client.delete(user_pr_msg_key)
    else:
        await callback.message.answer(i18n.auto.analyze.no_pdf())