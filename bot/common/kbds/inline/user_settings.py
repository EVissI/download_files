from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup

class UserSettingsCallback(CallbackData, prefix="user_settings"):
    action: str  # "list_users", "export_excel", "back"
    user_id: int 

def get_user_settings_kb(user_id:int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text='Поставить никнейм',
        callback_data=UserSettingsCallback(action="set_username", user_id=user_id).pack(),
    )
    kb.button(
        text='Отправить уведомление',
        callback_data=UserSettingsCallback(action="notify_user", user_id=user_id).pack(),
    )
    kb.button(
        text='Выгрузка игр в Excel',
        callback_data=UserSettingsCallback(action="export_excel", user_id=user_id).pack(),
    )
    kb.button(
        text='Назад',
        callback_data=UserSettingsCallback(action="back", user_id=user_id).pack(),
    )
    kb.adjust(1)
    return kb.as_markup()