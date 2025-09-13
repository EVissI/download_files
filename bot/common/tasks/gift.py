from bot.common.func.func import normalize_slashes
from bot.common.kbds.inline.activate_promo import get_activate_promo_without_link_keyboard
from bot.common.utils.notify import notify_user
from bot.config import translator_hub
from bot.db.dao import UserDAO, UserPromocodeDAO
from bot.db.database import async_session_maker
from bot.db.dao import MessageForNewDAO

async def check_and_notify_gift():
    """
    Проверяет, есть ли у пользователя подарок, и отправляет уведомление, если есть.
    """
    async with async_session_maker() as session:
        user_dao = UserDAO(session)
        message_dao = MessageForNewDAO(session)
        user_promocode_dao = UserPromocodeDAO(session)
        users = await user_dao.find_all()
        for user in users:
            user_promocodes = await user_promocode_dao.get_all_by_user(user.id)
            i18n = translator_hub.get_translator_by_locale(user.lang_code or 'en')
            if not user_promocodes:
                record = await message_dao.get_by_lang_code(user.lang_code)
                keyboard = get_activate_promo_without_link_keyboard(i18n)
                await notify_user(user.id, normalize_slashes(record.text), keyboard)
