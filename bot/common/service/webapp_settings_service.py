from loguru import logger
from sqlalchemy import select

from bot.db.database import async_session_maker
from bot.db.models import WebAppSetting


async def get_webapp_fullscreen_enabled(default: bool = True) -> bool:
    """Читает флаг fullscreen из БД (FAB). При ошибках возвращает default."""
    try:
        async with async_session_maker() as session:
            row = await session.scalar(
                select(WebAppSetting)
                .order_by(WebAppSetting.id.asc())
                .limit(1)
            )
            if row is None:
                row = WebAppSetting(webapp_fullscreen_enabled=bool(default))
                session.add(row)
                await session.commit()
                return bool(default)
            return bool(row.webapp_fullscreen_enabled)
    except Exception as e:
        logger.error(f"get_webapp_fullscreen_enabled failed: {e}")
        return bool(default)
