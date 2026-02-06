from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import WebAppInfo
from bot.config import settings

pokaz_router = Router()


@pokaz_router.message(Command("pokaz"))
async def pokaz_command(message: Message):
    """
    Обработчик команды /pokaz - отправляет сообщение с кнопкой веб-приложения
    """
    chat_id = message.from_user.id
    
    kb = InlineKeyboardBuilder()
    web_app_url = f'{settings.MINI_APP_URL}/pokaz?chat_id={chat_id}'
    kb.button(
        text="Открыть редактор позиций",
        web_app=WebAppInfo(url=web_app_url)
    )
    kb.adjust(1)
    
    await message.answer(
        "Откройте редактор позиций:",
        reply_markup=kb.as_markup()
    )
