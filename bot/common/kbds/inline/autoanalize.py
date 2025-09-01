﻿from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup


class DownloadPDFCallback(CallbackData, prefix="download_pdf"):
    action: str  # "yes" или "no"
    context: str 


def get_download_pdf_kb(i18n, context) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text=i18n.auto.analyze.download_pdf(),
        callback_data=DownloadPDFCallback(action="yes",context = context).pack(),
    )
    kb.adjust(1)
    return kb.as_markup()
