from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


PRO_ORDER_CALLBACK_PREFIX = "pro_order:"


def get_pro_analysis_order_kb(request_id: str) -> InlineKeyboardMarkup:
    """Кнопка для пользователя: заказать анализ у профи."""
    kb = InlineKeyboardBuilder()
    kb.button(
        text="Заказать анализ у профи",
        callback_data=f"{PRO_ORDER_CALLBACK_PREFIX}{request_id}",
    )
    kb.adjust(1)
    return kb.as_markup()


def get_pro_analysis_admin_reply_kb(user_id: int) -> InlineKeyboardMarkup:
    """Кнопка «Ответить» для админа (FSM в support_reply_router)."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Ответить",
                    callback_data=f"admin_reply:{user_id}",
                )
            ]
        ]
    )
