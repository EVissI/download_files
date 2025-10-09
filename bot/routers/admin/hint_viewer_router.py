from aiogram import Router, F
from aiogram.types import Message
from aiogram.exceptions import TelegramAPIError
from loguru import logger
import asyncio
import tempfile
import os
import json
import re
from prettytable import PrettyTable

from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import StateFilter

from bot.common.func.hint_viewer import process_mat_file, random_filename
from bot.common.kbds.markup.admin_panel import AdminKeyboard

hint_viewer_router = Router()


class HintViewerStates(StatesGroup):
    waiting_file = State()


@hint_viewer_router.message(F.text == AdminKeyboard.get_kb_text()["test"])
async def hint_viewer_start(message: Message, state: FSMContext):
    await state.set_state(HintViewerStates.waiting_file)
    await message.answer(
        "Нажата кнопка просмотра подсказок. Пришлите .mat файл для анализа."
    )


@hint_viewer_router.message(F.document, StateFilter(HintViewerStates.waiting_file))
async def hint_viewer_menu(message: Message, state: FSMContext):
    """
    Принимает .mat файл после нажатия кнопки, запускает process_mat_file -> output json,
    для каждого хода с подсказками отправляет таблицу (prettytable) с:
      № | Ход | Eq | Вероятности (первые 3 значения)
    """
    await state.clear()
    doc = message.document
    fname = doc.file_name or "game.mat"
    if not fname.lower().endswith(".mat"):
        await message.reply("Пожалуйста, пришлите .mat файл.")
        return

    # временные файлы для входа и выхода
    tmp_in = os.path.join(tempfile.gettempdir(), random_filename(ext=".mat", length=8))
    tmp_out = os.path.join(
        tempfile.gettempdir(), random_filename(ext=".json", length=8)
    )

    try:
        await message.reply("Принял файл, начинаю обработку...")
        # сохранить файл локально
        file = await message.bot.get_file(doc.file_id)
        with open(tmp_in, "wb") as f:
            await message.bot.download_file(file.file_path, f)
        # heavy processing in thread
        await asyncio.to_thread(process_mat_file, tmp_in, tmp_out)

        # прочитать результат
        with open(tmp_out, "r", encoding="utf-8") as f:
            data = json.load(f)

        # пройти по записям и отправить таблицы только по ходам с hints
        for entry in data:
            hints = entry.get("hints") or []
            if not hints:
                continue

            # формируем таблицу
            table = PrettyTable()
            table.field_names = ["№", "Ход", "Вероятности", "Eq"]
            table.align = "l"

            for h in hints:
                idx = h.get("idx", "")
                move = (h.get("move") or "").strip()
                # Убираем в тексте маркеры типа "Cubeful 2-ply" или "0-ply", "2-ply" и т.п.
                move = re.sub(r"(?i)\b(?:cubeful\s*)?\d+-ply\b", "", move)
                # Сжимаем лишние пробелы и убираем ведущие/хвостовые знаки пунктуации
                move = " ".join(move.split()).strip(" .:-")
                eq = h.get("eq", 0.0)
                probs = h.get("probs") or []
                # первые три вероятности 
                probs_display = (
                    ", ".join(f"{p:.3f}" for p in probs[:3]) if probs else "—"
                )
                table.add_row([idx, move, probs_display, f"{eq:+.3f}"])

            header = f"Файл: {fname}\nХод: {entry.get('turn', '—')} игрок: {entry.get('player', '—')}\n"
            # отправляем как HTML с <pre> чтобы таблица сохранила форматирование
            try:
                await message.answer(
                    f"{header}<pre>{table.get_string()}</pre>", parse_mode="HTML"
                )
            except TelegramAPIError:
                # fallback — отправка без HTML
                await message.answer(header + "\n" + table.get_string())
            await asyncio.sleep(0.5)  # небольшая пауза между сообщениями

    except Exception:
        logger.exception("Ошибка при обработке hint viewer")
        await message.reply("Ошибка при обработке файла.")
    finally:
        # чистим временные файлы
        try:
            if os.path.exists(tmp_in):
                os.remove(tmp_in)
            if os.path.exists(tmp_out):
                os.remove(tmp_out)
        except Exception:
            pass
        await state.clear()
