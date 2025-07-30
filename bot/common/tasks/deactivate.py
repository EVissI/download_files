from datetime import datetime, timedelta, timezone
from bot.common.utils.notify import notify_user
from bot.db.dao import UserPromocodeDAO, UserAnalizePaymentDAO, UserDAO
from bot.db.database import async_session_maker
from bot.config import translator_hub


async def expire_analiz_balances():
    async with async_session_maker() as session:
        user_promo_dao = UserPromocodeDAO(session)
        user_payment_dao = UserAnalizePaymentDAO(session)
        user_dao = UserDAO(session)

        now = datetime.now(timezone.utc)
        need_commit = False

        # --- ПРОМОКОДЫ ---
        promos = await user_promo_dao.get_active_with_promocode()
        for up in promos:
            promo = up.promocode
            if not promo or promo.duration_days is None:
                continue
            expire_date = up.created_at + timedelta(days=promo.duration_days)
            if expire_date < now and up.is_active:
                user = await user_dao._session.get(user_dao.model, up.user_id)
                if user and promo.analiz_count:
                    user.analiz_balance = max((user.analiz_balance or 0) - promo.analiz_count, 0)
                    up.is_active = False
                    need_commit = True
                    lang = user.lang_code or "ru"
                    i18n = translator_hub.get_translator_by_locale(lang)
                    text = i18n.user.profile.expire_notice(
                        amount=promo.analiz_count,
                        source=f"промокоду {promo.code}"
                    )
                    await notify_user(user.id, text)

        # --- ПЛАТЕЖИ ---
        payments = await user_payment_dao.get_active_with_payment()
        for up in payments:
            payment = up.analize_payment
            if not payment or payment.duration_days is None:
                continue
            expire_date = up.created_at + timedelta(days=payment.duration_days)
            if expire_date < now and up.is_active:
                user = await user_dao._session.get(user_dao.model, up.user_id)
                if user and payment.amount:
                    user.analiz_balance = max((user.analiz_balance or 0) - payment.amount, 0)
                    up.is_active = False
                    need_commit = True
                    text = i18n.user.profile.expire_notice(
                        amount=payment.amount,
                        source=f"пакету '{payment.name}'"
                    )
                    await notify_user(user.id, text)

        if need_commit:
            await session.commit()