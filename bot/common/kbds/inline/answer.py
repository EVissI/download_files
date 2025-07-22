from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


class AnswerCallback(CallbackData, prefix="reply_user"):
    user_id: int
    analysis_id: str


def get_admin_answer_kb(user_id: int, analysis_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="Ответить",
        callback_data=AnswerCallback(user_id=user_id, analysis_id=analysis_id).pack(),
    )
    return builder.as_markup()


class ResultCallback(CallbackData, prefix="result_action"):
    action: str


def get_result_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="Отправить пользователю",
        callback_data=ResultCallback(action="send_to_user").pack(),
    )
    builder.button(
        text="Попробовать снова",
        callback_data=ResultCallback(action="try_again").pack(),
    )
    return builder.as_markup()


def get_player_keyboard(player1: str, player2: str, analysis_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=player1, callback_data=f"player:{player1}:{analysis_id}")
    builder.button(text=player2, callback_data=f"player:{player2}:{analysis_id}")
    return builder.as_markup()