from aiogram import Router, F
from aiogram.types import Message, WebAppInfo
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.db.dao import UserContentCardDAO
from bot.common.filters.user_info import UserInfo
from bot.common.utils.i18n import get_all_locales_for_key, get_text_for_locale
from bot.config import settings, translator_hub


cards_cabinet_entry_router = Router()


def get_cards_cabinet_entry_kb(button_text: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text=button_text,
        web_app=WebAppInfo(url=f"{settings.MINI_APP_URL.rstrip('/')}/cards-cabinet"),
    )
    kb.adjust(1)
    return kb.as_markup()


@cards_cabinet_entry_router.message(
    F.text.in_(get_all_locales_for_key(translator_hub, "keyboard-user-reply-cards_cabinet")),
    UserInfo(),
)
async def handle_cards_cabinet_button(message: Message, user_info):
    lang = (user_info.lang_code or "ru") if user_info else "ru"
    from bot.db.database import async_session_maker

    async with async_session_maker() as session:
        links = await UserContentCardDAO(session).get_all_by_user(int(user_info.id))

    if not links:
        no_cards_text = get_text_for_locale(
            translator_hub,
            lang,
            "user-cards-cabinet-no_cards",
            fallback='Для получения карточек можно обратиться <a href="https://t.me/Learn_bg">@Learn_bg</a>',
        )
        await message.answer(no_cards_text, parse_mode="HTML", disable_web_page_preview=True)
        return

    text = get_text_for_locale(
        translator_hub,
        lang,
        "user-cards-cabinet-select_action",
        fallback="Откройте кабинет карточек по кнопке ниже.",
    )
    button_text = get_text_for_locale(
        translator_hub,
        lang,
        "user-cards-cabinet-open_button",
        fallback="Открыть кабинет карточек",
    )
    await message.answer(
        text,
        reply_markup=get_cards_cabinet_entry_kb(button_text),
    )
