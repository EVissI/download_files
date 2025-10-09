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
    await state.clear()
    doc = message.document
    fname = doc.file_name
    if not fname.lower().endswith(".mat"):
        await message.reply("Пожалуйста, пришлите .mat файл.")
        return

    tmp_in = os.path.join(tempfile.gettempdir(), random_filename(ext=".mat", length=8))
    tmp_out = os.path.join(tempfile.gettempdir(), random_filename(ext=".json", length=8))

    try:
        await message.reply("Принял файл, начинаю обработку...")
        file = await message.bot.get_file(doc.file_id)
        with open(tmp_in, "wb") as f:
            await message.bot.download_file(file.file_path, f)

        await asyncio.to_thread(process_mat_file, tmp_in, tmp_out)

        with open(tmp_out, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, dict):
            data = data.get("entries") or data.get("turns") or []

        for entry in data:
            # ✅ используем нашу функцию
            hints = parse_hints_with_log(entry)
            if not hints:
                continue

            table = PrettyTable()
            table.field_names = ["№", "Ход", "Вероятности", "Eq"]
            table.align = "l"

            for h in hints:
                idx = h.get("idx", "")
                move = (h.get("move") or "").strip()
                move = re.sub(r"(?i)\b(?:cubeful\s*)?\d+-ply\b", "", move)
                move = " ".join(move.split()).strip(" .:-")
                eq = h.get("eq", 0.0)
                probs = h.get("probs") or []
                probs_display = (
                    ", ".join(f"{p:.3f}" for p in probs[:3]) if probs else "—"
                )
                table.add_row([idx, move, probs_display, f"{eq:+.3f}"])

            header = f"Файл: {fname}\nХод: {entry.get('turn', '—')} игрок: {entry.get('player', '—')}\n"
            try:
                await message.answer(
                    f"{header}<pre>{table.get_string()}</pre>", parse_mode="HTML"
                )
            except TelegramAPIError:
                await message.answer(header + "\n" + table.get_string())

            await asyncio.sleep(0.5)

    except Exception:
        logger.exception("Ошибка при обработке hint viewer")
        await message.reply("Ошибка при обработке файла.")
    finally:
        for tmp in (tmp_in, tmp_out):
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except Exception:
                pass
        await state.clear()

def parse_hints_with_log(entry: dict) -> list:
    """
    Безопасно извлекает и парсит hints из entry, с логированием содержимого.
    Возвращает список подсказок или пустой список.
    """
    hints_raw = entry.get("hints")

    logger.info(f"Raw hints type: {type(hints_raw).__name__}")
    if isinstance(hints_raw, (list, dict)):
        logger.info(f"Raw hints (list/dict, first 200 chars): {str(hints_raw)[:200]}")
    elif isinstance(hints_raw, str):
        logger.info(f"Raw hints (string, first 200 chars): {hints_raw[:200]}")
    else:
        logger.info(f"Raw hints value: {repr(hints_raw)}")

    if isinstance(hints_raw, str):
        try:
            hints = json.loads(hints_raw)
        except json.JSONDecodeError:
            logger.warning(f"❌ Не удалось распарсить hints как JSON: {hints_raw[:200]}")
            hints = []
    else:
        hints = hints_raw or []

    if not isinstance(hints, list):
        logger.warning(f"⚠️ hints не список после парсинга: {type(hints).__name__}")
        return []

    return hints