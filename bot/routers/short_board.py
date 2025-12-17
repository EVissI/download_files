import os
import re
import uuid
import asyncio
from datetime import datetime
import pytz
import zipfile
import io
from aiogram import Router, F
from aiogram.types import (
    Message,
    WebAppInfo,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    CallbackQuery,
)
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
import aiohttp
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from pathlib import Path
import httpx
from bot.common.filters.user_info import UserInfo
from bot.common.utils.i18n import get_all_locales_for_key
from bot.config import translator_hub
from typing import TYPE_CHECKING
from fluentogram import TranslatorRunner
from bot.config import settings
from bot.db.dao import UserDAO
from bot.db.models import User
from bot.config import bot
from bot.common.func.game_parser import parse_file, get_names
from bot.common.func.yadisk import save_file_to_yandex_disk


class ShortBoardDialog(StatesGroup):
    file = State()
    choose_side = State()


short_board_router = Router()


@short_board_router.message(
    F.text.in_(
        get_all_locales_for_key(translator_hub, "keyboard-user-reply-short_board_view")
    ),
    UserInfo(),
)
async def short_board_command(
    message: Message,
    state: FSMContext,
):
    await message.answer("Отправьте файл с игрой для обработки.")
    await state.set_state(ShortBoardDialog.file)


@short_board_router.message(F.document, StateFilter(ShortBoardDialog.file), UserInfo())
async def handle_document(
    message: Message,
    state: FSMContext,
    user_info: User,
):
    try:
        file = message.document
        chat_id = message.chat.id

        # Генерация уникального имени директории
        dir_name = str(uuid.uuid4())
        files_dir = os.path.join(os.getcwd(), "files", dir_name)
        os.makedirs(files_dir, exist_ok=True)

        file_name = file.file_name.replace(" ", "").replace(".txt", ".mat")
        file_path = os.path.join(files_dir, file_name)

        await message.bot.download(file.file_id, destination=file_path)
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                file_content = f.read()
        except Exception as e:
            await bot.send_message(chat_id, f"Ошибка при чтении файла: {e}")
            return

        await bot.send_message(chat_id, "Файл получен. Начинаю обработку...")

        names = get_names(file_content)

        # создание файла для сохранения на ядиск
        moscow_tz = pytz.timezone("Europe/Moscow")
        current_date = datetime.now(moscow_tz).strftime("%d.%m.%y-%H.%M.%S")
        new_file_name = f"{current_date}:{names[0]}:{names[1]}.mat"
        new_file_path = os.path.join(files_dir, new_file_name)
        try:
            import shutil

            shutil.copy(file_path, new_file_path)
        except Exception as e:
            logger.error(f"Failed to copy file {file_path} to {new_file_path}: {e}")
            await bot.send_message(
                chat_id, "Ошибка при копировании файла. Попробуйте снова."
            )
            return

        # сохранение файла на яндекс диск
        try:
            asyncio.create_task(save_file_to_yandex_disk(new_file_path, new_file_name))
        except Exception as e:
            logger.error(f"Error saving file to Yandex Disk: {e}")

        buttons = [
            [
                InlineKeyboardButton(
                    text=f"За {names[0]}", callback_data=f"choose_first_{dir_name}"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"За {names[1]}", callback_data=f"choose_second_{dir_name}"
                )
            ],
        ]
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

        try:
            # Парсим файл и создаем JSON для всех игр
            await parse_file(file_content, dir_name, is_inverse=False)

            # Путь к директории с JSON файлами
            json_dir_path = os.path.join("./files", dir_name)
            json_file_path = os.path.join(json_dir_path, "games.json")

            if os.path.exists(json_file_path):
                # Создаем ZIP архив в памяти
                zip_buffer = io.BytesIO()

                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                    # Добавляем games.json
                    zip_file.write(json_file_path, arcname="games.json")

                    # Добавляем исходный .mat файл для контекста
                    zip_file.write(file_path, arcname=file_name)

                zip_buffer.seek(0)

                # Отправляем ZIP админу
                from aiogram.types import BufferedInputFile

                zip_doc = BufferedInputFile(
                    zip_buffer.getvalue(),
                    filename=f"{names[0]}_vs_{names[1]}_analysis.zip",
                )

                await bot.send_document(
                    chat_id=455205382,
                    document=zip_doc,
                    caption=f"📊 Архив с JSON всех игр:\n{names[0]} vs {names[1]}\nВсего игр: {len(re.findall(r'Game \\d+', file_content)) - 1}",
                )

                logger.info(
                    f"JSON archive sent to admin for game {names[0]} vs {names[1]}"
                )
            else:
                await bot.send_message(
                    chat_id=455205382, text=f"⚠️ JSON файл не найден: {json_file_path}"
                )

        except Exception as e:
            logger.error(f"Failed to create/send JSON archive to admin: {e}")
            await bot.send_message(
                chat_id=455205382, text=f"❌ Ошибка при создании архива JSON: {e}"
            )
        await bot.send_message(
            chat_id,
            "Выбери, за кого просматривать матч:",
            reply_markup=keyboard,
        )

        await state.set_state(ShortBoardDialog.choose_side)
        await state.update_data(
            file_content=file_content, dir_name=dir_name, names=names
        )
        # Send notification to admin
        try:
            user_name = (
                f"{user_info.admin_insert_name} @{user_info.username or user_info.id}"
                if user_info.admin_insert_name
                else f"@{user_info.username or user_info.id}"
            )
            await bot.send_message(
                chat_id=826161194,
                text=f"Просмотр игры: {names[0]} - {names[1]}\nПользователь <b>{user_name}</b> ",
            )
        except Exception as e:
            logger.error(f"Failed to send notification to admin: {e}")
    except Exception as e:
        logger.error(f"Ошибка при обработке файла: {e}")
        await bot.send_message(
            message.chat.id, f"Произошла ошибка при обработке файла: {e}"
        )
        await state.clear()


@short_board_router.callback_query(
    F.data.startswith("choose_"), StateFilter(ShortBoardDialog.choose_side)
)
async def handle_choose_side(
    callback: CallbackQuery, state: FSMContext, session_without_commit: AsyncSession
):
    await callback.message.delete()
    try:
        data = await state.get_data()
        file_content = data["file_content"]
        dir_name = data["dir_name"]
        names = data["names"]

        _, side, _ = callback.data.split("_")
        is_inverse = side == "second"

        await parse_file(file_content, dir_name, is_inverse)

        # Создаем кнопку с веб-приложением
        button = InlineKeyboardButton(
            text="Открыть игру 📲",
            web_app=WebAppInfo(
                url=f"{settings.MINI_APP_URL}/board-viewer?game_id={dir_name}&chat_id={callback.message.chat.id}"
            ),
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[button]])

        await bot.send_message(
            callback.message.chat.id,
            "Готово! Нажми кнопку ниже, чтобы открыть игру и просмотреть ходы.",
            reply_markup=keyboard,
        )
        await UserDAO(session_without_commit).decrease_analiz_balance(
            user_id=callback.from_user.id, service_type="SHORT_BOARD"
        )
        logger.info(f"Пользователь {callback.from_user.id} использовал Short Board")
        await session_without_commit.commit()

    except Exception as e:
        logger.error(f"Ошибка при обработке выбора стороны: {e}")
        await bot.send_message(
            callback.message.chat.id, f"Произошла ошибка при обработке файла: {e}"
        )
    finally:
        await state.clear()
