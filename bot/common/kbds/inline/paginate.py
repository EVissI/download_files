from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup

from bot.db.models import AnalizePayment
from typing import List, Callable, Any, Set


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


class PaginatedCallback(CallbackData, prefix="paginated"):
    item_id: int = 0
    page: int = 0
    action: str = "select"  # select, prev, next, back
    context: str

def get_paginated_keyboard(
    items: List[Any],
    context: str,
    get_display_text: Callable[[Any], str],
    get_item_id: Callable[[Any], int],
    page: int = 0,
    items_per_page: int = 5,
    with_back_butn:bool = False
) -> InlineKeyboardMarkup:
    """
    Создает инлайн-клавиатуру с пагинацией для списка объектов.
    
    Args:
        items: Список объектов для отображения.
        context: Контекст для коллбэка (например, для идентификации клавиатуры).
        get_display_text: Функция, возвращающая отображаемый текст для объекта.
        get_item_id: Функция, возвращающая ID объекта для коллбэка.
        page: Текущая страница (по умолчанию 0).
        items_per_page: Количество элементов на странице (по умолчанию 5).
        lang: Язык для локализации (по умолчанию 'ru').
    
    Returns:
        InlineKeyboardMarkup: Готовая клавиатура с кнопками и навигацией.
    """
    kb = InlineKeyboardBuilder()
    start_idx = page * items_per_page
    end_idx = start_idx + items_per_page
    current_items = items[start_idx:end_idx]

    # Добавление кнопок для элементов
    for item in current_items:
        display_text = get_display_text(item)
        kb.button(
            text=display_text,
            callback_data=PaginatedCallback(
                item_id=get_item_id(item),
                page=page,
                action="select",
                context=context
            ).pack()
        )

    # Навигационные кнопки
    nav_buttons = []
    if page > 0:
        nav_buttons.append((
            "←",
            PaginatedCallback(item_id=0, page=page-1, action="prev", context=context).pack()
        ))
    if end_idx < len(items):
        nav_buttons.append((
            "→",
            PaginatedCallback(item_id=0, page=page+1, action="next", context=context).pack()
        ))

    for text, callback in nav_buttons:
        kb.button(text=text, callback_data=callback)
    rows = [1] * len(current_items)
    if nav_buttons:
        rows.append(len(nav_buttons))

    if with_back_butn:
        back_cb = PaginatedCallback(item_id=0, page=page, action="back", context=context).pack()
        kb.button(text="Назад", callback_data=back_cb)
        rows.append(1)

    kb.adjust(*rows)
    return kb.as_markup()

class PaginatedCheckboxCallback(CallbackData, prefix="paginated_chk"):
    item_id: int = 0
    page: int = 0
    action: str = "toggle"  # toggle, prev, next, done
    context: str = ""

def get_paginated_checkbox_keyboard(
    items: List[Any],
    context: str,
    get_display_text: Callable[[Any], str],
    get_item_id: Callable[[Any], int],
    selected_ids: Set[int] | List[int] | None = None,
    page: int = 0,
    items_per_page: int = 5,
    with_back_butn:bool = False
) -> InlineKeyboardMarkup:
    """
    Создаёт клавиатуру с чекбоксами. Состояние выбранных id хранится в FSM state,
    а в callback_data передаётся только item_id/page/action/context (без списка selected).
    """
    kb = InlineKeyboardBuilder()
    start_idx = page * items_per_page
    end_idx = start_idx + items_per_page
    current_items = items[start_idx:end_idx]

    sel_set = set(selected_ids or [])

    for item in current_items:
        item_id = get_item_id(item)
        display = get_display_text(item)
        prefix = "+ " if item_id in sel_set else ""
        cb = PaginatedCheckboxCallback(
            item_id=item_id,
            page=page,
            action="toggle",
            context=context,
        ).pack()
        kb.button(text=f"{prefix}{display}", callback_data=cb)

    # Навигация
    nav_buttons = []
    if page > 0:
        nav_buttons.append((
            "←",
            PaginatedCheckboxCallback(item_id=0, page=page-1, action="prev", context=context).pack()
        ))
    if end_idx < len(items):
        nav_buttons.append((
            "→",
            PaginatedCheckboxCallback(item_id=0, page=page+1, action="next", context=context).pack()
        ))

    for text, callback in nav_buttons:
        kb.button(text=text, callback_data=callback)

    # Кнопка "Далее"
    done_cb = PaginatedCheckboxCallback(item_id=0, page=page, action="done", context=context).pack()
    kb.button(text="Далее", callback_data=done_cb)

    rows = [1] * len(current_items)
    if nav_buttons:
        rows.append(len(nav_buttons))
    if with_back_butn:
        back_cb = PaginatedCheckboxCallback(item_id=0, page=page, action="back", context=context).pack()
        kb.button(text="Назад", callback_data=back_cb)
        rows.append(1)
    rows.append(1)
    kb.adjust(*rows)
    return kb.as_markup()
