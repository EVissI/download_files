
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder

from bot.db.models import User

from fluentogram import TranslatorRunner
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from locales.stub import TranslatorRunner

class MainKeyboard:
    @staticmethod
    def get_user_keyboard(i18n:TranslatorRunner) -> dict:
        return {
            'autoanalize': i18n.keyboard.user.reply.autoanalyze(),
            'short_board': i18n.keyboard.user.reply.short_board_view(),
            'hint_viewer': i18n.keyboard.user.reply.hint_viewer(),
            'pokaz': i18n.keyboard.user.reply.pokaz(),
            'profile': i18n.keyboard.user.reply.profile(),
        }
    
    @staticmethod
    def get_admin_kb_text(i18n:TranslatorRunner) -> dict:
        return {
            'admin_panel': i18n.keyboard.admin.reply.admin_panel(),
        }
    
    @staticmethod
    def build(user_role:str, i18n:TranslatorRunner) -> ReplyKeyboardMarkup:
        kb = ReplyKeyboardBuilder()
        for text in MainKeyboard.get_user_keyboard(i18n).values():
            kb.add(KeyboardButton(text=text))
        if user_role == User.Role.ADMIN.value:
            for text in MainKeyboard.get_admin_kb_text(i18n).values():
                kb.add(
                    KeyboardButton(text=text)
                )
        kb.adjust(2)
        return kb.as_markup(resize_keyboard=True)