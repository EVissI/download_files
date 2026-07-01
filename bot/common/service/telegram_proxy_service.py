"""Загрузка Telegram-прокси из БД."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Iterable
from urllib.parse import urlparse

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from loguru import logger

from bot.common.proxy_utils import mask_proxy_url, normalize_proxy_url
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
    return normalize_proxy_url(str(proxy.url or "")) is not None


def _proxy_urls_from_rows(rows: Iterable[TelegramProxy]) -> list[str]:
    now = _utcnow()
    urls: list[str] = []
    for row in rows:
        if not _is_proxy_usable(row, now=now):
            continue
        url = normalize_proxy_url(str(row.url or ""))
        if url is None:
            if row.is_active and str(row.url or "").strip():
                logger.warning(
                    "Skip invalid telegram proxy URL: id={} name={!r} raw={!r}",
                    row.id,
                    row.name,
                    str(row.url or ""),
                )
            continue
        if url not in urls:
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
        if urls:
            logger.info(
                "Active telegram proxies loaded (count={}): {}",
                len(urls),
                ", ".join(mask_proxy_url(u) for u in urls),
            )
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


MAX_PROXY_CONNECTION_FAILURES = 10


def _find_proxy_row_by_url(session: Session, proxy_url: str):
    from bot.db.models import TelegramProxy

    normalized = normalize_proxy_url(str(proxy_url or "")) or str(proxy_url or "").strip()
    if not normalized:
        return None

    row = (
        session.query(TelegramProxy)
        .filter(TelegramProxy.url == normalized)
        .order_by(TelegramProxy.id.asc())
        .first()
    )
    if row is not None:
        return row

    active_rows = (
        session.query(TelegramProxy)
        .filter(TelegramProxy.is_active.is_(True))
        .order_by(TelegramProxy.priority.asc(), TelegramProxy.id.asc())
        .all()
    )
    if len(active_rows) == 1:
        return active_rows[0]

    parsed = urlparse(normalized)
    host_port = (parsed.hostname, parsed.port)
    if not parsed.hostname:
        return None

    for candidate in active_rows:
        candidate_parsed = urlparse(str(candidate.url or "").strip())
        if (
            candidate_parsed.hostname == host_port[0]
            and candidate_parsed.port == host_port[1]
        ):
            return candidate

    return None


def record_proxy_connection_success_sync(proxy_url: str) -> None:
    """Сбрасывает счётчик ошибок после успешного запроса через прокси."""
    try:
        with _get_sync_session() as session:
            row = _find_proxy_row_by_url(session, proxy_url)
            if row is None or not row.connection_failure_count:
                return
            row.connection_failure_count = 0
            session.commit()
    except Exception as exc:
        logger.exception(
            "Failed to reset proxy failure counter for {}: {}",
            mask_proxy_url(proxy_url),
            exc,
        )


def record_proxy_connection_failure_sync(proxy_url: str) -> bool:
    """
    Увеличивает счётчик ошибок подключения.
    После MAX_PROXY_CONNECTION_FAILURES помечает прокси неактивным.
    Возвращает True, если прокси только что деактивирован.
    """
    try:
        with _get_sync_session() as session:
            row = _find_proxy_row_by_url(session, proxy_url)
            if row is None:
                logger.warning(
                    "Proxy connection failure for unknown URL: {}",
                    mask_proxy_url(proxy_url),
                )
                return False

            row.connection_failure_count = int(row.connection_failure_count or 0) + 1
            failures = row.connection_failure_count
            deactivated = False

            if failures >= MAX_PROXY_CONNECTION_FAILURES and row.is_active:
                row.is_active = False
                deactivated = True
                logger.error(
                    "Telegram proxy deactivated after {} failures: id={} name={!r} url={}",
                    failures,
                    row.id,
                    row.name,
                    mask_proxy_url(row.url),
                )
            else:
                logger.warning(
                    "Telegram proxy failure {}/{}: id={} name={!r} url={}",
                    failures,
                    MAX_PROXY_CONNECTION_FAILURES,
                    row.id,
                    row.name,
                    mask_proxy_url(row.url),
                )

            session.commit()
            if deactivated:
                from bot.common.telegram_proxy_config import clear_telegram_proxy_cache

                clear_telegram_proxy_cache()
            return deactivated
    except Exception as exc:
        logger.exception(
            "Failed to record proxy connection failure for {}: {}",
            mask_proxy_url(proxy_url),
            exc,
        )
        return False


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
