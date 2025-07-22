from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup

class GeneralUnloadingCallback(CallbackData, prefix="general_unloading"):
    action: str
    type: str = "ex"

def get_general_unloading_kb(type:str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="Общая выгрузка",
        callback_data=GeneralUnloadingCallback(action="general_unloading",type=type).pack()
    )
    builder.button(
        text="Выгрузка по дате",
        callback_data=GeneralUnloadingCallback(action="uploading_by_date",type=type).pack()
    )
    builder.button(
        text="Отмена",
        callback_data=GeneralUnloadingCallback(action="back",type=type).pack()
    )
    builder.adjust(1)
    return builder.as_markup()