from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, WebAppInfo
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.config import settings


pip_count_cabinet_entry_router = Router()


def get_pip_count_cabinet_entry_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text="Открыть кабинет «Подсчёт пипсов»",
        web_app=WebAppInfo(
            url=f"{settings.MINI_APP_URL.rstrip('/')}/pip-count-cabinet"
        ),
    )
    kb.adjust(1)
    return kb.as_markup()


@pip_count_cabinet_entry_router.message(Command("pip_count_cabinet"))
async def handle_pip_count_cabinet_command(message: Message):
    """Вход в кабинет pip-count (пока только для ROOT_ADMIN_IDS)."""
    user_id = message.from_user.id if message.from_user else None
    if user_id is None or user_id not in settings.ROOT_ADMIN_IDS:
        await message.answer("Команда доступна только администраторам.")
        return

    await message.answer(
        "Кабинет «Подсчёт пипсов»:",
        reply_markup=get_pip_count_cabinet_entry_kb(),
    )
