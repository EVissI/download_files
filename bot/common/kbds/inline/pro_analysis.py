from typing import TYPE_CHECKING

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

if TYPE_CHECKING:
    from locales.stub import TranslatorRunner


PRO_ORDER_CALLBACK_PREFIX = "pro_order:"


def get_pro_analysis_order_kb(
    request_id: str, i18n: "TranslatorRunner"
) -> InlineKeyboardMarkup:
    """Кнопка для пользователя: заказать анализ у эксперта."""
    kb = InlineKeyboardBuilder()
    kb.button(
        text=i18n.pro.analysis.order_button(),
        callback_data=f"{PRO_ORDER_CALLBACK_PREFIX}{request_id}",
    )
    kb.adjust(1)
    return kb.as_markup()


def get_pro_analysis_admin_reply_kb(
    user_id: int, i18n: "TranslatorRunner"
) -> InlineKeyboardMarkup:
    """Кнопка «Ответить» для админа (FSM в support_reply_router)."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=i18n.pro.analysis.admin_reply(),
                    callback_data=f"admin_reply:{user_id}",
                )
            ]
        ]
    )
