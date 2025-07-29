from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup

from bot.db.models import AnalizePayment


class PlayerNameCallback(CallbackData, prefix="player_name_page"):
    player_name: str = ""
    page: int = 0
    action: str = "select"  # select, prev, next, back

def get_player_names_kb(
    player_names: list[str],
    page: int = 0,
    items_per_page: int = 5,
    lang: str = "ru"
) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    start_idx = page * items_per_page
    end_idx = start_idx + items_per_page
    current_names = player_names[start_idx:end_idx]

    for name in current_names:
        kb.button(
            text=name,
            callback_data=PlayerNameCallback(player_name=name, page=page, action="select").pack()
        )

    nav_buttons = []
    if page > 0:
        nav_buttons.append((
            "←",
            PlayerNameCallback(player_name="", page=page-1, action="prev").pack()
        ))
    if end_idx < len(player_names):
        nav_buttons.append((
            "→",
            PlayerNameCallback(player_name="", page=page+1, action="next").pack()
        ))

    for text, callback in nav_buttons:
        kb.button(text=text, callback_data=callback)

    rows = [1] * len(current_names)
    if nav_buttons:
        rows.append(len(nav_buttons))

    kb.adjust(*rows)
    return kb.as_markup()


class AnalizePaymentCallback(CallbackData, prefix="analize_payment_page"):
    payment_id: int = 0
    page: int = 0
    action: str = "select"  # select, prev, next, back
    context: str

def get_analize_payments_kb(
    payments: list[AnalizePayment],
    context:str,
    page: int = 0,
    items_per_page: int = 5,
    lang: str = "ru"
) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    start_idx = page * items_per_page
    end_idx = start_idx + items_per_page
    current_payments = payments[start_idx:end_idx]

    for payment in current_payments:
        display_text = f"{payment.name} за {payment.price} RUB"
        kb.button(
            text=display_text,
            callback_data=AnalizePaymentCallback(payment_id=payment.id, page=page, action="select",context = context).pack()
        )

    nav_buttons = []
    if page > 0:
        nav_buttons.append((
            "←",
            AnalizePaymentCallback(payment_id=0, page=page-1, action="prev", context = context).pack()
        ))
    if end_idx < len(payments):
        nav_buttons.append((
            "→",
            AnalizePaymentCallback(payment_id=0, page=page+1, action="next", context = context).pack()
        ))

    for text, callback in nav_buttons:
        kb.button(text=text, callback_data=callback)

    rows = [1] * len(current_payments)
    if nav_buttons:
        rows.append(len(nav_buttons))

    kb.adjust(*rows)
    return kb.as_markup()