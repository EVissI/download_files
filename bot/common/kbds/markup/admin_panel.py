from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder


class AdminKeyboard:
    admin_text_kb = {
        'excel':'Excel выгрузки',
        'promo':'Промокоды',
        'payment':'Пакеты услуг',
        'notify':'Рассылка',
        'users_setting':'Пользователи',
        'back':'Назад',
    }

    @staticmethod
    def get_kb_text() -> dict:
        return AdminKeyboard.admin_text_kb
    
    @staticmethod
    def build() -> ReplyKeyboardMarkup:
        kb = ReplyKeyboardBuilder()
        for text in AdminKeyboard.get_kb_text().values():
            kb.add(
                KeyboardButton(text=text)
            )
        kb.adjust(2,2,1,1)
        return kb.as_markup(resize_keyboard=True)