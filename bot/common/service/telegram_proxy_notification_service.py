"""Email-уведомления админу о состоянии Telegram-прокси."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from loguru import logger
from sqlalchemy import select

from bot.common.service.email_service import email_service
from bot.common.service.telegram_proxy_service import fetch_usable_proxies_sync
from bot.db.redis import sync_redis_client

ALL_PROXIES_DOWN_REDIS_KEY = "telegram_proxies:all_down_notified"
MSK = ZoneInfo("Europe/Moscow")


def fetch_admin_notification_email_sync() -> str | None:
    """Email администратора из FAB → «Настройки WebApp»."""
    from bot.common.service.telegram_proxy_service import _get_sync_session
    from bot.db.models import WebAppSetting

    try:
        with _get_sync_session() as session:
            row = session.scalar(
                select(WebAppSetting).order_by(WebAppSetting.id.asc()).limit(1)
            )
            if row is None:
                return None
            email = str(row.admin_notification_email or "").strip()
            return email or None
    except Exception as exc:
        logger.warning("Failed to load admin notification email from FAB settings: {}", exc)
        return None


def _build_all_proxies_down_email() -> tuple[str, str, str]:
    now_msk = datetime.now(MSK).strftime("%d.%m.%Y %H:%M")
    subject = "Все Telegram-прокси недоступны"
    body_text = (
        f"Все настроенные Telegram-прокси перестали работать ({now_msk}, МСК).\n\n"
        "Бот не может отправлять запросы в Telegram API.\n"
        "Проверьте прокси в FAB → «Прокси Telegram» и при необходимости обновите URL или срок действия."
    )
    body_html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <h2 style="color: #dc3545;">Все Telegram-прокси недоступны</h2>
        <p>На момент <strong>{now_msk} (МСК)</strong> ни один прокси не пригоден к использованию.</p>
        <p>Бот не может отправлять запросы в Telegram API.</p>
        <p>Проверьте прокси в FAB → «Прокси Telegram»: URL, активность и срок действия.</p>
    </body>
    </html>
    """
    return subject, body_text, body_html


def sync_telegram_proxy_availability_notification() -> None:
    """
    Если прокси снова доступны — сбрасывает флаг уведомления.
    Если все прокси недоступны — один раз отправляет email админу.
    """
    usable = fetch_usable_proxies_sync()
    if usable:
        if sync_redis_client.get(ALL_PROXIES_DOWN_REDIS_KEY):
            sync_redis_client.delete(ALL_PROXIES_DOWN_REDIS_KEY)
            logger.info("Telegram proxies recovered, all-down notification flag cleared")
        return

    if sync_redis_client.get(ALL_PROXIES_DOWN_REDIS_KEY):
        return

    admin_email = fetch_admin_notification_email_sync()
    if not admin_email:
        logger.warning(
            "All Telegram proxies are down, but admin notification email is not set in FAB"
        )
        return

    if not email_service.is_configured():
        logger.warning(
            "All Telegram proxies are down, but SMTP is not configured (set SMTP_* in .env)"
        )
        return

    subject, body_text, body_html = _build_all_proxies_down_email()
    if email_service.send_email(
        admin_email,
        subject,
        body_html,
        body_text=body_text,
    ):
        sync_redis_client.set(ALL_PROXIES_DOWN_REDIS_KEY, "1")
        logger.error(
            "All Telegram proxies are down — notification email sent to {}",
            admin_email,
        )
