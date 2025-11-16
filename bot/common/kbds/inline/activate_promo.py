from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup
from typing import TYPE_CHECKING
from fluentogram import TranslatorRunner
from bot.common.utils.i18n import get_all_locales_for_key
if TYPE_CHECKING:
    from locales.stub import TranslatorRunner

class PromoCallback(CallbackData, prefix="activate_promo"):
    action: str

def get_activate_promo_keyboard(i18n:TranslatorRunner) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=i18n.user.inline.activate_promo_2(),
        callback_data=PromoCallback(action='activate').pack(),
    )
    builder.button(
        text=i18n.user.inline.take_promo(),
        url="https://t.me/Matchbg",
    )
    return builder.as_markup()

def get_activate_promo_without_link_keyboard(i18n:TranslatorRunner) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=i18n.user.inline.activate_promo_2(),
        callback_data=PromoCallback(action='activate').pack(),
    )
    return builder.as_markup()