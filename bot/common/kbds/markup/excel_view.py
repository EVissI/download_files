from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder


class ExcelKeyboard:
    excel_text_kb = {
        'general_unloading_ex':'Общая выгрузка ex',
        'upload_by_user_ex':'Выгрузка по пользователю ex',
        'general_unloading_gnu':'Общая выгрузка gnu',
        'upload_by_user_gnu':'Выгрузка по пользователю gnu',
        'back':'Назад',
    }

    @staticmethod
    def get_kb_text() -> dict:
        return ExcelKeyboard.excel_text_kb
    
    @staticmethod
    def build() -> ReplyKeyboardMarkup:
        kb = ReplyKeyboardBuilder()
        for text in ExcelKeyboard.get_kb_text().values():
            kb.add(
                KeyboardButton(text=text)
            )
        kb.adjust(2)
        return kb.as_markup(resize_keyboard=True)