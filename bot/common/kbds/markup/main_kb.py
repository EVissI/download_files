
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
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
            'cards_cabinet': i18n.keyboard.user.reply.cards_cabinet(),
            'match_analysis_cabinet': i18n.keyboard.user.reply.match_analysis_cabinet(),
            'pip_count_cabinet': i18n.keyboard.user.reply.pip_count_cabinet(),
            'profile': i18n.keyboard.user.reply.profile(),
        }
    
    @staticmethod
    def get_admin_kb_text(i18n:TranslatorRunner) -> dict:
        return {
            'admin_panel': i18n.keyboard.admin.reply.admin_panel(),
            'fab_admin': i18n.keyboard.admin.reply.fab_admin(),
        }
    
    @staticmethod
    def build(user_role:str, i18n:TranslatorRunner) -> ReplyKeyboardMarkup:
        kb = ReplyKeyboardBuilder()
        user_texts = list(MainKeyboard.get_user_keyboard(i18n).values())
        for text in user_texts:
            kb.add(KeyboardButton(text=text))

        is_admin = user_role == User.Role.ADMIN.value
        if is_admin:
            for text in MainKeyboard.get_admin_kb_text(i18n).values():
                kb.add(KeyboardButton(text=text))

        # Все пользовательские кнопки парами:
        # «Карточки | Анализ матча», затем «Подсчёт пипсов | Профиль»;
        # у админа ниже — «Админпанель | Веб-админка».
        # Важно: web_app на ReplyKeyboard не передаёт initData (ограничение Telegram),
        # поэтому кабинет/веб-админка — текстовые кнопки → дальше inline WebApp.
        row_sizes: list[int] = [2, 2, 2, 2]
        if is_admin:
            row_sizes.append(2)
        kb.adjust(*row_sizes)
        return kb.as_markup(resize_keyboard=True)
