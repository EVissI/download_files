from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder


class PromoKeyboard:
    promo_text_kb = {
        'create_promo':'Cоздать',
        'view_promo':'Просмотр',
        'deactivate_promo':'Деактивировать',
        'back':'Назад',
    }

    @staticmethod
    def get_kb_text() -> dict:
        return PromoKeyboard.promo_text_kb
    
    @staticmethod
    def build() -> ReplyKeyboardMarkup:
        kb = ReplyKeyboardBuilder()
        for text in PromoKeyboard.get_kb_text().values():
            kb.add(
                KeyboardButton(text=text)
            )
        kb.adjust(3,1)
        return kb.as_markup(resize_keyboard=True)