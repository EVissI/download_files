from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup


class DownloadPDFCallback(CallbackData, prefix="download_pdf"):
    action: str  # "yes" или "no"
    context: str 


class SendToHintViewerCallback(CallbackData, prefix="send_to_hints"):
    action: str  # "yes"
    context: str
    file_id: str = ""  # Уникальный идентификатор файла для батчевого анализа


def get_download_pdf_kb(
    i18n, context, include_hint_viewer=False, file_id: str = ""
) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text=i18n.auto.analyze.download_pdf(),
        callback_data=DownloadPDFCallback(action="yes", context=context).pack(),
    )
    if include_hint_viewer:
        kb.button(
            text=i18n.auto.analyze.send_to_hints(),
            callback_data=SendToHintViewerCallback(
                action="yes", context=context, file_id=file_id
            ).pack(),
        )
    kb.adjust(1)
    return kb.as_markup()


def get_analyze_actions_kb(
    i18n,
    context: str,
    *,
    file_id: str = "",
    include_pdf: bool = True,
    include_hints: bool = True,
    pro_request_id: str | None = None,
) -> InlineKeyboardMarkup:
    """PDF, анализ ошибок и заказ эксперта в одной клавиатуре."""
    kb = InlineKeyboardBuilder()
    if include_hints:
        kb.button(
            text=i18n.auto.analyze.send_to_hints(),
            callback_data=SendToHintViewerCallback(
                action="yes", context=context, file_id=file_id
            ).pack(),
        )
    if include_pdf:
        kb.button(
            text=i18n.auto.analyze.download_pdf(),
            callback_data=DownloadPDFCallback(action="yes", context=context).pack(),
        )
    if pro_request_id:
        from bot.common.kbds.inline.pro_analysis import PRO_ORDER_CALLBACK_PREFIX

        kb.button(
            text=i18n.pro.analysis.order_button(),
            callback_data=f"{PRO_ORDER_CALLBACK_PREFIX}{pro_request_id}",
        )
    kb.adjust(1)
    return kb.as_markup()


def get_hint_viewer_kb(i18n, context="solo", file_id: str = "") -> InlineKeyboardMarkup:
    """Создает клавиатуру с кнопкой отправки на анализ ошибок"""
    kb = InlineKeyboardBuilder()
    kb.button(
        text=i18n.auto.analyze.send_to_hints(),
        callback_data=SendToHintViewerCallback(action="yes", context=context, file_id=file_id).pack(),
    )
    kb.adjust(1)
    return kb.as_markup()
