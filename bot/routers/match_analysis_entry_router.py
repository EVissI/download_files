"""Вход в кабинет «Анализ матча» по команде /match_analysis и кнопке админ-клавиатуры."""

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message, WebAppInfo
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from loguru import logger
from sqlalchemy import select

from bot.common.filters.user_info import UserInfo
from bot.common.utils.i18n import get_all_locales_for_key
from bot.config import settings, translator_hub
from bot.db.database import async_session_maker
from bot.db.models import MatchAnalysis, User, UserMatchAnalysis
from bot.flask_admin.match_analysis_grant import grant_match_analyses_async


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


def _is_match_analysis_admin(user_id: int, user_info) -> bool:
    return user_id in settings.ROOT_ADMIN_IDS or (
        user_info is not None and user_info.role == User.Role.ADMIN.value
    )


async def _send_match_analysis_cabinet_entry(message: Message, user_info) -> None:
    user_id = int(user_info.id) if user_info else int(message.from_user.id)
    is_admin = _is_match_analysis_admin(user_id, user_info)
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
        'Кабинет "Анализ матча" - просмотр матча с аудио комментариями',
        reply_markup=get_match_analysis_cabinet_kb(),
    )


@match_analysis_entry_router.message(Command("match_analysis"), UserInfo())
async def handle_match_analysis_command(message: Message, user_info):
    await _send_match_analysis_cabinet_entry(message, user_info)


@match_analysis_entry_router.message(
    Command("all_analyses"),
    UserInfo(),
)
async def handle_grant_all_ready_match_analyses(message: Message, user_info):
    """
    Админ: выдать себе все анализы матча (без фильтра is_ready), которых ещё нет.
    Команда: /all_analyses
    """
    user_id = int(user_info.id) if user_info else int(message.from_user.id)
    if not _is_match_analysis_admin(user_id, user_info):
        await message.answer("Команда доступна только администраторам.")
        return

    try:
        async with async_session_maker() as session:
            any_analysis = await session.scalar(select(MatchAnalysis.id).limit(1))
            if any_analysis is None:
                await message.answer("В системе пока нет сохранённых анализов матча.")
                return

            issued = await grant_match_analyses_async(
                session,
                user_id=user_id,
                quantity=None,
                ready_only=False,
                commit=True,
            )
    except Exception as e:
        logger.exception("all_analyses grant failed user_id={}", user_id)
        await message.answer(f"Ошибка выдачи анализов: {e}")
        return

    if issued <= 0:
        await message.answer(
            "У вас уже есть все анализы матча.",
            reply_markup=get_match_analysis_cabinet_kb(),
        )
        return

    await message.answer(
        f"Выдано анализов матча: {issued}.\nОткройте кабинет, чтобы посмотреть.",
        reply_markup=get_match_analysis_cabinet_kb(),
    )


@match_analysis_entry_router.message(
    F.text.in_(
        get_all_locales_for_key(
            translator_hub, "keyboard-admin-reply-match_analysis_cabinet"
        )
    ),
    UserInfo(),
)
async def handle_match_analysis_cabinet_button(message: Message, user_info):
    """Кнопка над «Админпанель» — только у админов в MainKeyboard."""
    if not user_info or user_info.role != User.Role.ADMIN.value:
        await message.answer("Доступно только администраторам.")
        return
    await _send_match_analysis_cabinet_entry(message, user_info)
