from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup

from typing import TYPE_CHECKING
from fluentogram import TranslatorRunner
from bot.common.utils.i18n import get_all_locales_for_key
if TYPE_CHECKING:
    from locales.stub import TranslatorRunner

class ProfileCallback(CallbackData, prefix="profile"):
    action: str

def get_profile_kb(i18n: TranslatorRunner) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=i18n.user.profile.inline_button.change_language(),
        callback_data=ProfileCallback(action="change_lang").pack()
    )
    builder.button(
        text=i18n.user.profile.inline_button.my_stats(),
        callback_data=ProfileCallback(action="my_stat").pack()
    )

    builder.adjust(1)
    return builder.as_markup()

class ProfileChangeLanguageCallback(CallbackData, prefix="profile_change_language"):
    language: str = "en"  # Default language
    action: str

def get_profile_change_language_kb(i18n: TranslatorRunner) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=i18n.keyboard.inline.change_language.ru(),
        callback_data=ProfileChangeLanguageCallback(action="change_language", language='ru').pack()
    )
    builder.button(
        text=i18n.keyboard.inline.change_language.en(),
        callback_data=ProfileChangeLanguageCallback(action="change_language", language='en').pack()
    )
    builder.button(
        text=i18n.keyboard.reply.back(),
        callback_data=ProfileChangeLanguageCallback(action="back").pack()
    )
    builder.adjust(2)
    return builder.as_markup()