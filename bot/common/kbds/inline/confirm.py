from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup

from typing import TYPE_CHECKING
from fluentogram import TranslatorRunner
if TYPE_CHECKING:
    from locales.stub import TranslatorRunner

class ConfrimCallback(CallbackData, prefix="back"):
    context: str
    action:str

def get_confrim_kb(i18n: TranslatorRunner, context: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=i18n.keyboard.confirm(),
        callback_data=ConfrimCallback(context=context, action='confirm').pack()
    )
    builder.button(
        text=i18n.keyboard.reply.cancel(),
        callback_data=ConfrimCallback(context=context, action='back').pack()
    )
    builder.adjust(1)
    return builder.as_markup()