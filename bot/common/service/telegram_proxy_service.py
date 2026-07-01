"""Загрузка Telegram-прокси из БД."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Iterable

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from loguru import logger

from bot.common.proxy_utils import mask_proxy_url
from bot.config import settings

if TYPE_CHECKING:
    from bot.db.models import TelegramProxy

_sync_engine = None
_sync_session_maker: sessionmaker[Session] | None = None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _get_sync_session() -> Session:
    global _sync_engine, _sync_session_maker
    if _sync_session_maker is None:
        _sync_engine = create_engine(settings.DB_URL_SYNC, pool_pre_ping=True)
        _sync_session_maker = sessionmaker(bind=_sync_engine)
    return _sync_session_maker()


def _is_proxy_usable(proxy: TelegramProxy, *, now: datetime | None = None) -> bool:
    if not proxy.is_active:
        return False
    if proxy.expires_at is not None:
        check_time = now or _utcnow()
        expires_at = proxy.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= check_time:
            return False
    return bool(str(proxy.url or "").strip())


def _proxy_urls_from_rows(rows: Iterable[TelegramProxy]) -> list[str]:
    now = _utcnow()
    urls: list[str] = []
    for row in rows:
        if not _is_proxy_usable(row, now=now):
            continue
        url = str(row.url).strip()
        if url and url not in urls:
            urls.append(url)
    return urls


def fetch_active_proxy_urls_sync(session: Session | None = None) -> list[str]:
    from bot.db.models import TelegramProxy

    if session is not None:
        rows = (
            session.query(TelegramProxy)
            .filter(TelegramProxy.is_active.is_(True))
            .order_by(TelegramProxy.priority.asc(), TelegramProxy.id.asc())
            .all()
        )
        return _proxy_urls_from_rows(rows)

    with _get_sync_session() as db_session:
        rows = (
            db_session.query(TelegramProxy)
            .filter(TelegramProxy.is_active.is_(True))
            .order_by(TelegramProxy.priority.asc(), TelegramProxy.id.asc())
            .all()
        )
        urls = _proxy_urls_from_rows(rows)
        for row in rows:
            logger.info(
                "telegram_proxies row: id={} name={!r} priority={} active={} usable={} url={}",
                row.id,
                row.name,
                row.priority,
                row.is_active,
                _is_proxy_usable(row),
                mask_proxy_url(str(row.url or "")),
            )
        return urls


async def fetch_proxies_needing_expiry_warning() -> list[TelegramProxy]:
    """Прокси, у которых до истечения ≤2 суток и предупреждение ещё не отправляли."""
    from bot.db.database import async_session_maker
    from bot.db.models import TelegramProxy

    now = _utcnow()
    window_end = now + timedelta(days=2)
    async with async_session_maker() as session:
        result = await session.execute(
            select(TelegramProxy)
            .where(
                TelegramProxy.is_active.is_(True),
                TelegramProxy.expires_at.is_not(None),
                TelegramProxy.expires_at > now,
                TelegramProxy.expires_at <= window_end,
                TelegramProxy.expiry_warning_sent_at.is_(None),
            )
            .order_by(TelegramProxy.expires_at.asc())
        )
        return list(result.scalars().all())


async def mark_expiry_warning_sent(proxy_id: int) -> None:
    from bot.db.database import async_session_maker
    from bot.db.models import TelegramProxy

    async with async_session_maker() as session:
        row = await session.get(TelegramProxy, proxy_id)
        if row is None:
            return
        row.expiry_warning_sent_at = _utcnow()
        await session.commit()


async def send_proxy_test_message(
    *,
    proxy_url: str,
    proxy_name: str,
    chat_ids: Iterable[int],
) -> int:
    """Отправляет тестовое сообщение через указанный прокси. Возвращает число успешных отправок."""
    from aiogram import Bot
    from aiogram.client.default import DefaultBotProperties
    from aiogram.client.session.aiohttp import AiohttpSession
    from aiogram.enums import ParseMode

    url = str(proxy_url or "").strip()
    if not url:
        raise ValueError("URL прокси не задан")

    recipients = [int(chat_id) for chat_id in chat_ids]
    if not recipients:
        raise ValueError("Не заданы получатели (ROOT_ADMIN_IDS)")

    session = AiohttpSession(proxy=url)
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        session=session,
    )
    sent = 0
    try:
        text = (
            f"✅ Тест прокси Telegram «{proxy_name}» прошёл успешно.\n"
            f"URL: {mask_proxy_url(url)}"
        )
        for chat_id in recipients:
            await bot.send_message(chat_id, text)
            sent += 1
    finally:
        await bot.session.close()
    return sent
