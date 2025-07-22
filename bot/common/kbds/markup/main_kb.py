from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder

from bot.db.models import User


class MainKeyboard:
    user_text_kb = {
        'auto_analyze': 'Auto analysis',
        'analize':'Advanced analysis',
        'my_stat':'My statistics',
    }
    admin_text_kb = {
        'excel':'Выгрузки Excel'
    }
    @staticmethod
    def get_user_kb_text() -> dict:
        return MainKeyboard.user_text_kb
    
    @staticmethod
    def get_admin_kb_text() -> dict:
        return MainKeyboard.admin_text_kb
    
    @staticmethod
    def build(user_role:str) -> ReplyKeyboardMarkup:
        kb = ReplyKeyboardBuilder()
        for text in MainKeyboard.get_user_kb_text().values():
            kb.add(
                KeyboardButton(text=text)
            )
        if user_role == User.Role.ADMIN.value:
            for text in MainKeyboard.get_admin_kb_text().values():
                kb.add(
                    KeyboardButton(text=text)
                )
        kb.adjust(2)
        return kb.as_markup(resize_keyboard=True)