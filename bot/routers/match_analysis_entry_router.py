"""Вход в кабинет «Анализ матча» по команде /match_analysis."""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, WebAppInfo
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select

from bot.common.filters.user_info import UserInfo
from bot.config import settings
from bot.db.database import async_session_maker
from bot.db.models import UserMatchAnalysis


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
    is_admin = user_id in settings.ROOT_ADMIN_IDS
    has_grants = False
    if not is_admin:
        async with async_session_maker() as session:
            row = await session.scalar(
                select(UserMatchAnalysis.id)
                .where(UserMatchAnalysis.user_id == user_id)
                .limit(1)
            )
            has_grants = row is not None
    if not is_admin and not has_grants:
        await message.answer(
            "Кабинет доступен администраторам или пользователям с выданными анализами."
        )
        return
    await message.answer(
        "Кабинет «Анализ матча» — сохранённые протоколы с аудио-комментариями к ходам.",
        reply_markup=get_match_analysis_cabinet_kb(),
    )
