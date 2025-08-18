from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
from loguru import logger
from bot.config import bot

async def notify_user(user_id: int, text: str, keyboard=None):
    """
    Отправляет сообщение пользователю, если это возможно.
    Обрабатывает ситуации, когда пользователь заблокировал бота или удалил чат.
    """
    try:
        await bot.send_message(user_id, text, reply_markup=keyboard)
    except TelegramForbiddenError:
        logger.warning(f"Пользователь {user_id} заблокировал бота. Сообщение не доставлено.")
    except TelegramBadRequest as e:
        logger.warning(f"Ошибка отправки сообщения пользователю {user_id}: {e}")
    except Exception as e:
        logger.error(f"Неожиданная ошибка при отправке сообщения пользователю {user_id}: {e}")