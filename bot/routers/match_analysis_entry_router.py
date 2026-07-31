"""Вход в кабинет «Анализ матча» по команде /match_analysis (только ROOT_ADMIN)."""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, WebAppInfo
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.common.filters.user_info import UserInfo
from bot.config import settings


match_analysis_entry_router = Router()


def get_match_analysis_cabinet_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text="Открыть «Анализ матча»",
        web_app=WebAppInfo(
            url=f"{settings.MINI_APP_URL.rstrip('/')}/match-analysis-cabinet"
        ),
    )
    kb.adjust(1)
    return kb.as_markup()


@match_analysis_entry_router.message(Command("match_analysis"), UserInfo())
async def handle_match_analysis_command(message: Message, user_info):
    user_id = int(user_info.id) if user_info else int(message.from_user.id)
    if user_id not in settings.ROOT_ADMIN_IDS:
        await message.answer("Команда доступна только администраторам.")
        return
    await message.answer(
        "Кабинет «Анализ матча» — сохранённые протоколы с аудио-комментариями к ходам.",
        reply_markup=get_match_analysis_cabinet_kb(),
    )
