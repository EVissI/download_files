from loguru import logger
from sqlalchemy import select

from bot.db.database import async_session_maker
from bot.db.models import WebAppSetting

WEBAPP_FULLSCREEN_FIELD_BY_SERVICE: dict[str, str] = {
    "default": "webapp_fullscreen_hints_enabled",
    "hints": "webapp_fullscreen_hints_enabled",
    "pokaz": "webapp_fullscreen_pokaz_enabled",
    "cards": "webapp_fullscreen_cards_enabled",
    "cards_cabinet": "webapp_fullscreen_cards_enabled",
    "content_card_view": "webapp_fullscreen_cards_enabled",
    "admin_login": "webapp_fullscreen_admin_login_enabled",
    "player": "webapp_fullscreen_player_enabled",
}


async def get_webapp_fullscreen_enabled(
    service: str = "default",
    default: bool = True,
) -> bool:
    """Читает fullscreen-флаг из БД для конкретного сервиса (FAB)."""
    try:
        key = str(service or "default").strip().lower()
        field_name = WEBAPP_FULLSCREEN_FIELD_BY_SERVICE.get(
            key, WEBAPP_FULLSCREEN_FIELD_BY_SERVICE["default"]
        )
        async with async_session_maker() as session:
            row = await session.scalar(
                select(WebAppSetting)
                .order_by(WebAppSetting.id.asc())
                .limit(1)
            )
            if row is None:
                v = bool(default)
                row = WebAppSetting(
                    webapp_fullscreen_hints_enabled=v,
                    webapp_fullscreen_pokaz_enabled=v,
                    webapp_fullscreen_cards_enabled=v,
                    webapp_fullscreen_admin_login_enabled=v,
                    webapp_fullscreen_player_enabled=v,
                )
                session.add(row)
                await session.commit()
                return bool(default)
            return bool(getattr(row, field_name, getattr(row, WEBAPP_FULLSCREEN_FIELD_BY_SERVICE["default"], default)))
    except Exception as e:
        logger.error(f"get_webapp_fullscreen_enabled failed: {e}")
        return bool(default)
