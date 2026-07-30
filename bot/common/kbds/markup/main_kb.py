
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, WebAppInfo
from aiogram.utils.keyboard import ReplyKeyboardBuilder

from bot.config import settings
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
            admin_texts = MainKeyboard.get_admin_kb_text(i18n)
            kb.add(KeyboardButton(text=admin_texts['admin_panel']))
            kb.add(
                KeyboardButton(
                    text=admin_texts['fab_admin'],
                    web_app=WebAppInfo(
                        url=f"{settings.MINI_APP_URL.rstrip('/')}/admin/login"
                    ),
                )
            )

        # Пользовательские кнопки парами; админ-кнопки — каждая на своей строке
        # (веб-админка под «Админпанель»).
        row_sizes: list[int] = [2] * (len(user_texts) // 2)
        if len(user_texts) % 2:
            row_sizes.append(1)
        if is_admin:
            row_sizes.extend([1, 1])
        kb.adjust(*row_sizes)
        return kb.as_markup(resize_keyboard=True)
