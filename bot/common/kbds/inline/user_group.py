from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup

class UserGroupCallback(CallbackData, prefix="user_group"):
    action: str  

def get_user_group_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text='Создать группу',
        callback_data=UserGroupCallback(action="create_group").pack(),
    )
    kb.button(
        text='Удалить группу',
        callback_data=UserGroupCallback(action="delete_group").pack(),
    )
    kb.button(
        text='Добавить пользователей в группу',
        callback_data=UserGroupCallback(action="add_users").pack(),
    )
    kb.button(
        text='Удалить пользователей из группы',
        callback_data=UserGroupCallback(action="delete_users").pack(),
    )
    kb.adjust(1)
    return kb.as_markup()