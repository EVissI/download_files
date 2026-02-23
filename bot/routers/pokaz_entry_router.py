from aiogram import Router, F
from aiogram.types import Message
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import WebAppInfo

from bot.config import settings, translator_hub
from bot.common.filters.user_info import UserInfo
from bot.common.utils.i18n import get_all_locales_for_key


pokaz_entry_router = Router()


def get_pokaz_entry_kb(chat_id: int, lang: str = None, button_text: str = None) -> InlineKeyboardMarkup:
    """Клавиатура при нажатии кнопки Позиции: редактор позиций."""
    kb = InlineKeyboardBuilder()
    lang_param = f"&lang={lang}" if lang in ("ru", "en") else ""
    text = button_text or "Открыть редактор позиций"
    kb.button(
        text=text,
        web_app=WebAppInfo(url=f"{settings.MINI_APP_URL}/pokaz?chat_id={chat_id}{lang_param}"),
    )
    kb.adjust(1)
    return kb.as_markup()


@pokaz_entry_router.message(
    F.text.in_(get_all_locales_for_key(translator_hub, "keyboard-user-reply-pokaz")),
    UserInfo(),
)
async def handle_pokaz_button(message: Message, i18n, user_info):
    """Отправляет текст с кнопками при нажатии кнопки Позиции."""
    chat_id = message.from_user.id if message.from_user else 0
    lang = (user_info.lang_code or "ru") if user_info else "ru"
    await message.answer(
        i18n.user.pokaz.select_action(),
        reply_markup=get_pokaz_entry_kb(chat_id, lang, i18n.user.pokaz.open_editor()),
    )
