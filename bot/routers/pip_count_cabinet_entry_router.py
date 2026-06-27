from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, WebAppInfo
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.common.filters.user_info import UserInfo
from bot.common.utils.i18n import get_all_locales_for_key, get_text_for_locale
from bot.config import settings, translator_hub
from bot.db.dao import UserContentCardDAO
from bot.db.models import ContentCardPool


pip_count_cabinet_entry_router = Router()


def get_pip_count_cabinet_entry_kb(button_text: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text=button_text,
        web_app=WebAppInfo(
            url=f"{settings.MINI_APP_URL.rstrip('/')}/pip-count-cabinet"
        ),
    )
    kb.adjust(1)
    return kb.as_markup()


async def handle_pip_count_cabinet_entry(message: Message, user_info) -> None:
    lang = (user_info.lang_code or "ru") if user_info else "ru"
    from bot.db.database import async_session_maker

    async with async_session_maker() as session:
        links = await UserContentCardDAO(session).get_all_by_user(int(user_info.id))

    pip_links = [
        row
        for row in links
        if row.content_card and row.content_card.card_pool == ContentCardPool.PIP_COUNT
    ]

    if not pip_links:
        no_cards_text = get_text_for_locale(
            translator_hub,
            lang,
            "user-pip-count-cabinet-no_cards",
            fallback='Для получения карточек можно обратиться <a href="https://t.me/Learn_bg">@Learn_bg</a>',
        )
        await message.answer(no_cards_text, parse_mode="HTML", disable_web_page_preview=True)
        return

    text = get_text_for_locale(
        translator_hub,
        lang,
        "user-pip-count-cabinet-select_action",
        fallback="Для входа в кабинет «Подсчёт пипсов», перейдите по кнопке ниже.",
    )
    button_text = get_text_for_locale(
        translator_hub,
        lang,
        "user-pip-count-cabinet-open_button",
        fallback="Открыть кабинет «Подсчёт пипсов»",
    )
    await message.answer(
        text,
        reply_markup=get_pip_count_cabinet_entry_kb(button_text),
    )


@pip_count_cabinet_entry_router.message(
    F.text.in_(get_all_locales_for_key(translator_hub, "keyboard-user-reply-pip_count_cabinet")),
    UserInfo(),
)
async def handle_pip_count_cabinet_button(message: Message, user_info):
    await handle_pip_count_cabinet_entry(message, user_info)


@pip_count_cabinet_entry_router.message(Command("pip_count_cabinet"), UserInfo())
async def handle_pip_count_cabinet_command(message: Message, user_info):
    await handle_pip_count_cabinet_entry(message, user_info)
