
from aiogram.types import WebAppInfo, ReplyKeyboardMarkup, ReplyKeyboardRemove,KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from typing import TYPE_CHECKING
from fluentogram import TranslatorRunner

if TYPE_CHECKING:
    from locales.stub import TranslatorRunner

def get_contatct_request(i18n:TranslatorRunner) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=i18n.user.static.share_phone, request_contact=True)],
            [KeyboardButton(text=i18n.keyboard.reply.cancel)],
        ],
        resize_keyboard=True,
    )