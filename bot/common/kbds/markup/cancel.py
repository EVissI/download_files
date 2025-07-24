from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder

from fluentogram import TranslatorRunner
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from locales.stub import TranslatorRunner

def get_cancel_kb(i18n:TranslatorRunner) -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    kb.add(KeyboardButton(text=i18n.keyboard.reply.cancel()))
    return kb.as_markup(resize_keyboard=True)

