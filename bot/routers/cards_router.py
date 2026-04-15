"""Команда /cards — открытие Web App с личным кабинетом карточек контента."""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.config import settings

cards_router = Router()


@cards_router.message(Command("cards"))
async def cmd_cards(message: Message) -> None:
    if not message.from_user:
        return
    base = settings.MINI_APP_URL.rstrip("/")
    url = f"{base}/cards-cabinet"
    kb = InlineKeyboardBuilder()
    kb.button(text="Мои карточки", web_app=WebAppInfo(url=url))
    kb.adjust(1)
    await message.answer(
        "Личный кабинет: здесь список ваших карточек. Нажмите кнопку, чтобы открыть мини-приложение.",
        reply_markup=kb.as_markup(),
    )
