import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, StateFilter
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
import pytz
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger
import os
import json

from bot.common.filters.user_info import UserInfo
from bot.common.func.func import (
    format_detailed_analysis,
    get_analysis_data,
    get_user_file_name,
)
from bot.common.func.waiting_message import WaitingMessageManager
from bot.common.func.yadisk import save_file_to_yandex_disk
from bot.common.kbds.markup.cancel import get_cancel_kb
from bot.common.kbds.markup.main_kb import MainKeyboard
from bot.db.dao import DetailedAnalysisDAO, UserDAO
from bot.db.models import User
from bot.common.func.analiz_func import analyze_mat_file
from bot.db.schemas import SDetailedAnalysis, SUser

from bot.common.utils.i18n import get_all_locales_for_key
from bot.config import translator_hub
from typing import TYPE_CHECKING
from fluentogram import TranslatorRunner

if TYPE_CHECKING:
    from locales.stub import TranslatorRunner

auto_analyze_router = Router()


class AutoAnalyzeDialog(StatesGroup):
    file = State()


@auto_analyze_router.message(
    F.text.in_(
        get_all_locales_for_key(translator_hub, "keyboard-user-reply-autoanalyze")
    )
)
async def start_auto_analyze(
    message: Message, state: FSMContext, i18n: TranslatorRunner
):
    await state.set_state(AutoAnalyzeDialog.file)
    await message.answer(i18n.auto.analyze.submit(), reply_markup=get_cancel_kb(i18n))


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
    try:
        waiting_manager = WaitingMessageManager(message.chat.id, message.bot, i18n)
        file = message.document
        if not file.file_name.endswith(".mat"):
            return await message.answer(i18n.auto.analyze.invalid())

        # Создаем директорию если её нет
        files_dir = os.path.join(os.getcwd(), "files")
        os.makedirs(files_dir, exist_ok=True)
        await waiting_manager.start()
        file_name = file.file_name.replace(" ", "")
        file_path = os.path.join(files_dir, file_name)

        await message.bot.download(file.file_id, destination=file_path)

        loop = asyncio.get_running_loop()
        analysis_result = await loop.run_in_executor(None, analyze_mat_file, file_path)
        analysis_data = await loop.run_in_executor(None, json.loads, analysis_result)

        player_names = list(analysis_data["chequerplay"].keys())
        if len(player_names) != 2:
            raise ValueError("Incorrect number of players in analysis")

        # Генерируем новое имя файла
        moscow_tz = pytz.timezone("Europe/Moscow")
        current_date = datetime.now(moscow_tz).strftime("%d.%m.%y-%H.%M.%S")
        new_file_name = f"{current_date}:{player_names[0]}:{player_names[1]}.mat"
        new_file_path = os.path.join(files_dir, new_file_name)

        # Переименовываем файл
        os.rename(file_path, new_file_path)
        try:
            asyncio.create_task(save_file_to_yandex_disk(new_file_path, new_file_name))
        except Exception as e:
            logger.error(f"Error saving file to Yandex Disk: {e}")

        if user_info.player_username and user_info.player_username in player_names:
            selected_player = user_info.player_username
            game_id = f"auto_{message.from_user.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            player_data = {
                "user_id": message.from_user.id,
                "player_name": selected_player,
                "file_name": new_file_name,
                "file_path": new_file_path,
                "game_id": game_id,
                **get_analysis_data(analysis_data, selected_player),
            }

            dao = DetailedAnalysisDAO(session_without_commit)
            await dao.add(SDetailedAnalysis(**player_data))

            user_dao = UserDAO(session_without_commit)
            await user_dao.decrease_analiz_balance(user_info.id)

            await session_without_commit.commit()

            formatted_analysis = format_detailed_analysis(analysis_data, i18n)
            await waiting_manager.stop()
            await message.answer(
                f"{formatted_analysis}\n\n",
                parse_mode="HTML",
                reply_markup=MainKeyboard.build(user_info.role, i18n),
            )
            await state.clear()

        else:
            await state.update_data(
                analysis_data=analysis_data,
                file_name=new_file_name,
                file_path=new_file_path,
                player_names=player_names,
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

    except Exception as e:
        logger.error(f"Ошибка при автоматическом анализе файла: {e}")
        await message.answer(i18n.auto.analyze.error.parse())
        await waiting_manager.stop()


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

        await user_dao.decrease_analiz_balance(user_info.id)

        formatted_analysis = format_detailed_analysis(analysis_data, i18n)

        await callback.message.delete()
        await callback.message.answer(
            f"{formatted_analysis}\n\n",
            parse_mode="HTML",
            reply_markup=MainKeyboard.build(user_info.role, i18n),
        )
        await session_without_commit.commit()
        await state.clear()

    except Exception as e:
        logger.error(f"Ошибка при сохранении выбора игрока: {e}")
        await callback.message.answer(i18n.auto.analyze.error.save())
