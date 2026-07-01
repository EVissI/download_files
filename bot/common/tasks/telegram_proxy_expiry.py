"""Уведомления админам об истечении Telegram-прокси."""

from __future__ import annotations

from zoneinfo import ZoneInfo

from loguru import logger

from bot.common.service.telegram_proxy_service import (
    fetch_proxies_needing_expiry_warning,
    mark_expiry_warning_sent,
    mask_proxy_url,
)
from bot.config import admins, bot

MSK = ZoneInfo("Europe/Moscow")


async def notify_telegram_proxy_expiry() -> None:
    proxies = await fetch_proxies_needing_expiry_warning()
    if not proxies:
        return

    for proxy in proxies:
        expires_msk = proxy.expires_at.astimezone(MSK).strftime("%d.%m.%Y %H:%M")
        text = (
            f"⚠️ Прокси Telegram «{proxy.name}» истекает {expires_msk} (МСК).\n"
            f"URL: {mask_proxy_url(proxy.url)}\n"
            f"Обновите или продлите прокси в FAB → «Прокси Telegram»."
        )
        sent_any = False
        for admin_id in admins:
            try:
                await bot.send_message(admin_id, text)
                sent_any = True
            except Exception as exc:
                logger.warning(
                    "Failed to send proxy expiry warning to admin {}: {}",
                    admin_id,
                    exc,
                )
        if sent_any:
            await mark_expiry_warning_sent(proxy.id)
            logger.info("Proxy expiry warning sent for id={} name={}", proxy.id, proxy.name)
