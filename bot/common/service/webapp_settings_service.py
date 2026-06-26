from loguru import logger
from sqlalchemy import select

from bot.db.database import async_session_maker
from bot.db.models import WebAppSetting

DEFAULT_HINT_VIEWER_SCREENSHOT_FONT_SCALE_PERCENT = 100
MIN_HINT_VIEWER_SCREENSHOT_FONT_SCALE_PERCENT = 50
MAX_HINT_VIEWER_SCREENSHOT_FONT_SCALE_PERCENT = 200

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


def clamp_hint_viewer_screenshot_font_scale_percent(
    value: int,
    default: int = DEFAULT_HINT_VIEWER_SCREENSHOT_FONT_SCALE_PERCENT,
) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        n = default
    return max(
        MIN_HINT_VIEWER_SCREENSHOT_FONT_SCALE_PERCENT,
        min(MAX_HINT_VIEWER_SCREENSHOT_FONT_SCALE_PERCENT, n),
    )


async def _get_or_create_webapp_settings_row(session) -> tuple[WebAppSetting, bool]:
    row = await session.scalar(
        select(WebAppSetting).order_by(WebAppSetting.id.asc()).limit(1)
    )
    if row is not None:
        return row, False
    row = WebAppSetting(
        webapp_fullscreen_hints_enabled=True,
        webapp_fullscreen_pokaz_enabled=True,
        webapp_fullscreen_cards_enabled=True,
        webapp_fullscreen_admin_login_enabled=True,
        webapp_fullscreen_player_enabled=True,
        hint_viewer_screenshot_font_scale_percent=DEFAULT_HINT_VIEWER_SCREENSHOT_FONT_SCALE_PERCENT,
        pokaz_screenshot_font_scale_percent=DEFAULT_HINT_VIEWER_SCREENSHOT_FONT_SCALE_PERCENT,
    )
    session.add(row)
    return row, True


async def get_hint_viewer_screenshot_font_scale_percent(
    default: int = DEFAULT_HINT_VIEWER_SCREENSHOT_FONT_SCALE_PERCENT,
) -> int:
    """Глобальный масштаб шрифта hint_viewer при скриншоте (%, 100 = без изменений)."""
    try:
        async with async_session_maker() as session:
            row, created = await _get_or_create_webapp_settings_row(session)
            if created:
                await session.commit()
            return clamp_hint_viewer_screenshot_font_scale_percent(
                row.hint_viewer_screenshot_font_scale_percent,
                default=default,
            )
    except Exception as e:
        logger.error(f"get_hint_viewer_screenshot_font_scale_percent failed: {e}")
        return clamp_hint_viewer_screenshot_font_scale_percent(default, default=default)


async def set_hint_viewer_screenshot_font_scale_percent(value: int) -> int:
    """Сохраняет глобальный масштаб шрифта hint_viewer для скриншотов."""
    clamped = clamp_hint_viewer_screenshot_font_scale_percent(value)
    async with async_session_maker() as session:
        row, created = await _get_or_create_webapp_settings_row(session)
        row.hint_viewer_screenshot_font_scale_percent = clamped
        await session.commit()
    return clamped


async def get_pokaz_screenshot_font_scale_percent(
    default: int = DEFAULT_HINT_VIEWER_SCREENSHOT_FONT_SCALE_PERCENT,
) -> int:
    """Глобальный масштаб шрифта pokaz при скриншоте (%, 100 = без изменений)."""
    try:
        async with async_session_maker() as session:
            row, created = await _get_or_create_webapp_settings_row(session)
            if created:
                await session.commit()
            return clamp_hint_viewer_screenshot_font_scale_percent(
                row.pokaz_screenshot_font_scale_percent,
                default=default,
            )
    except Exception as e:
        logger.error(f"get_pokaz_screenshot_font_scale_percent failed: {e}")
        return clamp_hint_viewer_screenshot_font_scale_percent(default, default=default)


async def set_pokaz_screenshot_font_scale_percent(value: int) -> int:
    """Сохраняет глобальный масштаб шрифта pokaz для скриншотов."""
    clamped = clamp_hint_viewer_screenshot_font_scale_percent(value)
    async with async_session_maker() as session:
        row, _created = await _get_or_create_webapp_settings_row(session)
        row.pokaz_screenshot_font_scale_percent = clamped
        await session.commit()
    return clamped
