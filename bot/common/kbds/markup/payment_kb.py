from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder


class PaymentKeyboard:
    payment_text_kb = {
        'create':'Cоздать пакет',
        'view':'Посмотреть пакеты',
        'delete':'Удалить пакет',
        'view_buyers':'Посмотреть купивших пакеты',
        'back':'Назад',
    }

    @staticmethod
    def get_kb_text() -> dict:
        return PaymentKeyboard.payment_text_kb
    
    @staticmethod
    def build() -> ReplyKeyboardMarkup:
        kb = ReplyKeyboardBuilder()
        for text in PaymentKeyboard.get_kb_text().values():
            kb.add(
                KeyboardButton(text=text)
            )
        kb.adjust(3,1,1)
        return kb.as_markup(resize_keyboard=True)