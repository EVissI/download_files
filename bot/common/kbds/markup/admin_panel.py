from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from bot.config import settings


class AdminKeyboard:
    admin_text_kb = {
        'excel':'Excel выгрузки',
        # 'promo':'Промокоды',
        # 'payment':'Пакеты',
        'notify':'Рассылка',
        'monitor':'Мониторинг обработчиков',
        'users_setting':'Пользователи',
        'users_group': 'Группы пользователей',
        'message_for_new': 'Сообщение для новых пользователей',
        'back':'Назад',
    }

    @staticmethod
    def get_kb_text() -> dict:
        return AdminKeyboard.admin_text_kb
    
    @staticmethod
    def build() -> ReplyKeyboardMarkup:
        kb = ReplyKeyboardBuilder()
        for key, text in AdminKeyboard.admin_text_kb.items():
            if key == 'back':
                continue
            kb.add(KeyboardButton(text=text))
        kb.add(KeyboardButton(text=AdminKeyboard.admin_text_kb['back']))
        kb.adjust(2, 2, 2, 1, 1, 1)
        return kb.as_markup(resize_keyboard=True)

    @staticmethod
    def get_inline_admin_web(chat_id: int) -> InlineKeyboardMarkup:
        kb = InlineKeyboardBuilder()
        admin_url = f"{settings.MINI_APP_URL}/admin/login"
        kb.button(text="🚀 Войти в Админ-панель", web_app=WebAppInfo(url=admin_url))
        kb.add(KeyboardButton(text='Позиция',web_app=WebAppInfo(url=f'{settings.MINI_APP_URL}/pokaz?chat_id={chat_id}')))
        return kb.as_markup()