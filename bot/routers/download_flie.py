from ast import literal_eval
import json
import os
from datetime import datetime
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.filters import StateFilter
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from bot.common.filters.user_info import UserInfo
from bot.common.func.func import get_user_file_name
from bot.common.func.yadisk import save_file_to_yandex_disk
from bot.common.kbds.inline.answer import get_admin_answer_kb
from bot.common.kbds.markup.cancel import get_cancel_kb
from bot.common.texts import get_text
from bot.db.dao import AnalisisDAO, UserDAO
from bot.db.models import User
from bot.db.schemas import SAnalysis, SUser
from bot.db.redis import redis_client
from bot.common.kbds.markup.main_kb import MainKeyboard

download_router = Router()


class FileDialog(StatesGroup):
    file = State()


@download_router.message(F.text == MainKeyboard.get_user_kb_text().get("analize"))
async def start_file_dialog(message: Message, state: FSMContext):
    await state.set_state(FileDialog.file)
    await message.answer(get_text("send_file"), reply_markup=get_cancel_kb())


@download_router.message(
    F.text == get_text("cancel"), StateFilter(FileDialog.file), UserInfo()
)
async def cancel_file_dialog(message: Message, state: FSMContext, user_info: User):
    await state.clear()
    await message.answer(message.text, reply_markup=MainKeyboard.build(user_info.role))


@download_router.message(F.document, StateFilter(FileDialog.file), UserInfo())
async def handle_backgammon_file(
    message: Message, session_without_commit: AsyncSession, user_info: User
):
    try:
        file = message.document
        if not file.file_name.endswith((".sgf", ".mat")):
            return await message.answer("Please send .sgf or .mat file.")

        # Создаем директорию если её нет
        files_dir = os.path.join(os.getcwd(), "files")
        os.makedirs(files_dir, exist_ok=True)

        file_name = get_user_file_name(message.from_user.id, file.file_name, files_dir)
        file_path = os.path.join(files_dir, file_name)
        await save_file_to_yandex_disk(file_path, file_name)
        await message.bot.download(file.file_id, destination=file_path)

        # Генерируем уникальный ID для анализа
        analysis_id = f"analysis_{message.from_user.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Сохраняем информацию в Redis
        analysis_data = {
            "file_info": {
                "file_name": file_name,
                "file_path": file_path,
                "original_name": file.file_name,
            },
            "user_id": message.from_user.id,
            "analysis_id": analysis_id,
            "created_at": datetime.now().isoformat(),
        }
        await redis_client.set(
            f"analysis:{message.from_user.id}:{analysis_id}", json.dumps(analysis_data)
        )

        user_dao = UserDAO(session_without_commit)
        admins = await user_dao.find_all(filters=SUser(role=User.Role.ADMIN.value))

        await message.answer(
            get_text("file_saved"), reply_markup=MainKeyboard.build(user_info.role)
        )

        for admin in admins:
            try:
                sent_message = await message.bot.send_document(
                    chat_id=admin.id,
                    document=FSInputFile(file_path),
                    caption=f"Received new file from @{message.from_user.username or message.from_user.id}\nAnalysis ID: {analysis_id}",
                    reply_markup=get_admin_answer_kb(message.from_user.id, analysis_id),
                )
                await redis_client.add_admin_message(
                    user_id=message.from_user.id,
                    admin_id=admin.id,
                    message_id=sent_message.message_id,
                )
            except Exception as e:
                logger.error(f"Не удалось отправить файл админу {admin.id}: {e}")

    except Exception as e:
        logger.error(f"Ошибка при обработке файла: {e}")
        await message.answer("An error occurred while processing the file.")


@download_router.message(StateFilter(FileDialog.file), ~F.document)
async def handle_invalid_file(message: Message, state: FSMContext):
    await message.answer(get_text("file_save_error"), reply_markup=get_cancel_kb())
    await state.clear()


def parse_value(value, default=0):
    """
    Преобразует значение в число, если это возможно.
    Если значение равно "нет" или не может быть преобразовано, возвращает default.
    """
    if value == "нет":
        return default
    try:
        return float(value) if isinstance(value, str) and "." in value else int(value)
    except ValueError:
        return default


@download_router.callback_query(F.data.startswith("player:"))
async def handle_player_selection(
    callback: CallbackQuery, session_with_commit: AsyncSession
):
    try:
        # Удаляем клавиатуру и обновляем текст
        await callback.message.edit_reply_markup(reply_markup=None)
        updated_text = "\n".join(
            line
            for line in callback.message.text.splitlines()
            if line.strip() != "Which player are you?"
        )
        await callback.message.edit_text(updated_text)

        # Парсим данные из callback
        parts = callback.data.split(":")
        if len(parts) != 3:
            await callback.message.answer("Incorrect data format.")
            return

        selected_player = parts[1]
        analysis_id = parts[2]
        user_id = callback.message.chat.id
        redis_key = f"analysis:{user_id}:{analysis_id}"

        # Получаем данные из Redis
        redis_data = await redis_client.get(redis_key)
        if not redis_data:
            logger.error(f"Данные анализа не найдены: {redis_key}")
            await callback.message.answer("No analysis data found.")
            return

        # Проверяем наличие всех необходимых полей
        try:
            analysis_data = json.loads(redis_data)
            if not all(key in analysis_data for key in ["summary", "file_info"]):
                logger.error(f"Неполные данные анализа: {analysis_data}")
                await callback.message.answer("The analysis data is corrupted.")
                return

            summary = analysis_data["summary"]
            file_info = analysis_data["file_info"]

            if not all(key in file_info for key in ["file_name", "file_path"]):
                logger.error(f"Неполные данные о файле: {file_info}")
                await callback.message.answer("File data is corrupted.")
                return

        except json.JSONDecodeError as e:
            logger.error(f"Ошибка декодирования JSON: {e}")
            await callback.message.answer("Error processing analysis data.")
            return

        if selected_player not in summary:
            logger.error(f"Игрок {selected_player} не найден в данных анализа")
            await callback.message.answer(
                "The selected player is missing from the analysis data."
            )
            return

        # Формируем данные для записи в базу
        db_analysis_data = {
            "user_id": user_id,
            "mistake_total": parse_value(summary[selected_player].get("error", "нет")),
            "mistake_doubling": parse_value(
                summary[selected_player].get("doubling", "нет")
            ),
            "mistake_taking": parse_value(
                summary[selected_player].get("taking", "нет")
            ),
            "luck": parse_value(
                summary[selected_player].get("luck", "нет"), default=0.0
            ),
            "pr": parse_value(
                summary[selected_player].get("quality", "нет"), default=0.0
            ),
            "file_name": file_info["file_name"],
            "file_path": file_info["file_path"],
            "game_id": analysis_id,
        }

        # Записываем в базу
        dao = AnalisisDAO(session_with_commit)
        await dao.add(SAnalysis(**db_analysis_data))

        # Очищаем Redis после успешной записи
        await redis_client.delete(redis_key)
        logger.info(f"Анализ {analysis_id} успешно сохранен для пользователя {user_id}")

        await callback.message.answer(
            "The result has been saved. Thank you for using the bot!"
        )

    except Exception as e:
        logger.error(f"Ошибка при записи результата в базу: {e}")
        await callback.message.answer("An error occurred while writing the result.")
