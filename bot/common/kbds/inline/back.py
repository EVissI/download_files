from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup

from typing import TYPE_CHECKING
from fluentogram import TranslatorRunner
if TYPE_CHECKING:
    from locales.stub import TranslatorRunner

class BackCallback(CallbackData, prefix="back"):
    context: str

def get_back_kb(i18n: TranslatorRunner, context: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=i18n.keyboard.reply.back(),
        callback_data=BackCallback(context=context).pack()
    )
    builder.adjust(1)
    return builder.as_markup()