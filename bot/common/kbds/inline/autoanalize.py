from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup


class DownloadPDFCallback(CallbackData, prefix="download_pdf"):
    action: str  # "yes" или "no"


def get_download_pdf_kb(i18n) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text=i18n.auto.analyze.download_pdf(),
        callback_data=DownloadPDFCallback(action="yes").pack(),
    )
    kb.button(
        text=i18n.auto.analyze.no_thanks(),
        callback_data=DownloadPDFCallback(action="no").pack(),
    )
    kb.adjust(1)
    return kb.as_markup()
