from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup


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

    kb.adjust(1)
    return kb.as_markup()