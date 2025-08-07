from datetime import datetime, timezone
from typing import List
from loguru import logger
from bot.common.utils.notify import notify_user
from bot.db.dao import UserPromocodeDAO, UserAnalizePaymentDAO, UserDAO
from bot.db.database import async_session_maker
from bot.config import translator_hub
from sqlalchemy.ext.asyncio import AsyncSession


async def expire_analiz_balances(session: AsyncSession = None) -> None:
    """
    Проверяет и деактивирует истекшие записи UserPromocode и UserAnalizePayment,
    отправляя уведомления пользователям при деактивации.
    """
    try:
        # Если сессия не передана, создаем новую
        if session is None:
            async with async_session_maker() as session:
                await _expire_analiz_balances_with_session(session)
        else:
            await _expire_analiz_balances_with_session(session)
    except Exception as e:
        logger.error(f"Ошибка в expire_analiz_balances: {e}")
        raise


async def _expire_analiz_balances_with_session(session: AsyncSession) -> None:
    """
    Внутренняя функция для обработки истечения балансов с использованием предоставленной сессии.
    """
    try:
        user_promo_dao = UserPromocodeDAO(session)
        user_payment_dao = UserAnalizePaymentDAO(session)
        user_dao = UserDAO(session)

        # Получить всех пользователей с активными записями UserPromocode или UserAnalizePayment
        promos = await user_promo_dao.get_active_with_promocode()
        payments = await user_payment_dao.get_active_with_payment()

        # Собираем уникальные ID пользователей
        user_ids = set()
        for up in promos:
            user_ids.add(up.user_id)
        for up in payments:
            user_ids.add(up.user_id)

        logger.info(f"Найдено {len(user_ids)} пользователей с активными записями для проверки")

        # Проверяем истекшие записи для каждого пользователя
        for user_id in user_ids:
            # Проверяем и деактивируем истекшие записи
            any_expired = await user_dao.check_expired_records(user_id)
            if any_expired:
                # Загружаем пользователя для отправки уведомления
                user = await user_dao.find_one_or_none_by_id(user_id)
                if user:
                    lang = user.lang_code or "ru"
                    i18n = translator_hub.get_translator_by_locale(lang)
                    # Получаем текущий баланс для сообщения
                    total_balance = await user_dao.get_total_analiz_balance(user_id)
                    balance_text = (
                        "неограниченный"
                        if total_balance is None
                        else str(total_balance)
                    )
                    text = i18n.user.profile.expire_notice(
                        amount=balance_text,
                        source="истекшим записям (промокоды или платежи)"
                    )
                    await notify_user(user_id, text)
                    logger.info(f"Уведомление отправлено пользователю {user_id}")

        await session.commit()
        logger.info("Проверка истекших записей завершена")
    except Exception as e:
        logger.error(f"Ошибка в _expire_analiz_balances_with_session: {e}")
        await session.rollback()
        raise