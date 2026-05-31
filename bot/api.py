import mimetypes
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, Request, Response, HTTPException, File, Form, UploadFile, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.wsgi import WSGIMiddleware
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from typing import Any, Optional
import secrets

from pydantic import BaseModel, Field

from bot.routers.hint_viewer_router import hint_viewer_api_router
from bot.routers.short_board import short_board_api_router
from bot.flask_admin.appbuilder_main import create_app
from bot.common.utils.tg_auth import verify_telegram_webapp_data
from bot.common.service.hint_s3_service import HintS3Storage
from bot.common.service.webapp_settings_service import get_webapp_fullscreen_enabled
from bot.config import settings
from bot.config import bot, scheduler, SUPPORT_TG_ID, translator_hub
from bot.common.utils.i18n import get_text_for_locale
from bot.db.redis import redis_client
from bot.common.kbds.inline.activate_promo import get_activate_promo_keyboard
from bot.common.func.pokaz_func import get_hints_for_xgid
from bot.db.database import async_session_maker
from bot.db.dao import (
    ContentCardActivationLinkDAO,
    ContentCardFolderDAO,
    ContentCardFolderLinkDAO,
    UserDAO,
    MessagesTextsDAO,
    ContentCardDAO,
    UserContentCardDAO,
)
from bot.db.models import (
    ContentCard,
    ContentCardFolder,
    ContentCardFolderItem,
    ContentCardFolderLink,
    ContentFrameTemplate,
    LabelPreset,
    ServiceType,
    TextStylePreset,
    User,
    UserContentCard,
    UserContentCardInteractiveStat,
    UserContentCardStatus,
)
from bot.db.schemas import SContentCardCreate, SUserContentCardCreate
from loguru import logger
import traceback
import json
import os
import re
import time
from pathlib import Path
from aiogram.types import (
    BufferedInputFile,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    WebAppInfo,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

BASE_DIR = Path(__file__).parent.parent

CC_MEDIA_MAX_BYTES = 30 * 1024 * 1024
CC_FRAME_TEMPLATE_MAX_JSON_BYTES = 12 * 1024 * 1024


def _safe_content_disposition_filename(name: str | None, fallback: str) -> str:
    raw = (name or fallback or "file").replace("\\", "/").split("/")[-1].strip() or "file"
    forbidden = {'"', "\\"}
    safe = "".join(c if c.isascii() and c not in forbidden else "_" for c in raw)[:200]
    return safe or "download"


static_dir = BASE_DIR / "bot" / "static"
templates_dir = BASE_DIR / "bot" / "templates"


class NoCacheStaticFiles(StaticFiles):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache"
        return response


app = FastAPI(title="Backgammon Hint Viewer API", version="1.0.0")


@app.on_event("startup")
async def start_scheduler_on_api_startup():
    """
    В API-процессе поднимаем scheduler в paused-режиме:
    - FAB может создавать/обновлять jobs в SQLAlchemyJobStore;
    - задачи НЕ исполняются в этом процессе (чтобы не было дублей с ботом).
    Исполнение задач остается в backgammon_bot (bot/init.py).
    """
    if getattr(scheduler, "running", False):
        return
    scheduler.start(paused=True)
    logger.info("APScheduler started on FastAPI startup in paused mode")


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global exception caught: {exc}")
    logger.error(traceback.format_exc())
    return Response(
        content=json.dumps({"detail": str(exc), "traceback": traceback.format_exc()}),
        status_code=500,
        media_type="application/json",
    )


# CORS middleware for web app integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def admin_security_middleware(request: Request, call_next):
    if request.url.path.startswith("/admin"):
        # Allow login and verify bypass
        if request.url.path in ["/admin/login", "/admin/verify"]:
            return await call_next(request)

        session_token = request.cookies.get("admin_session")
        if not session_token:
            return Response("Unauthorized", status_code=401)

        admin_id = await redis_client.get(f"admin_session:{session_token}")
        if not admin_id:
            return Response("Unauthorized", status_code=401)

    return await call_next(request)


app.mount("/static", NoCacheStaticFiles(directory=str(static_dir)), name="static")
templates = Jinja2Templates(directory=str(templates_dir))

# Include routers
app.include_router(hint_viewer_api_router, prefix="")
app.include_router(short_board_api_router, prefix="")


def _get_pokaz_translations(lang: str) -> dict:
    """Собирает переводы для страницы pokaz из Fluent."""
    t = lambda k, fbk="": get_text_for_locale(translator_hub, lang, k, fbk)
    return {
        "title": t("pokaz-page-title", "Position Editor"),
        "hide_pips": t("pokaz-page-hide-pips", "Hide pips"),
        "hide_point_dropdowns": t(
            "pokaz-page-hide-point-dropdowns", "Hide point dropdowns"
        ),
        "lower_player": t("pokaz-page-lower-player", "Lower player:"),
        "toggle_lower_player": t(
            "pokaz-page-toggle-lower-player", "Toggle lower player"
        ),
        "place_checkers": t("pokaz-page-place-checkers", "Place checkers"),
        "delete_checkers": t("pokaz-page-delete-checkers", "Remove checkers"),
        "moneygame": t("pokaz-page-moneygame", "Moneygame"),
        "match": t("pokaz-page-match", "Match"),
        "checkers": t("pokaz-page-checkers", "Checkers"),
        "white_checkers": t("pokaz-page-white-checkers", "White checkers"),
        "black_checkers": t("pokaz-page-black-checkers", "Black checkers"),
        "on_bar": t("pokaz-page-on-bar", "On bar"),
        "jacobi_beaver_max": t(
            "pokaz-page-jacobi-beaver-max", "Jacoby Beaver Max cube"
        ),
        "yes": t("pokaz-page-yes", "Yes"),
        "no": t("pokaz-page-no", "No"),
        "game_type": t("pokaz-page-game-type", "Game type"),
        "match_headers_lower": t("pokaz-page-match-headers-lower", "Lower pts"),
        "match_headers_upper": t("pokaz-page-match-headers-upper", "Upper pts"),
        "match_headers_length": t("pokaz-page-match-headers-length", "Match len"),
        "match_headers_max_cube": t("pokaz-page-match-headers-max-cube", "Max cube"),
        "cube_shown": t("pokaz-page-cube-shown", "Cube shown?"),
        "cube": t("pokaz-page-cube", "Cube"),
        "whose_cube": t("pokaz-page-whose-cube", "Whose cube?"),
        "crawford": t("pokaz-page-crawford", "Crawford"),
        "whose_turn": t("pokaz-page-whose-turn", "Whose turn?"),
        "dice": t("pokaz-page-dice", "Dice"),
        "history_back": t("pokaz-page-history-back", "History back"),
        "history_forward": t("pokaz-page-history-forward", "History forward"),
        "confirm_move": t("pokaz-page-confirm-move", "Confirm move"),
        "random_dice": t("pokaz-page-random-dice", "Random dice"),
        "analyze_position": t("pokaz-page-analyze-position", "Analyze position"),
        "collapse_table": t("pokaz-page-collapse-table", "Collapse table"),
        "expand_table": t("pokaz-page-expand-table", "Expand table"),
        "toggle_table": t("pokaz-page-toggle-table", "Collapse/expand table"),
        "take_screenshot": t("pokaz-page-take-screenshot", "Take screenshot"),
        "save_screenshot": t(
            "pokaz-page-save-screenshot", "Save screenshot to clipboard"
        ),
        "upload_screenshots": t("pokaz-page-upload-screenshots", "Upload screenshots"),
        "clear": t("pokaz-page-clear", "Clear"),
        "clear_confirm_msg": t(
            "pokaz-page-clear-confirm-msg", "Clear board and start over?"
        ),
        "init": t("pokaz-page-init", "Set up"),
        "init_confirm_msg": t(
            "pokaz-page-init-confirm-msg", "Set up initial position?"
        ),
        "admin_comment_placeholder": t(
            "pokaz-page-admin-comment-placeholder", "Enter message text..."
        ),
        "move": t("pokaz-page-move", "Move"),
        "equity": t("pokaz-page-equity", "Equity"),
        "restore_position": t("pokaz-page-restore-position", "Restore saved position"),
        "next_cube": t("pokaz-page-next-cube", "Next cube"),
        "match_to_tpl": t(
            "pokaz-page-match-to", "Match to __LENGTH__. Score __MAX__-__MIN__"
        ),
        "cancel": t("keyboard-reply-cancel", "Cancel"),
        "confirm": t("pokaz-page-confirm", "Confirmation"),
        "table_header_move": t("pokaz-page-table-header-move", "Move"),
        "table_header_equity": t("pokaz-page-table-header-equity", "Equity"),
        "table_header_action": t("pokaz-page-table-header-action", "Action"),
        "impossible_move": t("pokaz-page-impossible-move", "Impossible move"),
        "unknown_hint_type": t("pokaz-page-unknown-hint-type", "Unknown hint type"),
        "turn_white": t("pokaz-page-turn-white", "White to move"),
        "turn_black": t("pokaz-page-turn-black", "Black to move"),
        "loading_hints": t("pokaz-page-loading-hints", "Loading hints..."),
        "error_insufficient_balance": t(
            "pokaz-page-error-insufficient-balance", "Insufficient balance for hints"
        ),
        "error_no_chat_id": t(
            "pokaz-page-error-no-chat-id", "Missing chat_id. Open via Telegram."
        ),
        "cube_no_double": t("pokaz-page-cube-no-double", "no double"),
        "cube_double": t("pokaz-page-cube-double", "double"),
        "cube_take": t("pokaz-page-cube-take", "take"),
        "cube_pass": t("pokaz-page-cube-pass", "pass"),
        "comment_btn": t("pokaz-page-comment-btn", "Comment"),
        "comment_modal_title": t(
            "pokaz-page-comment-modal-title", "Ask a question about the position"
        ),
        "comment_send": t("pokaz-page-comment-send", "Send"),
        "comment_empty_alert": t(
            "pokaz-page-comment-empty-alert", "Please enter a description of the issue"
        ),
    }


@app.get("/pokaz")
async def get_pokaz(
    request: Request,
    chat_id: str = None,
    xgid: str = None,
    lang: str = None,
):
    """
    Возвращает HTML-страницу редактора доски нардов.
    Параметры: chat_id, xgid, lang (ru|en, по умолчанию ru).
    """
    lang = lang if lang in ("ru", "en") else "ru"
    translations = _get_pokaz_translations(lang)
    cache_timestamp = int(time.time())
    webapp_fullscreen_enabled = await get_webapp_fullscreen_enabled("pokaz")
    response = templates.TemplateResponse(
        "pokaz.html",
        {
            "request": request,
            "chat_id": chat_id,
            "xgid": xgid,
            "lang": lang,
            "i18n": translations,
            "cache_timestamp": cache_timestamp,
            "webapp_fullscreen_enabled": webapp_fullscreen_enabled,
        },
    )
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@app.get("/content-card-view")
async def content_card_view_page(request: Request):
    """Просмотр сохранённой карточки контента (кадры, только переключение)."""
    cache_timestamp = int(time.time())
    webapp_fullscreen_enabled = await get_webapp_fullscreen_enabled("cards")
    response = templates.TemplateResponse(
        "content_card_view.html",
        {
            "request": request,
            "cache_timestamp": cache_timestamp,
            "webapp_fullscreen_enabled": webapp_fullscreen_enabled,
        },
    )
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@app.get("/cards-cabinet")
async def cards_cabinet_page(request: Request):
    """Личный кабинет: сетка карточек пользователя (Telegram WebApp)."""
    cache_timestamp = int(time.time())
    webapp_fullscreen_enabled = await get_webapp_fullscreen_enabled("cards")
    response = templates.TemplateResponse(
        "cards_cabinet.html",
        {
            "request": request,
            "cache_timestamp": cache_timestamp,
            "webapp_fullscreen_enabled": webapp_fullscreen_enabled,
        },
    )
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@app.get("/pokaz/hints")
async def get_pokaz_hints(xgid: str, chat_id: Optional[int] = None):
    """
    Возвращает подсказки для заданной позиции XGID.
    Проверяет баланс пользователя и списывает при успешной обработке.
    """
    try:
        logger.info(
            f"Получен запрос /pokaz/hints с параметрами: xgid={xgid}, chat_id={chat_id}"
        )

        # Проверяем наличие chat_id
        if chat_id is None:
            logger.warning("Запрос без chat_id")
            raise HTTPException(status_code=400, detail="Параметр chat_id обязателен")

        # Создаем сессию БД
        async with async_session_maker() as session:
            user_dao = UserDAO(session)

            # Получаем баланс пользователя для сервиса POKAZ
            balance = await user_dao.get_total_analiz_balance(
                chat_id, ServiceType.POKAZ
            )

            # Проверяем баланс (None означает безлимитный)
            if balance is not None and balance < 1:
                logger.warning(
                    f"Недостаточно баланса для пользователя {chat_id}. Баланс: {balance}"
                )
                raise HTTPException(status_code=402, detail="Недостаточно баланса")

            # Получаем подсказки
            hints = get_hints_for_xgid(xgid)
            logger.info(f"Hints для пользователя {chat_id}: {hints}")

            # Списываем баланс только если массив hints не пустой
            if hints and len(hints) > 0:
                success = await user_dao.decrease_analiz_balance(
                    user_id=chat_id, service_type=ServiceType.POKAZ.name
                )
                if success:
                    await session.commit()
                    logger.info(f"Баланс успешно списан для пользователя {chat_id}")
                else:
                    logger.warning(
                        f"Не удалось списать баланс для пользователя {chat_id}"
                    )
            else:
                logger.info(
                    f"Hints пустой, баланс не списан для пользователя {chat_id}"
                )

            return {"hints": hints}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при обработке запроса pokaz/hints: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Ошибка сервера: {str(e)}")


@app.get("/admin/login", response_class=HTMLResponse)
async def admin_login(request: Request):
    webapp_fullscreen_enabled = await get_webapp_fullscreen_enabled("admin_login")
    return templates.TemplateResponse(
        "admin_login.html",
        {
            "request": request,
            "webapp_fullscreen_enabled": webapp_fullscreen_enabled,
        },
    )


@app.post("/admin/verify")
async def admin_verify(request: Request, response: Response):
    logger.info("Admin verify request received")
    data = await request.json()
    init_data = data.get("initData")
    if not init_data:
        logger.warning("Missing initData in request")
        raise HTTPException(status_code=400, detail="Missing initData")

    user_data = verify_telegram_webapp_data(init_data)
    if not user_data:
        logger.warning("Failed to verify telegram webapp data")
        raise HTTPException(status_code=401, detail="Invalid Telegram data")

    user_id = user_data.get("user", {}).get("id")
    logger.info(f"Verified user_id: {user_id}")
    if user_id not in settings.ROOT_ADMIN_IDS:
        logger.warning(
            f"User {user_id} not in ROOT_ADMIN_IDS: {settings.ROOT_ADMIN_IDS}"
        )
        raise HTTPException(status_code=403, detail="Not an admin")

    # Create session
    session_token = secrets.token_urlsafe(32)
    # Store session in redis
    logger.info(f"Creating session for user {user_id}")
    await redis_client.set(
        f"admin_session:{session_token}", str(user_id), expire=86400
    )  # 24h

    logger.info(f"Setting session cookie for user {user_id}")
    response.set_cookie(
        key="admin_session",
        value=session_token,
        httponly=True,
        samesite="lax",
        max_age=86400,
    )
    return {"status": "ok"}


@app.post("/api/send_to_admin")
async def send_to_admin(request: Request):
    """
    Принимает скриншот и комментарий, отправляет в админку с рейлимитом.
    """
    try:
        form_data = await request.form()
        photo = form_data.get("photo")
        text = form_data.get("text", "Без описания")
        chat_id = request.query_params.get("chat_id") or form_data.get("chat_id")

        if not chat_id:
            logger.warning("Admin comment request received without chat_id")
            raise HTTPException(status_code=400, detail="No chat_id provided")

        if not photo:
            logger.warning("Admin comment request received without photo")
            raise HTTPException(status_code=400, detail="No photo provided")
        # Рейлимит: 5 запросов за 10 минут (600 секунд)
        rate_limit_key = f"rate_limit:admin_comment:{chat_id}"
        current_requests = await redis_client.get(rate_limit_key)
        if current_requests and int(current_requests) >= 5:
            ttl = await redis_client.ttl(rate_limit_key)
            minutes = ttl // 60
            seconds = ttl % 60
            raise HTTPException(
                status_code=429,
                detail={
                    "message": "Слишком много запросов",
                    "retry_after": ttl,
                    "wait_text": (
                        f"{minutes} мин {seconds} сек"
                        if minutes > 0
                        else f"{seconds} сек"
                    ),
                },
            )
        # Проверка баланса по ServiceType.COMMENTS
        chat_id_int = int(chat_id)
        support_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Ответить",
                        callback_data=f"admin_reply:{chat_id}",
                    )
                ]
            ]
        )
        async with async_session_maker() as session:
            user_dao = UserDAO(session)
            balance = await user_dao.get_total_analiz_balance(
                chat_id_int, ServiceType.COMMENTS
            )
            if balance is not None and balance < 1:
                logger.warning(
                    f"Недостаточно баланса COMMENTS для пользователя {chat_id}. Баланс: {balance}"
                )
                # Уведомляем саппорт о попытке отправки без баланса
                await bot.send_message(
                    chat_id=SUPPORT_TG_ID,
                    text=f"⚠️ Пользователь попытался отправить сообщение, но у него не хватило баланса.\nUser ID: {chat_id}",
                    reply_markup=support_keyboard,
                )
                # Получаем язык юзера и отправляем сообщение с клавиатурой активации промо
                user = await user_dao.find_one_or_none_by_id(chat_id_int)
                lang_code = (user.lang_code or "en") if user else "en"
                message_dao = MessagesTextsDAO(session)
                msg_text = await message_dao.get_text(
                    "comments_not_enough_balance", lang_code
                )
                if msg_text:
                    i18n = translator_hub.get_translator_by_locale(lang_code)
                    await bot.send_message(
                        chat_id=chat_id_int,
                        text=msg_text,
                        reply_markup=get_activate_promo_keyboard(i18n),
                    )
                raise HTTPException(
                    status_code=402,
                    detail="Недостаточно баланса для отправки комментария",
                )

            # Читаем файл и отправляем в саппорт
            photo_bytes = await photo.read()
            photo_file = BufferedInputFile(
                photo_bytes, filename="admin_comment_screenshot.png"
            )
            await bot.send_photo(
                chat_id=SUPPORT_TG_ID,
                photo=photo_file,
                caption=f"❓ Вопрос от пользователя\nUser ID: {chat_id}\n\n{text}",
                reply_markup=support_keyboard,
            )

            # Списываем баланс COMMENTS после успешной отправки
            await user_dao.decrease_analiz_balance(
                user_id=chat_id_int,
                service_type=ServiceType.COMMENTS.name,
            )
            await session.commit()

        # Обновляем счетчик в Redis
        if not current_requests:
            await redis_client.set(rate_limit_key, 1, expire=600)
        else:
            await redis_client.incr(rate_limit_key)

        logger.info(f"Admin comment sent to {SUPPORT_TG_ID} from {chat_id}")
        return {"status": "success"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending admin comment: {e}")
        raise HTTPException(status_code=500, detail="Error sending admin comment")


def _is_public_content_card_media_key(key: str) -> bool:
    """
    Допустимый ключ для публичного чтения:
    - content_cards/media/{user_id}/{filename} (медиа карточек),
    - content_cards/media/cabinet_gallery/{filename} (общая галерея кабинета).
    """
    parts = key.split("/")
    if len(parts) != 4:
        return False
    if parts[0] != "content_cards" or parts[1] != "media":
        return False
    name = parts[3]
    if not name or len(name) > 220 or ".." in name:
        return False
    if not all(c.isalnum() or c in "._-" for c in name):
        return False
    mid = parts[2]
    if mid == HintS3Storage.CABINET_GALLERY_FOLDER:
        return True
    if mid.isdigit():
        return True
    return False


def _is_cabinet_gallery_s3_key(key: str) -> bool:
    return HintS3Storage.is_cabinet_gallery_media_key(key)


def _guess_content_upload_extension(filename: str | None, content_type: str | None) -> str:
    if filename and "." in filename:
        ext = filename.rsplit(".", 1)[-1].lower()
        if ext.isalnum() and len(ext) <= 8:
            return f".{ext}"
    ct = (content_type or "").split(";")[0].strip().lower()
    if ct:
        ext = mimetypes.guess_extension(ct)
        if ext:
            return ".jpg" if ext == ".jpe" else ext
    return ".bin"


def _require_content_card_admin(user_id: int) -> None:
    """Карточки контента и медиа к ним — только для ROOT_ADMIN_IDS."""
    if user_id not in settings.ROOT_ADMIN_IDS:
        raise HTTPException(
            status_code=403,
            detail="Загрузка карточек доступна только администраторам",
        )


def _build_empty_content_card_frames() -> dict[str, Any]:
    """Один пустой кадр — как buildEmptyContentCardFramePayload в редакторе."""
    frame_id = f"cc_0_{int(datetime.now(timezone.utc).timestamp() * 1000)}_{secrets.token_hex(4)}"
    saved_at = datetime.now(timezone.utc).isoformat()
    payload: dict[str, Any] = {
        "version": 1,
        "frameId": frame_id,
        "saveSlotIndex": 0,
        "savedAt": saved_at,
        "board": None,
        "cardData": None,
        "editor": {
            "boardCanvasToggle": True,
            "canvasBackground": "#ffffff",
            "showBoardMatchBanner": False,
        },
        "elements": [],
    }
    return {
        "version": 1,
        "frames": [
            {
                "frameId": frame_id,
                "saveSlotIndex": 0,
                "order": 0,
                "payload": payload,
            }
        ],
    }


def _normalize_content_card_labels(raw: list[str] | None) -> list[str] | None:
    if not raw:
        return None
    seen: set[str] = set()
    out: list[str] = []
    for item in raw[:200]:
        t = str(item).strip()[:255]
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return out or None


def _board_xgid_from_board_snapshot(board: Any) -> str | None:
    """Строка позиции из объекта доски сохранённого кадра (поле xgid как в hint_viewer)."""
    if board is None or not isinstance(board, dict):
        return None
    if board.get("error") == "no_game_data":
        return None
    raw = board.get("xgid")
    if isinstance(raw, str):
        s = raw.strip()
        if s:
            return s[:8000]
    return None


def _extract_board_xgid_from_frames(frames: dict[str, Any] | None) -> str | None:
    """
    Если в JSON карточки есть доска со строкой позиции — сохраняем её в колонке board_xgid.
    Смотрим sharedContext, затем по порядку payload каждого кадра.
    """
    if not frames or not isinstance(frames, dict):
        return None
    sc = frames.get("sharedContext")
    if isinstance(sc, dict):
        got = _board_xgid_from_board_snapshot(sc.get("board"))
        if got:
            return got
    inner = frames.get("frames")
    if not isinstance(inner, list):
        return None
    for item in inner:
        if not isinstance(item, dict):
            continue
        payload = item.get("payload")
        if isinstance(payload, dict):
            got = _board_xgid_from_board_snapshot(payload.get("board"))
            if got:
                return got
    return None


def _content_card_view_webapp_markup(view_url: str) -> InlineKeyboardMarkup:
    """Кнопка Web App — иначе при открытии ссылки из чата init_data в Telegram не передаётся."""
    kb = InlineKeyboardBuilder()
    kb.button(text="Открыть карточку", web_app=WebAppInfo(url=view_url))
    kb.adjust(1)
    return kb.as_markup()


def _cards_cabinet_webapp_markup(view_url: str) -> InlineKeyboardMarkup:
    """Кнопка открытия личного кабинета карточек в Telegram Web App."""
    kb = InlineKeyboardBuilder()
    kb.button(text="Открыть личный кабинет", web_app=WebAppInfo(url=view_url))
    kb.adjust(1)
    return kb.as_markup()


class ContentCardSaveBody(BaseModel):
    """Сохранение карточки редактора (hint viewer): проверка через Telegram init_data."""

    init_data: str = Field(..., min_length=1)
    file_name: str = Field(..., max_length=255)
    frames: dict[str, Any]
    labels: list[str] | None = None
    chat_id: int | None = None


class ContentCardFileNameCheckBody(BaseModel):
    """Проверка, есть ли уже карточка с тем же исходным именем файла (file_name)."""

    init_data: str = Field(..., min_length=1)
    file_name: str = Field(..., max_length=255)


class ContentCardBoardXgidCheckBody(BaseModel):
    """Проверка, есть ли карточка с той же строкой позиции (board_xgid), что и у снимка доски."""

    init_data: str = Field(..., min_length=1)
    board_xgid: str = Field(..., min_length=1, max_length=8000)


class ContentCardFetchBody(BaseModel):
    """Загрузка сохранённой карточки для просмотра (Telegram WebApp)."""

    init_data: str | None = None
    fab_token: str | None = None
    content_card_id: int = Field(..., ge=1)


class ContentCardMyListBody(BaseModel):
    """Список карточек пользователя для личного кабинета (Telegram WebApp)."""

    init_data: str | None = None
    fab_token: str | None = None


class ContentCardAssignToUserBody(BaseModel):
    """Выдача выбранных карточек пользователю (только ROOT_ADMIN_IDS)."""

    init_data: str | None = None
    fab_token: str | None = None
    target_user_id: int = Field(..., ge=1)
    content_card_ids: list[int] = Field(..., min_length=1, max_length=3000)


class ContentCardGenerateLinkBody(BaseModel):
    """Генерация одноразовой deep-link для активации карточек (только ROOT_ADMIN_IDS)."""

    init_data: str | None = None
    fab_token: str | None = None
    content_card_ids: list[int] = Field(..., min_length=1, max_length=3000)


class LabelPresetCreateBody(BaseModel):
    init_data: str | None = None
    fab_token: str | None = None
    value: str = Field(..., min_length=1, max_length=255)


class LabelPresetDeleteBody(BaseModel):
    init_data: str | None = None
    fab_token: str | None = None
    preset_id: int = Field(..., ge=1)


class TextStylePresetCreateBody(BaseModel):
    init_data: str | None = None
    fab_token: str | None = None
    name: str = Field(..., min_length=1, max_length=80)
    payload: dict[str, Any]


class TextStylePresetDeleteBody(BaseModel):
    init_data: str | None = None
    fab_token: str | None = None
    preset_id: int = Field(..., ge=1)


class FrameTemplateCreateBody(BaseModel):
    """Сохранение шаблона кадра редактора (JSON payload после upload медиа в S3)."""

    init_data: str | None = None
    fab_token: str | None = None
    name: str = Field(..., min_length=1, max_length=200)
    payload: dict[str, Any]


class FrameTemplateDeleteBody(BaseModel):
    init_data: str | None = None
    fab_token: str | None = None
    template_id: int = Field(..., ge=1)


class ContentCardMarkViewedBody(BaseModel):
    """Отметка карточки как просмотренной для текущего пользователя."""

    init_data: str | None = None
    fab_token: str | None = None
    content_card_id: int = Field(..., ge=1)


class ContentCardDeleteBody(BaseModel):
    """Удаление карточки из БД (только ROOT_ADMIN_IDS)."""

    init_data: str | None = None
    fab_token: str | None = None
    content_card_id: int = Field(..., ge=1)


class ContentCardInteractiveRecordBody(BaseModel):
    """Запись ответа в интерактиве «лучший ход»."""

    init_data: str | None = None
    fab_token: str | None = None
    content_card_id: int = Field(..., ge=1)
    correct: bool


class ContentCardInteractiveStatsBody(BaseModel):
    """Запрос статистики интерактива по карточке."""

    init_data: str | None = None
    fab_token: str | None = None
    content_card_id: int = Field(..., ge=1)


class ContentCardSetStatusBody(BaseModel):
    """Ручная установка статуса карточки для текущего пользователя."""

    init_data: str | None = None
    fab_token: str | None = None
    content_card_id: int = Field(..., ge=1)
    status: UserContentCardStatus


class ContentCardHintMatBody(BaseModel):
    """Скачивание исходного .mat из S3 (hints/{game_id}.mat) по имени файла карточки."""

    init_data: str | None = None
    fab_token: str | None = None
    content_card_id: int = Field(..., ge=1)


def _sanitize_text_style_preset_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Некорректный payload пресета")

    def _int(value: Any, fallback: int, min_v: int, max_v: int) -> int:
        try:
            n = int(value)
        except (TypeError, ValueError):
            n = fallback
        return max(min_v, min(max_v, n))

    text_align = str(payload.get("textAlign") or "left").strip().lower()
    if text_align not in {"left", "center", "right", "justify"}:
        text_align = "left"

    font_weight = str(payload.get("fontWeight") or "normal").strip().lower()
    if font_weight not in {"normal", "bold"}:
        font_weight = "normal"

    font_style = str(payload.get("fontStyle") or "normal").strip().lower()
    if font_style not in {"normal", "italic"}:
        font_style = "normal"

    text_decoration = str(payload.get("textDecoration") or "none").strip().lower()
    if text_decoration not in {"none", "underline"}:
        text_decoration = "none"

    return {
        "fontSizePx": _int(payload.get("fontSizePx"), 16, 8, 200),
        "textColor": str(payload.get("textColor") or "#333333")[:32],
        "textAlign": text_align,
        "lineHeightPx": _int(payload.get("lineHeightPx"), 20, 8, 120),
        "paddingPx": _int(payload.get("paddingPx"), 8, 0, 100),
        "backgroundColor": str(payload.get("backgroundColor") or "#ffffff")[:32],
        "fontWeight": font_weight,
        "fontStyle": font_style,
        "textDecoration": text_decoration,
    }


async def _resolve_hint_mat_location(content_card_id: int) -> tuple[str, str]:
    async with async_session_maker() as session:
        card_dao = ContentCardDAO(session)
        card = await card_dao.find_one_or_none_by_id(content_card_id)
        if not card:
            raise HTTPException(status_code=404, detail="Карточка не найдена")

    fname = os.path.basename((card.file_name or "").strip())[:255]
    if not fname:
        raise HTTPException(status_code=400, detail="У карточки не задано имя файла")
    stem, _, ext = fname.rpartition(".")
    if ext.lower() != "mat" or not stem:
        raise HTTPException(
            status_code=400,
            detail="Ожидается имя вида {game_id}.mat для скачивания из hints/",
        )
    game_id = stem
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,220}", game_id):
        raise HTTPException(
            status_code=400, detail="Некорректный game_id в имени файла"
        )

    return HintS3Storage.mat_key(game_id), fname


class ContentCardUpdateBody(BaseModel):
    """Обновление JSON кадров существующей карточки (только ROOT_ADMIN_IDS)."""

    init_data: str = Field(..., min_length=1)
    content_card_id: int = Field(..., ge=1)
    frames: dict[str, Any]


class ContentCardMetaUpdateBody(BaseModel):
    """Обновление метаданных карточки (метки/примечания) без изменения кадров."""

    init_data: str | None = None
    fab_token: str | None = None
    content_card_id: int = Field(..., ge=1)
    labels: list[str] | None = None
    notes: str | None = None


class ContentCardMediaListBody(BaseModel):
    """Список объектов в S3 под префиксом медиа карточек текущего админа (для галереи в редакторе)."""

    init_data: str | None = None
    fab_token: str | None = None
    continuation_token: str | None = None
    limit: int = Field(48, ge=1, le=100)


class CabinetGalleryListBody(BaseModel):
    """Список изображений общей галереи кабинета карточек (S3); просмотр — любой авторизованный WebApp."""

    init_data: str | None = None
    fab_token: str | None = None
    continuation_token: str | None = None
    limit: int = Field(48, ge=1, le=100)


class CabinetGalleryDeleteBody(BaseModel):
    init_data: str | None = None
    fab_token: str | None = None
    key: str = Field(..., min_length=1, max_length=512)


class CabinetGalleryShareBody(BaseModel):
    """Deep-link на отправку картинки из галереи кабинета (Redis + /start imglink_)."""

    init_data: str | None = None
    fab_token: str | None = None
    s3_key: str = Field(..., min_length=1, max_length=512)


async def _resolve_content_cards_user_id(
    init_data: str | None, fab_token: str | None
) -> int:
    if init_data:
        user_data = verify_telegram_webapp_data(init_data)
        if not user_data:
            raise HTTPException(status_code=401, detail="Недействительные данные Telegram")
        uid = (user_data.get("user") or {}).get("id")
        if uid is None:
            raise HTTPException(status_code=401, detail="В init_data нет user")
        return int(uid)

    if fab_token:
        token_val = await redis_client.get(f"fab_cards_auth:{fab_token}")
        if not token_val:
            raise HTTPException(status_code=401, detail="Недействительный FAB-токен")
        return int(token_val)

    raise HTTPException(status_code=401, detail="Требуется init_data или fab_token")


async def _require_admin_session_user_id(request: Request) -> int:
    session_token = request.cookies.get("admin_session")
    if not session_token:
        raise HTTPException(status_code=401, detail="Unauthorized")
    admin_id_raw = await redis_client.get(f"admin_session:{session_token}")
    if not admin_id_raw:
        raise HTTPException(status_code=401, detail="Unauthorized")
    admin_id = int(admin_id_raw)
    if admin_id not in settings.ROOT_ADMIN_IDS:
        raise HTTPException(status_code=403, detail="Not an admin")
    return admin_id


async def _issue_fab_cards_auth_token(user_id: int) -> str:
    fab_token = secrets.token_urlsafe(24)
    await redis_client.set(f"fab_cards_auth:{fab_token}", str(user_id), expire=7200)
    return fab_token


async def _user_can_access_content_card_interactive(
    session, user_id: int, content_card_id: int
) -> bool:
    """Доступ как у fetch: выдача user_content_cards или ROOT_ADMIN и существующая карточка."""
    ucc_dao = UserContentCardDAO(session)
    link = await ucc_dao.find_one_by_user_and_card(user_id, content_card_id)
    if link:
        return True
    if user_id in settings.ROOT_ADMIN_IDS:
        card_dao = ContentCardDAO(session)
        card = await card_dao.find_one_or_none_by_id(content_card_id)
        return card is not None
    return False


async def _build_start_link_for_cards_activation(link_token: str) -> str:
    me = await bot.get_me()
    if not me.username:
        raise HTTPException(
            status_code=500,
            detail="Не удалось определить username бота для генерации ссылки",
        )
    payload = f"cardlink_{link_token}"
    return f"https://t.me/{me.username}?start={payload}"


async def _build_start_link_for_gallery_image_share(share_token: str) -> str:
    me = await bot.get_me()
    if not me.username:
        raise HTTPException(
            status_code=500,
            detail="Не удалось определить username бота для генерации ссылки",
        )
    payload = f"imglink_{share_token}"
    return f"https://t.me/{me.username}?start={payload}"


async def _build_start_link_for_folder_share(link_token: str) -> str:
    me = await bot.get_me()
    if not me.username:
        raise HTTPException(
            status_code=500,
            detail="Не удалось определить username бота для генерации ссылки",
        )
    payload = f"folderlink_{link_token}"
    return f"https://t.me/{me.username}?start={payload}"


@app.get("/admin/cards-cabinet")
async def admin_cards_cabinet_bridge(request: Request):
    """
    Мост FAB -> кабинет карточек: создаёт временный fab_token и редиректит в /cards-cabinet.
    Доступно только авторизованному администратору FAB (cookie admin_session).
    """
    admin_id = await _require_admin_session_user_id(request)
    fab_token = await _issue_fab_cards_auth_token(admin_id)
    url = f"/cards-cabinet?fab_token={fab_token}"
    return RedirectResponse(url=url, status_code=302)


@app.get("/admin/content-card-view/{content_card_id}")
async def admin_content_card_view_bridge(content_card_id: int, request: Request):
    """
    Мост FAB -> просмотр конкретной карточки в WebApp.
    Доступно только авторизованному администратору FAB (cookie admin_session).
    """
    if content_card_id < 1:
        raise HTTPException(status_code=400, detail="Некорректный content_card_id")
    admin_id = await _require_admin_session_user_id(request)
    fab_token = await _issue_fab_cards_auth_token(admin_id)
    url = (
        f"/content-card-view?content_card_id={content_card_id}"
        f"&fab_token={fab_token}"
    )
    return RedirectResponse(url=url, status_code=302)


@app.post("/api/content_cards/check_file_name")
async def check_content_card_file_name(body: ContentCardFileNameCheckBody):
    """
    Возвращает, существует ли карточка с таким же file_name (как при сохранении — basename, обрезка).
    """
    user_data = verify_telegram_webapp_data(body.init_data)
    if not user_data:
        raise HTTPException(status_code=401, detail="Недействительные данные Telegram")
    tg_user = user_data.get("user") or {}
    user_id = tg_user.get("id")
    if user_id is None:
        raise HTTPException(status_code=401, detail="В init_data нет user")
    user_id = int(user_id)
    _require_content_card_admin(user_id)

    safe_name = os.path.basename(body.file_name.strip())[:255] or "card"
    async with async_session_maker() as session:
        card_dao = ContentCardDAO(session)
        existing = await card_dao.find_one_by_file_name(safe_name)
        if existing:
            return {"exists": True, "content_card_id": existing.id}
        return {"exists": False, "content_card_id": None}


@app.post("/api/content_cards/check_board_xgid")
async def check_content_card_board_xgid(body: ContentCardBoardXgidCheckBody):
    """
    Есть ли карточка с таким же board_xgid (колонка в content_cards, из снимка доски).
    """
    user_data = verify_telegram_webapp_data(body.init_data)
    if not user_data:
        raise HTTPException(status_code=401, detail="Недействительные данные Telegram")
    tg_user = user_data.get("user") or {}
    user_id = tg_user.get("id")
    if user_id is None:
        raise HTTPException(status_code=401, detail="В init_data нет user")
    user_id = int(user_id)
    _require_content_card_admin(user_id)

    normalized = str(body.board_xgid or "").strip()[:8000]
    if not normalized:
        raise HTTPException(status_code=400, detail="Пустая строка позиции")

    async with async_session_maker() as session:
        result = await session.execute(
            select(ContentCard.id)
            .where(ContentCard.board_xgid == normalized)
            .limit(1)
        )
        existing_id = result.scalar_one_or_none()
        if existing_id is not None:
            return {"exists": True, "content_card_id": int(existing_id)}
        return {"exists": False, "content_card_id": None}


@app.post("/api/content_cards/save")
async def save_content_card(body: ContentCardSaveBody):
    """
    Создаёт новую карточку (JSON кадров). Доступно только Telegram-пользователям из ROOT_ADMIN_IDS.
    """
    user_data = verify_telegram_webapp_data(body.init_data)
    if not user_data:
        raise HTTPException(status_code=401, detail="Недействительные данные Telegram")

    tg_user = user_data.get("user") or {}
    user_id = tg_user.get("id")
    if user_id is None:
        raise HTTPException(status_code=401, detail="В init_data нет user")

    user_id = int(user_id)
    _require_content_card_admin(user_id)
    if body.chat_id is not None and int(body.chat_id) != user_id:
        raise HTTPException(status_code=403, detail="chat_id не совпадает с пользователем")

    frames_inner = body.frames.get("frames")
    if not isinstance(frames_inner, list) or len(frames_inner) == 0:
        raise HTTPException(
            status_code=400,
            detail="Поле frames.frames должно быть непустым массивом",
        )

    safe_name = os.path.basename(body.file_name.strip())[:255] or "card"
    labels = _normalize_content_card_labels(body.labels)
    board_xgid = _extract_board_xgid_from_frames(body.frames)

    async with async_session_maker() as session:
        user_dao = UserDAO(session)
        user = await user_dao.find_one_or_none_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=404,
                detail="Пользователь не найден в базе. Откройте бота хотя бы раз.",
            )

        card_dao = ContentCardDAO(session)
        ucc_dao = UserContentCardDAO(session)

        new_card = await card_dao.add(
            SContentCardCreate(
                file_name=safe_name,
                frames=body.frames,
                labels=labels,
                board_xgid=board_xgid,
            )
        )
        saved_id = new_card.id
        await ucc_dao.add(
            SUserContentCardCreate(
                user_id=user_id,
                content_card_id=saved_id,
            )
        )
        await session.commit()
        # --- TEST_ONLY: уведомление в Telegram со ссылкой на просмотр (удалить после тестов) ---
        try:
            _view_url = (
                f"{settings.MINI_APP_URL.rstrip('/')}"
                f"/content-card-view?content_card_id={saved_id}"
            )
            await bot.send_message(
                chat_id=user_id,
                text="Карточка сохранена.",
                reply_markup=_content_card_view_webapp_markup(_view_url),
            )
        except Exception as _e:
            logger.warning(
                "TEST_ONLY content_card TG notify (create) skipped: {}",
                _e,
            )
        # --- /TEST_ONLY ---
        return {
            "ok": True,
            "content_card_id": saved_id,
        }


@app.post("/api/content_cards/update")
async def update_content_card(body: ContentCardUpdateBody):
    """
    Обновляет frames у существующей карточки. Только пользователи из ROOT_ADMIN_IDS.
    """
    user_data = verify_telegram_webapp_data(body.init_data)
    if not user_data:
        raise HTTPException(status_code=401, detail="Недействительные данные Telegram")
    tg_user = user_data.get("user") or {}
    user_id = tg_user.get("id")
    if user_id is None:
        raise HTTPException(status_code=401, detail="В init_data нет user")
    user_id = int(user_id)
    _require_content_card_admin(user_id)

    frames_inner = body.frames.get("frames")
    if not isinstance(frames_inner, list) or len(frames_inner) == 0:
        raise HTTPException(
            status_code=400,
            detail="Поле frames.frames должно быть непустым массивом",
        )

    async with async_session_maker() as session:
        card_dao = ContentCardDAO(session)
        card = await card_dao.find_one_or_none_by_id(body.content_card_id)
        if not card:
            raise HTTPException(status_code=404, detail="Карточка не найдена")
        board_xgid = _extract_board_xgid_from_frames(body.frames)
        await card_dao.update(
            body.content_card_id,
            {"frames": body.frames, "board_xgid": board_xgid},
        )
        await session.commit()

    return {"ok": True, "content_card_id": body.content_card_id}


@app.post("/api/content_cards/update_meta")
async def update_content_card_meta(body: ContentCardMetaUpdateBody):
    """
    Обновляет labels/notes у существующей карточки. Только ROOT_ADMIN_IDS.
    """
    user_id = await _resolve_content_cards_user_id(body.init_data, body.fab_token)
    _require_content_card_admin(user_id)

    if body.labels is None and body.notes is None:
        raise HTTPException(status_code=400, detail="Нечего обновлять")

    updates: dict[str, Any] = {}
    if body.labels is not None:
        updates["labels"] = _normalize_content_card_labels(body.labels)
    if body.notes is not None:
        notes = str(body.notes).strip()
        updates["notes"] = notes[:4000] if notes else None

    async with async_session_maker() as session:
        card_dao = ContentCardDAO(session)
        card = await card_dao.find_one_or_none_by_id(body.content_card_id)
        if not card:
            raise HTTPException(status_code=404, detail="Карточка не найдена")
        await card_dao.update(body.content_card_id, updates)
        await session.commit()

    return {"ok": True, "content_card_id": body.content_card_id}


@app.post("/api/content_cards/my_list")
async def content_cards_my_list(body: ContentCardMyListBody):
    """
    Список id карточек, доступных текущему пользователю (связи user_content_cards),
    в стабильном порядке (по id связи).
    """
    user_id = await _resolve_content_cards_user_id(body.init_data, body.fab_token)
    is_root_admin = user_id in settings.ROOT_ADMIN_IDS
    recent_cutoff = datetime.utcnow() - timedelta(days=1)

    async with async_session_maker() as session:
        ucc_dao = UserContentCardDAO(session)
        links = await ucc_dao.get_all_by_user(user_id)
        links.sort(key=lambda row: row.id)
        cards = [
            {
                "content_card_id": row.content_card_id,
                "status": (
                    "RECENT"
                    if (
                        (
                            str(
                                row.card_status.value
                                if hasattr(row.card_status, "value")
                                else row.card_status
                            )
                            == UserContentCardStatus.UNVIEWED.value
                        )
                        and
                        row.created_at
                        and row.created_at >= recent_cutoff
                    )
                    else (
                        row.card_status.value
                        if hasattr(row.card_status, "value")
                        else str(row.card_status)
                    )
                ),
                "labels": (
                    list(row.content_card.labels)
                    if is_root_admin and row.content_card and row.content_card.labels
                    else []
                ),
                "notes": (
                    (row.content_card.notes or "").strip()
                    if is_root_admin and row.content_card
                    else ""
                ),
            }
            for row in links
        ]

    return {"cards": cards, "is_root_admin": is_root_admin}


@app.post("/api/content_cards/delete")
async def content_cards_delete(body: ContentCardDeleteBody):
    """Удаление карточки и связанных записей (CASCADE). Только ROOT_ADMIN_IDS."""
    user_id = await _resolve_content_cards_user_id(body.init_data, body.fab_token)
    _require_content_card_admin(user_id)

    async with async_session_maker() as session:
        exists = await session.scalar(
            select(ContentCard.id)
            .where(ContentCard.id == body.content_card_id)
            .limit(1)
        )
        if exists is None:
            raise HTTPException(status_code=404, detail="Карточка не найдена")
        await session.execute(
            delete(ContentCardFolderItem).where(
                ContentCardFolderItem.content_card_id == body.content_card_id
            )
        )
        await session.execute(
            delete(ContentCard).where(ContentCard.id == body.content_card_id)
        )
        await session.commit()

    logger.info(
        "Content card deleted: id={} by user_id={}",
        body.content_card_id,
        user_id,
    )
    return {"ok": True, "content_card_id": body.content_card_id}


@app.post("/api/content_cards/create_empty")
async def content_cards_create_empty(body: ContentCardMyListBody):
    """
    Создаёт карточку с одним пустым кадром и выдаёт её текущему админу.
    Только ROOT_ADMIN_IDS.
    """
    user_id = await _resolve_content_cards_user_id(body.init_data, body.fab_token)
    _require_content_card_admin(user_id)

    frames = _build_empty_content_card_frames()
    safe_name = f"cabinet_new_{uuid.uuid4().hex[:12]}.json"

    async with async_session_maker() as session:
        user_dao = UserDAO(session)
        user = await user_dao.find_one_or_none_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=404,
                detail="Пользователь не найден в базе. Откройте бота хотя бы раз.",
            )

        card_dao = ContentCardDAO(session)
        ucc_dao = UserContentCardDAO(session)

        new_card = await card_dao.add(
            SContentCardCreate(
                file_name=safe_name,
                frames=frames,
                labels=None,
                board_xgid=None,
            )
        )
        saved_id = new_card.id
        await ucc_dao.add(
            SUserContentCardCreate(
                user_id=user_id,
                content_card_id=saved_id,
            )
        )
        await session.commit()

    logger.info(
        "Content card created (empty): id={} by user_id={}",
        saved_id,
        user_id,
    )
    return {
        "ok": True,
        "content_card_id": saved_id,
        "status": UserContentCardStatus.UNVIEWED.value,
    }


@app.post("/api/content_cards/all_labels")
async def content_cards_all_labels(body: ContentCardMyListBody):
    """Все уникальные метки карточек (только ROOT_ADMIN_IDS)."""
    user_id = await _resolve_content_cards_user_id(body.init_data, body.fab_token)
    _require_content_card_admin(user_id)

    async with async_session_maker() as session:
        rows = await session.execute(select(ContentCard.labels))
        labels_set: set[str] = set()
        for (labels,) in rows.all():
            if not labels:
                continue
            for item in labels:
                if item is None:
                    continue
                text = str(item).strip()
                if text:
                    labels_set.add(text)

    return {"labels": sorted(labels_set, key=lambda x: x.lower())}


@app.post("/api/content_cards/admin_users")
async def content_cards_admin_users(body: ContentCardMyListBody):
    """Список пользователей для модалки назначения карточек (только ROOT_ADMIN_IDS)."""
    user_id = await _resolve_content_cards_user_id(body.init_data, body.fab_token)
    _require_content_card_admin(user_id)

    async with async_session_maker() as session:
        result = await session.execute(
            select(User.id, User.username, User.admin_insert_name).order_by(User.id.asc())
        )
        users = [
            {
                "id": int(row_id),
                "username": str(username or ""),
                "assigned_name": str(admin_insert_name or ""),
            }
            for row_id, username, admin_insert_name in result.all()
        ]
    return {"users": users}


@app.post("/api/content_cards/assign_to_user")
async def content_cards_assign_to_user(body: ContentCardAssignToUserBody):
    """Выдать выбранные карточки пользователю и отправить Telegram-уведомление."""
    user_id = await _resolve_content_cards_user_id(body.init_data, body.fab_token)
    _require_content_card_admin(user_id)

    card_ids_ordered_unique: list[int] = []
    seen_ids: set[int] = set()
    for raw_id in body.content_card_ids:
        try:
            card_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        if card_id < 1 or card_id in seen_ids:
            continue
        seen_ids.add(card_id)
        card_ids_ordered_unique.append(card_id)
    if not card_ids_ordered_unique:
        raise HTTPException(
            status_code=400,
            detail="Нужно передать хотя бы один корректный content_card_id",
        )

    issued_count = 0
    already_had_count = 0
    invalid_count = 0
    async with async_session_maker() as session:
        target_exists = await session.scalar(
            select(User.id).where(User.id == body.target_user_id).limit(1)
        )
        if target_exists is None:
            raise HTTPException(status_code=404, detail="Пользователь не найден")

        existing_cards_result = await session.execute(
            select(ContentCard.id).where(ContentCard.id.in_(card_ids_ordered_unique))
        )
        existing_card_ids = {
            int(row_id) for row_id in existing_cards_result.scalars().all() if row_id is not None
        }
        selected_existing_ids = [
            card_id for card_id in card_ids_ordered_unique if card_id in existing_card_ids
        ]
        invalid_count = len(card_ids_ordered_unique) - len(selected_existing_ids)
        if not selected_existing_ids:
            raise HTTPException(status_code=404, detail="Выбранные карточки не найдены")

        existing_user_links_result = await session.execute(
            select(UserContentCard.content_card_id).where(
                UserContentCard.user_id == body.target_user_id,
                UserContentCard.content_card_id.in_(selected_existing_ids),
            )
        )
        already_has_ids = {
            int(row_id)
            for row_id in existing_user_links_result.scalars().all()
            if row_id is not None
        }
        already_had_count = len(already_has_ids)

        for card_id in selected_existing_ids:
            if card_id in already_has_ids:
                continue
            session.add(
                UserContentCard(
                    user_id=body.target_user_id,
                    content_card_id=card_id,
                )
            )
            issued_count += 1

        if issued_count > 0:
            await session.commit()

    notify_sent = False
    notify_error = None
    if issued_count > 0:
        try:
            cabinet_url = f"{settings.MINI_APP_URL.rstrip('/')}/cards-cabinet"
            await bot.send_message(
                chat_id=body.target_user_id,
                text=(
                    f"Вам зачислено {issued_count} карточек, "
                    "посмотреть их можете в личном кабинете."
                ),
                reply_markup=_cards_cabinet_webapp_markup(cabinet_url),
            )
            notify_sent = True
        except Exception as e:
            notify_error = str(e)
            logger.warning("Не удалось отправить уведомление о выдаче карточек: {}", e)

    return {
        "ok": True,
        "issued_count": issued_count,
        "already_had_count": already_had_count,
        "invalid_count": invalid_count,
        "notify_sent": notify_sent,
        "notify_error": notify_error,
    }


@app.post("/api/content_cards/generate_link")
async def content_cards_generate_link(body: ContentCardGenerateLinkBody):
    """Создать одноразовую deep-link для активации выбранных карточек."""
    user_id = await _resolve_content_cards_user_id(body.init_data, body.fab_token)
    _require_content_card_admin(user_id)

    card_ids_ordered_unique: list[int] = []
    seen_ids: set[int] = set()
    for raw_id in body.content_card_ids:
        try:
            card_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        if card_id < 1 or card_id in seen_ids:
            continue
        seen_ids.add(card_id)
        card_ids_ordered_unique.append(card_id)
    if not card_ids_ordered_unique:
        raise HTTPException(
            status_code=400,
            detail="Нужно передать хотя бы один корректный content_card_id",
        )

    async with async_session_maker() as session:
        existing_cards_result = await session.execute(
            select(ContentCard.id).where(ContentCard.id.in_(card_ids_ordered_unique))
        )
        existing_card_ids = {
            int(card_id)
            for card_id in existing_cards_result.scalars().all()
            if card_id is not None
        }
        selected_existing_ids = [
            card_id for card_id in card_ids_ordered_unique if card_id in existing_card_ids
        ]
        if not selected_existing_ids:
            raise HTTPException(status_code=404, detail="Выбранные карточки не найдены")

        link_dao = ContentCardActivationLinkDAO(session)
        try:
            activation_link = await link_dao.create_link(selected_existing_ids)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        link_token = str(activation_link.link)
        await session.commit()

    start_link = await _build_start_link_for_cards_activation(link_token)
    return {
        "ok": True,
        "link": start_link,
        "token": link_token,
        "cards_count": len(selected_existing_ids),
    }


@app.post("/api/content_cards/assign_preview")
async def content_cards_assign_preview(body: ContentCardAssignToUserBody):
    """Предпросмотр выдачи: какие выбранные карточки уже есть у пользователя."""
    user_id = await _resolve_content_cards_user_id(body.init_data, body.fab_token)
    _require_content_card_admin(user_id)

    card_ids_ordered_unique: list[int] = []
    seen_ids: set[int] = set()
    for raw_id in body.content_card_ids:
        try:
            card_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        if card_id < 1 or card_id in seen_ids:
            continue
        seen_ids.add(card_id)
        card_ids_ordered_unique.append(card_id)
    if not card_ids_ordered_unique:
        raise HTTPException(
            status_code=400,
            detail="Нужно передать хотя бы один корректный content_card_id",
        )

    async with async_session_maker() as session:
        target_exists = await session.scalar(
            select(User.id).where(User.id == body.target_user_id).limit(1)
        )
        if target_exists is None:
            raise HTTPException(status_code=404, detail="Пользователь не найден")

        existing_user_links_result = await session.execute(
            select(UserContentCard.content_card_id).where(
                UserContentCard.user_id == body.target_user_id,
                UserContentCard.content_card_id.in_(card_ids_ordered_unique),
            )
        )
        already_has_ids_set = {
            int(row_id)
            for row_id in existing_user_links_result.scalars().all()
            if row_id is not None
        }
        already_has_ids_ordered = [
            card_id for card_id in card_ids_ordered_unique if card_id in already_has_ids_set
        ]

    return {
        "ok": True,
        "already_had_ids": already_has_ids_ordered,
    }


@app.post("/api/content_cards/label_presets")
async def content_cards_label_presets(body: ContentCardMyListBody):
    """
    Список пресетов меток из БД (тот же контур, что all_labels) — для подстановки в UI меток.
    """
    user_id = await _resolve_content_cards_user_id(body.init_data, body.fab_token)
    _require_content_card_admin(user_id)

    async with async_session_maker() as session:
        result = await session.execute(
            select(LabelPreset.id, LabelPreset.value).order_by(LabelPreset.value)
        )
        rows = result.all()

    return {"presets": [{"id": int(i), "value": v} for (i, v) in rows]}


@app.post("/api/content_cards/label_presets/create")
async def content_cards_label_preset_create(body: LabelPresetCreateBody):
    """Создать пресет метки (только ROOT_ADMIN_IDS)."""
    user_id = await _resolve_content_cards_user_id(body.init_data, body.fab_token)
    _require_content_card_admin(user_id)
    val = str(body.value or "").strip()[:255]
    if not val:
        raise HTTPException(status_code=400, detail="Пустое значение пресета")

    async with async_session_maker() as session:
        preset = LabelPreset(value=val)
        session.add(preset)
        try:
            await session.commit()
            await session.refresh(preset)
        except IntegrityError:
            await session.rollback()
            raise HTTPException(
                status_code=409,
                detail="Такой пресет уже существует",
            )

    return {"id": preset.id, "value": preset.value}


@app.post("/api/content_cards/label_presets/delete")
async def content_cards_label_preset_delete(body: LabelPresetDeleteBody):
    """Удалить пресет метки (только ROOT_ADMIN_IDS)."""
    user_id = await _resolve_content_cards_user_id(body.init_data, body.fab_token)
    _require_content_card_admin(user_id)

    async with async_session_maker() as session:
        exists = await session.scalar(
            select(LabelPreset.id).where(LabelPreset.id == body.preset_id).limit(1)
        )
        if exists is None:
            raise HTTPException(status_code=404, detail="Пресет не найден")
        await session.execute(delete(LabelPreset).where(LabelPreset.id == body.preset_id))
        await session.commit()

    return {"ok": True}


@app.post("/api/content_cards/text_style_presets")
async def content_cards_text_style_presets(body: ContentCardMyListBody):
    """Список пресетов стилей текста из БД (общие для ROOT_ADMIN_IDS)."""
    user_id = await _resolve_content_cards_user_id(body.init_data, body.fab_token)
    _require_content_card_admin(user_id)

    async with async_session_maker() as session:
        result = await session.execute(
            select(TextStylePreset.id, TextStylePreset.name, TextStylePreset.payload_json).order_by(
                TextStylePreset.name
            )
        )
        rows = result.all()

    return {
        "presets": [
            {"id": int(pid), "name": name, "payload": payload or {}}
            for (pid, name, payload) in rows
        ]
    }


@app.post("/api/content_cards/text_style_presets/create")
async def content_cards_text_style_presets_create(body: TextStylePresetCreateBody):
    """Создать пресет стиля текста (только ROOT_ADMIN_IDS)."""
    user_id = await _resolve_content_cards_user_id(body.init_data, body.fab_token)
    _require_content_card_admin(user_id)
    name = str(body.name or "").strip()[:80]
    if not name:
        raise HTTPException(status_code=400, detail="Пустое название пресета")
    payload = _sanitize_text_style_preset_payload(body.payload)

    async with async_session_maker() as session:
        preset = TextStylePreset(name=name, payload_json=payload)
        session.add(preset)
        try:
            await session.commit()
            await session.refresh(preset)
        except IntegrityError:
            await session.rollback()
            raise HTTPException(
                status_code=409,
                detail="Пресет с таким названием уже существует",
            )

    return {"id": preset.id, "name": preset.name, "payload": preset.payload_json or {}}


@app.post("/api/content_cards/text_style_presets/delete")
async def content_cards_text_style_presets_delete(body: TextStylePresetDeleteBody):
    """Удалить пресет стиля текста (только ROOT_ADMIN_IDS)."""
    user_id = await _resolve_content_cards_user_id(body.init_data, body.fab_token)
    _require_content_card_admin(user_id)

    async with async_session_maker() as session:
        exists = await session.scalar(
            select(TextStylePreset.id).where(TextStylePreset.id == body.preset_id).limit(1)
        )
        if exists is None:
            raise HTTPException(status_code=404, detail="Пресет не найден")
        await session.execute(
            delete(TextStylePreset).where(TextStylePreset.id == body.preset_id)
        )
        await session.commit()

    return {"ok": True}


def _frame_template_payload_json_bytes(payload: dict[str, Any]) -> int:
    try:
        raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode(
            "utf-8"
        )
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Некорректный JSON payload")
    return len(raw)


@app.post("/api/content_cards/frame_templates/list")
async def content_cards_frame_templates_list(body: ContentCardMyListBody):
    """Список шаблонов кадра редактора (глобально; только ROOT_ADMIN_IDS)."""
    user_id = await _resolve_content_cards_user_id(body.init_data, body.fab_token)
    _require_content_card_admin(user_id)

    async with async_session_maker() as session:
        result = await session.execute(
            select(
                ContentFrameTemplate.id,
                ContentFrameTemplate.name,
                ContentFrameTemplate.payload_json,
                ContentFrameTemplate.created_at,
            ).order_by(ContentFrameTemplate.name)
        )
        rows = result.all()

    out = []
    for tid, name, payload, created_at in rows:
        lm = created_at
        if lm is not None and getattr(lm, "tzinfo", None) is None:
            lm = lm.replace(tzinfo=timezone.utc)
        lm_iso = lm.isoformat() if lm is not None else None
        out.append(
            {
                "id": int(tid),
                "name": name,
                "payload": payload or {},
                "created_at": lm_iso,
            }
        )

    return {"templates": out}


@app.post("/api/content_cards/frame_templates/create")
async def content_cards_frame_templates_create(body: FrameTemplateCreateBody):
    """Создать шаблон кадра (только ROOT_ADMIN_IDS)."""
    user_id = await _resolve_content_cards_user_id(body.init_data, body.fab_token)
    _require_content_card_admin(user_id)
    name = str(body.name or "").strip()[:200]
    if not name:
        raise HTTPException(status_code=400, detail="Пустое название шаблона")
    pay = body.payload if isinstance(body.payload, dict) else {}
    sz = _frame_template_payload_json_bytes(pay)
    if sz > CC_FRAME_TEMPLATE_MAX_JSON_BYTES:
        raise HTTPException(
            status_code=413,
            detail="Шаблон слишком большой для сохранения",
        )

    async with async_session_maker() as session:
        row = ContentFrameTemplate(name=name, payload_json=pay)
        session.add(row)
        try:
            await session.commit()
            await session.refresh(row)
        except IntegrityError:
            await session.rollback()
            raise HTTPException(
                status_code=409,
                detail="Шаблон с таким названием уже существует",
            )

    return {
        "id": row.id,
        "name": row.name,
        "payload": row.payload_json or {},
    }


@app.post("/api/content_cards/frame_templates/delete")
async def content_cards_frame_templates_delete(body: FrameTemplateDeleteBody):
    """Удалить шаблон кадра (только ROOT_ADMIN_IDS)."""
    user_id = await _resolve_content_cards_user_id(body.init_data, body.fab_token)
    _require_content_card_admin(user_id)

    async with async_session_maker() as session:
        exists = await session.scalar(
            select(ContentFrameTemplate.id)
            .where(ContentFrameTemplate.id == body.template_id)
            .limit(1)
        )
        if exists is None:
            raise HTTPException(status_code=404, detail="Шаблон не найден")
        await session.execute(
            delete(ContentFrameTemplate).where(
                ContentFrameTemplate.id == body.template_id
            )
        )
        await session.commit()

    return {"ok": True}


@app.post("/api/content_cards/mark_viewed")
async def content_cards_mark_viewed(body: ContentCardMarkViewedBody):
    """Помечает карточку как просмотренную (VIEWED) для текущего пользователя."""
    user_id = await _resolve_content_cards_user_id(body.init_data, body.fab_token)

    async with async_session_maker() as session:
        ucc_dao = UserContentCardDAO(session)
        link = await ucc_dao.find_one_by_user_and_card(user_id, body.content_card_id)
        if not link:
            raise HTTPException(status_code=403, detail="Нет доступа к этой карточке")

        if link.card_status == UserContentCardStatus.UNVIEWED:
            link.card_status = UserContentCardStatus.VIEWED
            await session.commit()

    return {"ok": True}


@app.post("/api/content_cards/interactive/record")
async def content_cards_interactive_record(body: ContentCardInteractiveRecordBody):
    """Учёт ответа в интерактиве «лучший ход» (доступ как у fetch)."""
    user_id = await _resolve_content_cards_user_id(body.init_data, body.fab_token)
    incr_c = 1 if body.correct else 0
    incr_w = 0 if body.correct else 1

    async with async_session_maker() as session:
        if not await _user_can_access_content_card_interactive(
            session, user_id, body.content_card_id
        ):
            raise HTTPException(status_code=403, detail="Нет доступа к этой карточке")

        stmt = insert(UserContentCardInteractiveStat).values(
            user_id=user_id,
            content_card_id=body.content_card_id,
            correct_count=incr_c,
            wrong_count=incr_w,
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_ucc_interactive_user_id_content_card_id",
            set_={
                "correct_count": UserContentCardInteractiveStat.correct_count + incr_c,
                "wrong_count": UserContentCardInteractiveStat.wrong_count + incr_w,
                "updated_at": func.now(),
            },
        )
        await session.execute(stmt)
        await session.commit()

    return {"ok": True}


@app.post("/api/content_cards/interactive/stats")
async def content_cards_interactive_stats(body: ContentCardInteractiveStatsBody):
    """Статистика интерактива по карточке для текущего пользователя."""
    user_id = await _resolve_content_cards_user_id(body.init_data, body.fab_token)

    async with async_session_maker() as session:
        if not await _user_can_access_content_card_interactive(
            session, user_id, body.content_card_id
        ):
            raise HTTPException(status_code=403, detail="Нет доступа к этой карточке")

        row = await session.execute(
            select(UserContentCardInteractiveStat).where(
                UserContentCardInteractiveStat.user_id == user_id,
                UserContentCardInteractiveStat.content_card_id == body.content_card_id,
            )
        )
        stat = row.scalar_one_or_none()
        if stat is None:
            return {"correct_count": 0, "wrong_count": 0}
        return {
            "correct_count": int(stat.correct_count),
            "wrong_count": int(stat.wrong_count),
        }


@app.post("/api/content_cards/interactive/stats_total")
async def content_cards_interactive_stats_total(body: ContentCardMyListBody):
    """Суммарная статистика интерактива по всем карточкам текущего пользователя."""
    user_id = await _resolve_content_cards_user_id(body.init_data, body.fab_token)

    async with async_session_maker() as session:
        q = select(
            func.coalesce(func.sum(UserContentCardInteractiveStat.correct_count), 0),
            func.coalesce(func.sum(UserContentCardInteractiveStat.wrong_count), 0),
        ).where(UserContentCardInteractiveStat.user_id == user_id)
        row = await session.execute(q)
        c_sum, w_sum = row.one()
        return {
            "correct_count": int(c_sum),
            "wrong_count": int(w_sum),
        }


@app.post("/api/content_cards/set_status")
async def content_cards_set_status(body: ContentCardSetStatusBody):
    """Устанавливает статус карточки для текущего пользователя."""
    user_id = await _resolve_content_cards_user_id(body.init_data, body.fab_token)

    if body.status in (UserContentCardStatus.UNVIEWED, UserContentCardStatus.VIEWED):
        raise HTTPException(
            status_code=400,
            detail="Статусы UNVIEWED/VIEWED системные и не могут устанавливаться вручную",
        )

    async with async_session_maker() as session:
        ucc_dao = UserContentCardDAO(session)
        link = await ucc_dao.find_one_by_user_and_card(user_id, body.content_card_id)
        if not link:
            raise HTTPException(status_code=403, detail="Нет доступа к этой карточке")

        link.card_status = body.status
        await session.commit()

    return {"ok": True, "status": body.status.value}


@app.post("/api/content_cards/fetch")
async def fetch_content_card(body: ContentCardFetchBody):
    """
    Данные карточки для страницы просмотра: есть связь user_content_cards
    или пользователь в ROOT_ADMIN_IDS.
    Поля file_name, labels и notes отдаются только если user_id в ROOT_ADMIN_IDS.
    """
    user_id = await _resolve_content_cards_user_id(body.init_data, body.fab_token)

    async with async_session_maker() as session:
        ucc_dao = UserContentCardDAO(session)
        link = await ucc_dao.find_one_by_user_and_card(
            user_id, body.content_card_id
        )
        if not link and user_id not in settings.ROOT_ADMIN_IDS:
            raise HTTPException(
                status_code=403, detail="Нет доступа к этой карточке"
            )

        card_dao = ContentCardDAO(session)
        card = await card_dao.find_one_or_none_by_id(body.content_card_id)
        if not card:
            raise HTTPException(status_code=404, detail="Карточка не найдена")

        is_root_admin = user_id in settings.ROOT_ADMIN_IDS
        out: dict[str, Any] = {
            "frames": card.frames,
            "is_content_card_admin": is_root_admin,
            "user_card_status": link.card_status.value if link else None,
        }
        if is_root_admin:
            raw_labels = card.labels
            out["file_name"] = card.file_name
            out["labels"] = list(raw_labels) if raw_labels is not None else []
            out["notes"] = card.notes
            out["board_xgid"] = card.board_xgid
        return out


@app.post("/api/content_cards/hint_mat_download")
async def download_content_card_hint_mat(body: ContentCardHintMatBody):
    """
    Исходный .mat анализа в S3 по ключу hints/{game_id}.mat.
    Имя файла карточки (file_name) должно быть вида {game_id}.mat — как при сохранении из hint viewer.
    Только ROOT_ADMIN_IDS (тот же контур, что и поле «Файл» в информации о карточке).
    """
    user_id = await _resolve_content_cards_user_id(body.init_data, body.fab_token)
    _require_content_card_admin(user_id)

    key, fname = await _resolve_hint_mat_location(body.content_card_id)
    s3 = HintS3Storage.from_settings()
    if not s3.exists(key):
        raise HTTPException(
            status_code=404, detail="Файл .mat не найден в хранилище"
        )
    blob = s3.download_bytes(key)
    disp = _safe_content_disposition_filename(fname, "source.mat")
    headers: dict[str, str] = {
        "Content-Disposition": f'attachment; filename="{disp}"',
        "Cache-Control": "private, no-store",
        "Access-Control-Allow-Origin": "https://web.telegram.org",
    }
    return Response(
        content=blob,
        media_type="application/octet-stream",
        headers=headers,
    )


@app.post("/api/content_cards/hint_mat_download_link")
async def download_content_card_hint_mat_link(body: ContentCardHintMatBody):
    """
    Возвращает временную ссылку для скачивания .mat (TTL 5 минут).
    Используется WebApp-клиентом для мобильного сценария.
    """
    user_id = await _resolve_content_cards_user_id(body.init_data, body.fab_token)
    _require_content_card_admin(user_id)

    key, fname = await _resolve_hint_mat_location(body.content_card_id)
    s3 = HintS3Storage.from_settings()
    if not s3.exists(key):
        raise HTTPException(
            status_code=404, detail="Файл .mat не найден в хранилище"
        )

    token = secrets.token_urlsafe(24)
    payload = json.dumps({"key": key, "file_name": fname}, ensure_ascii=False)
    await redis_client.set(f"hint_mat_dl:{token}", payload, expire=300)
    return {"url": f"/api/content_cards/hint_mat_file?token={token}", "file_name": fname}


@app.get("/api/content_cards/hint_mat_file")
async def download_content_card_hint_mat_by_token(token: str):
    """
    Скачивание .mat по временному токену.
    """
    if not token:
        raise HTTPException(status_code=400, detail="Параметр token обязателен")
    raw = await redis_client.get(f"hint_mat_dl:{token}")
    if not raw:
        raise HTTPException(status_code=401, detail="Ссылка истекла или недействительна")

    try:
        data = json.loads(raw)
    except Exception:
        raise HTTPException(status_code=400, detail="Некорректные данные ссылки")

    key = str((data or {}).get("key") or "")
    fname = str((data or {}).get("file_name") or "source.mat")
    if not key.startswith("hints/"):
        raise HTTPException(status_code=400, detail="Некорректный ключ файла")

    s3 = HintS3Storage.from_settings()
    if not s3.exists(key):
        raise HTTPException(status_code=404, detail="Файл .mat не найден в хранилище")

    blob = s3.download_bytes(key)
    disp = _safe_content_disposition_filename(fname, "source.mat")
    headers: dict[str, str] = {
        "Content-Disposition": f'attachment; filename="{disp}"',
        "Cache-Control": "private, no-store",
        "Access-Control-Allow-Origin": "https://web.telegram.org",
    }
    return Response(
        content=blob,
        media_type="application/octet-stream",
        headers=headers,
    )


@app.post("/api/content_cards/media/upload")
async def content_card_media_upload(
    init_data: str = Form(...),
    file: UploadFile = File(...),
):
    """Загрузка медиа карточки в S3; только пользователи из ROOT_ADMIN_IDS."""
    user_data = verify_telegram_webapp_data(init_data)
    if not user_data:
        raise HTTPException(
            status_code=401, detail="Недействительные данные Telegram"
        )
    uid = (user_data.get("user") or {}).get("id")
    if uid is None:
        raise HTTPException(status_code=401, detail="В init_data нет user")
    uid = int(uid)
    _require_content_card_admin(uid)
    raw = await file.read()
    if len(raw) > CC_MEDIA_MAX_BYTES:
        raise HTTPException(status_code=413, detail="Файл слишком большой")
    ext = _guess_content_upload_extension(file.filename, file.content_type)
    unique_name = f"{uuid.uuid4().hex}{ext}"
    key = HintS3Storage.content_card_media_key(uid, unique_name)
    ct = file.content_type or mimetypes.guess_type(unique_name)[0] or "application/octet-stream"
    if ";" in str(ct):
        ct = str(ct).split(";")[0].strip()
    s3 = HintS3Storage.from_settings()
    s3.upload_bytes(key, raw, content_type=ct)
    logger.info(
        f"Content card media uploaded: key={key} user_id={uid} bytes={len(raw)}"
    )
    return {"s3_key": key, "content_type": ct}


@app.post("/api/content_cards/media/list")
async def content_card_media_list(body: ContentCardMediaListBody):
    """
    Изображения из S3, которые этот админ уже загружал в карточки (префикс content_cards/media/{user_id}/).
    Только ROOT_ADMIN_IDS; для выбора в редакторе без повторной загрузки файла.
    """
    uid = await _resolve_content_cards_user_id(body.init_data, body.fab_token)
    _require_content_card_admin(uid)
    s3 = HintS3Storage.from_settings()
    items, next_tok = s3.list_content_card_media_for_user(
        uid,
        max_keys=body.limit,
        continuation_token=body.continuation_token,
        image_only=True,
    )
    return {"items": items, "continuation_token": next_tok}


@app.post("/api/content_cards/cabinet_gallery/list")
async def cabinet_gallery_list(body: CabinetGalleryListBody):
    uid = await _resolve_content_cards_user_id(body.init_data, body.fab_token)
    s3 = HintS3Storage.from_settings()
    items, next_tok = s3.list_cabinet_gallery(
        max_keys=body.limit,
        continuation_token=body.continuation_token,
        image_only=True,
    )
    return {
        "items": items,
        "continuation_token": next_tok,
        "can_manage": uid in settings.ROOT_ADMIN_IDS,
    }


@app.post("/api/content_cards/cabinet_gallery/upload")
async def cabinet_gallery_upload(
    init_data: str | None = Form(None),
    fab_token: str | None = Form(None),
    file: UploadFile = File(...),
):
    """Загрузка изображения в общую галерею кабинета (S3); только ROOT_ADMIN_IDS."""
    if not (init_data and init_data.strip()) and not (fab_token and fab_token.strip()):
        raise HTTPException(
            status_code=400, detail="Нужен init_data или fab_token",
        )
    uid = await _resolve_content_cards_user_id(
        init_data.strip() if init_data else None,
        fab_token.strip() if fab_token else None,
    )
    _require_content_card_admin(uid)
    raw = await file.read()
    if len(raw) > CC_MEDIA_MAX_BYTES:
        raise HTTPException(status_code=413, detail="Файл слишком большой")
    ext = _guess_content_upload_extension(file.filename, file.content_type)
    unique_name = f"{uuid.uuid4().hex}{ext}"
    ct = file.content_type or mimetypes.guess_type(unique_name)[0] or ""
    if ";" in str(ct):
        ct = str(ct).split(";")[0].strip()
    ct_lower = (ct or "").lower()
    if not ct_lower.startswith("image/"):
        guessed = (mimetypes.guess_type(unique_name)[0] or "").lower()
        if not guessed.startswith("image/"):
            raise HTTPException(status_code=400, detail="Ожидается изображение")
    key = HintS3Storage.cabinet_gallery_media_key(unique_name)
    store_ct = ct if ct_lower.startswith("image/") else (guessed or "application/octet-stream")
    s3 = HintS3Storage.from_settings()
    s3.upload_bytes(key, raw, content_type=store_ct)
    logger.info(f"Cabinet gallery uploaded: key={key} user_id={uid} bytes={len(raw)}")
    return {"s3_key": key, "content_type": store_ct}


@app.post("/api/content_cards/cabinet_gallery/delete")
async def cabinet_gallery_delete(body: CabinetGalleryDeleteBody):
    """Удаление объекта галереи из S3; только ROOT_ADMIN_IDS."""
    uid = await _resolve_content_cards_user_id(body.init_data, body.fab_token)
    _require_content_card_admin(uid)
    key = str(body.key or "").strip()
    if not _is_cabinet_gallery_s3_key(key):
        raise HTTPException(status_code=400, detail="Некорректный key")
    s3 = HintS3Storage.from_settings()
    if not s3.exists(key):
        raise HTTPException(status_code=404, detail="Файл не найден")
    s3.delete_object(key)
    logger.info(f"Cabinet gallery deleted: key={key} user_id={uid}")
    return {"ok": True}


@app.post("/api/content_cards/cabinet_gallery/share_link")
async def cabinet_gallery_share_link(body: CabinetGalleryShareBody):
    """
    Deep-link: в Redis кладётся s3_key по токену; при /start imglink_<token> бот отправляет фото.
    Доступно любому пользователю с валидной сессией кабинета; s3_key только из галереи кабинета.
    Токен живёт до 7 суток, ссылку можно открывать повторно, пока токен в Redis.
    """
    await _resolve_content_cards_user_id(body.init_data, body.fab_token)
    key = str(body.s3_key or "").strip()
    if not HintS3Storage.is_cabinet_gallery_media_key(key):
        raise HTTPException(status_code=400, detail="Некорректный key")
    s3 = HintS3Storage.from_settings()
    if not s3.exists(key):
        raise HTTPException(status_code=404, detail="Файл не найден")
    share_token = secrets.token_urlsafe(18)
    redis_key = f"cabinet_gallery_img_share:{share_token}"
    await redis_client.set(redis_key, key, expire=604800)
    start_link = await _build_start_link_for_gallery_image_share(share_token)
    return {"start_link": start_link}


@app.get("/api/content_cards/media")
async def content_card_media_proxy(
    key: str,
    download: int | None = Query(None, description="1 — Content-Disposition: attachment (скачивание)"),
    filename: str | None = Query(None, description="Имя файла для заголовка attachment"),
):
    """
    Отдаёт файл из S3 по ключу. Доступ не привязан к владельцу: любой, кто знает key
    (обычно из JSON карточки), может отобразить медиа — для будущего шаринга карточек.
    Загрузка: POST .../upload с Telegram init_data и id из ROOT_ADMIN_IDS.
    При download=1 добавляется Content-Disposition: attachment (Telegram WebApp downloadFile и браузеры).
    """
    if not key:
        raise HTTPException(status_code=400, detail="Параметр key обязателен")
    if not _is_public_content_card_media_key(key):
        raise HTTPException(status_code=400, detail="Некорректный key")
    s3 = HintS3Storage.from_settings()
    if not s3.exists(key):
        raise HTTPException(status_code=404, detail="Файл не найден")
    blob = s3.download_bytes(key)
    fname = key.rsplit("/", 1)[-1]
    media_type = mimetypes.guess_type(fname)[0] or "application/octet-stream"
    headers: dict[str, str] = {"Cache-Control": "public, max-age=3600"}
    if download == 1:
        disp_name = _safe_content_disposition_filename(filename, fname)
        headers["Content-Disposition"] = f'attachment; filename="{disp_name}"'
        # Рекомендация Telegram для WebApp.downloadFile на web.telegram.org
        headers["Access-Control-Allow-Origin"] = "https://web.telegram.org"
    return Response(
        content=blob,
        media_type=media_type,
        headers=headers,
    )


# ============================================================
#  Pydantic-модели для API папок карточек
# ============================================================

class FolderBaseBody(BaseModel):
    init_data: str | None = None
    fab_token: str | None = None


class FolderCreateBody(FolderBaseBody):
    name: str = Field(..., min_length=1, max_length=255)
    parent_id: int | None = None
    sort_order: int = 0


class FolderUpdateBody(FolderBaseBody):
    folder_id: int
    name: str | None = Field(None, min_length=1, max_length=255)
    sort_order: int | None = None


class FolderMoveBody(FolderBaseBody):
    folder_id: int
    new_parent_id: int | None = None
    new_sort_order: int = 0


class FolderDeleteBody(FolderBaseBody):
    folder_id: int


class FolderSetItemsBody(FolderBaseBody):
    folder_id: int
    card_ids: list[int]


class FolderAddItemsBody(FolderBaseBody):
    folder_id: int
    card_ids: list[int]


class FolderGenerateLinkBody(FolderBaseBody):
    folder_id: int


class FolderLinkResolveBody(FolderBaseBody):
    folder_token: str
    direct_only: bool = False


# ============================================================
#  Helpers
# ============================================================

def _require_content_card_folder_admin(user_id: int) -> None:
    if user_id not in settings.ROOT_ADMIN_IDS:
        raise HTTPException(status_code=403, detail="Только администратор")


def _serialize_folder(f: ContentCardFolder) -> dict:
    return {
        "id": f.id,
        "name": f.name,
        "parent_id": f.parent_id,
        "sort_order": f.sort_order,
        "created_by_admin_id": f.created_by_admin_id,
        "created_at": f.created_at.isoformat() if f.created_at else None,
    }


def _serialize_folder_link(link: ContentCardFolderLink) -> dict:
    return {
        "link_token": link.link_token,
        "folder_id": link.folder_id,
        "is_active": link.is_active,
    }


def _sort_folder_tree_nodes(nodes: list[dict]) -> None:
    nodes.sort(key=lambda n: (n.get("sort_order", 0), n.get("id", 0)))
    for node in nodes:
        children = node.get("children")
        if children:
            _sort_folder_tree_nodes(children)


def _collect_folder_tree_ids(nodes: list[dict], placed: set[int]) -> None:
    for node in nodes:
        placed.add(node["id"])
        children = node.get("children")
        if children:
            _collect_folder_tree_ids(children, placed)


def _build_folder_tree(folders: list[ContentCardFolder], direct_counts: dict[int, int]) -> list[dict]:
    nodes: dict[int, dict] = {}
    for f in folders:
        nodes[f.id] = {
            **_serialize_folder(f),
            "children": [],
            "direct_cards_count": direct_counts.get(f.id, 0),
        }

    roots: list[dict] = []
    for f in folders:
        node = nodes[f.id]
        if f.parent_id is not None and f.parent_id in nodes:
            nodes[f.parent_id]["children"].append(node)
        else:
            roots.append(node)

    placed: set[int] = set()
    _collect_folder_tree_ids(roots, placed)
    for f in folders:
        if f.id not in placed:
            roots.append(nodes[f.id])

    _sort_folder_tree_nodes(roots)
    return roots


# ============================================================
#  Admin API: папки карточек
# ============================================================

@app.post("/api/content_cards/folders/tree")
async def folder_tree(body: FolderBaseBody):
    """Вернуть дерево папок со счётчиками карточек. Только ROOT_ADMIN."""
    user_id = await _resolve_content_cards_user_id(body.init_data, body.fab_token)
    _require_content_card_folder_admin(user_id)

    async with async_session_maker() as session:
        dao = ContentCardFolderDAO(session)
        folders = await dao.get_all_folders()

        # Считаем прямые карточки каждой папки
        counts_res = await session.execute(
            select(ContentCardFolderItem.folder_id, func.count(ContentCardFolderItem.id))
            .group_by(ContentCardFolderItem.folder_id)
        )
        direct_counts: dict[int, int] = {row[0]: row[1] for row in counts_res.all()}

        # Строим дерево: словарь id → узел
        roots = _build_folder_tree(folders, direct_counts)

    return {"folders": roots}


@app.post("/api/content_cards/folders/create")
async def folder_create(body: FolderCreateBody):
    """Создать папку. Только ROOT_ADMIN."""
    user_id = await _resolve_content_cards_user_id(body.init_data, body.fab_token)
    _require_content_card_folder_admin(user_id)

    async with async_session_maker() as session:
        async with session.begin():
            dao = ContentCardFolderDAO(session)
            if body.parent_id is not None:
                parent = await dao.get_folder_by_id(body.parent_id)
                if not parent:
                    raise HTTPException(status_code=404, detail="Родительская папка не найдена")
            folder = await dao.create_folder(
                name=body.name,
                parent_id=body.parent_id,
                sort_order=body.sort_order,
                admin_id=user_id,
            )
            return {"folder": _serialize_folder(folder)}


@app.post("/api/content_cards/folders/update")
async def folder_update(body: FolderUpdateBody):
    """Обновить имя/сортировку папки. Только ROOT_ADMIN."""
    user_id = await _resolve_content_cards_user_id(body.init_data, body.fab_token)
    _require_content_card_folder_admin(user_id)

    async with async_session_maker() as session:
        async with session.begin():
            dao = ContentCardFolderDAO(session)
            folder = await dao.update_folder(
                folder_id=body.folder_id,
                name=body.name,
                sort_order=body.sort_order,
            )
            if not folder:
                raise HTTPException(status_code=404, detail="Папка не найдена")
            return {"folder": _serialize_folder(folder)}


@app.post("/api/content_cards/folders/move")
async def folder_move(body: FolderMoveBody):
    """Перенести папку (смена parent). Проверяет цикличность. Только ROOT_ADMIN."""
    user_id = await _resolve_content_cards_user_id(body.init_data, body.fab_token)
    _require_content_card_folder_admin(user_id)

    async with async_session_maker() as session:
        async with session.begin():
            dao = ContentCardFolderDAO(session)
            try:
                folder = await dao.move_folder(
                    folder_id=body.folder_id,
                    new_parent_id=body.new_parent_id,
                    new_sort_order=body.new_sort_order,
                )
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
            if not folder:
                raise HTTPException(status_code=404, detail="Папка не найдена")
            return {"folder": _serialize_folder(folder)}


@app.post("/api/content_cards/folders/delete")
async def folder_delete(body: FolderDeleteBody):
    """Удалить папку. Дети поднимаются на уровень родителя. Только ROOT_ADMIN."""
    user_id = await _resolve_content_cards_user_id(body.init_data, body.fab_token)
    _require_content_card_folder_admin(user_id)

    async with async_session_maker() as session:
        async with session.begin():
            dao = ContentCardFolderDAO(session)
            ok = await dao.delete_folder(body.folder_id)
            if not ok:
                raise HTTPException(status_code=404, detail="Папка не найдена")
    return {"ok": True}


@app.post("/api/content_cards/folders/add_items")
async def folder_add_items(body: FolderAddItemsBody):
    """Добавить карточки в папку (merge, без дубликатов). Только ROOT_ADMIN."""
    user_id = await _resolve_content_cards_user_id(body.init_data, body.fab_token)
    _require_content_card_folder_admin(user_id)

    card_ids: list[int] = []
    seen: set[int] = set()
    for raw_id in body.card_ids:
        try:
            cid = int(raw_id)
        except (TypeError, ValueError):
            continue
        if cid < 1 or cid in seen:
            continue
        seen.add(cid)
        card_ids.append(cid)
    if not card_ids:
        raise HTTPException(status_code=400, detail="Нужен хотя бы один content_card_id")

    async with async_session_maker() as session:
        async with session.begin():
            dao = ContentCardFolderDAO(session)
            folder = await dao.get_folder_by_id(body.folder_id)
            if not folder:
                raise HTTPException(status_code=404, detail="Папка не найдена")
            added = await dao.add_cards_to_folder(body.folder_id, card_ids)
    return {"ok": True, "added_count": added}


@app.post("/api/content_cards/folders/set_items")
async def folder_set_items(body: FolderSetItemsBody):
    """Батч-замена карточек в папке (add/remove/reorder). Только ROOT_ADMIN."""
    user_id = await _resolve_content_cards_user_id(body.init_data, body.fab_token)
    _require_content_card_folder_admin(user_id)

    async with async_session_maker() as session:
        async with session.begin():
            dao = ContentCardFolderDAO(session)
            folder = await dao.get_folder_by_id(body.folder_id)
            if not folder:
                raise HTTPException(status_code=404, detail="Папка не найдена")
            await dao.set_folder_items(
                folder_id=body.folder_id,
                card_ids_ordered=body.card_ids,
            )
    return {"ok": True}


# ============================================================
#  API ссылок на папки (generate + read-only resolve)
# ============================================================

@app.post("/api/content_cards/folders/generate_link")
async def folder_generate_link(body: FolderGenerateLinkBody):
    """Создать/получить активную ссылку на папку. Только ROOT_ADMIN."""
    user_id = await _resolve_content_cards_user_id(body.init_data, body.fab_token)
    _require_content_card_folder_admin(user_id)

    async with async_session_maker() as session:
        async with session.begin():
            folder_dao = ContentCardFolderDAO(session)
            folder = await folder_dao.get_folder_by_id(body.folder_id)
            if not folder:
                raise HTTPException(status_code=404, detail="Папка не найдена")
            link_dao = ContentCardFolderLinkDAO(session)
            link = await link_dao.get_or_create_link(
                folder_id=body.folder_id,
                admin_id=user_id,
            )
            link_payload = _serialize_folder_link(link)

    start_link = await _build_start_link_for_folder_share(link_payload["link_token"])
    return {**link_payload, "start_link": start_link}


@app.post("/api/content_cards/folders/link_resolve")
async def folder_link_resolve(body: FolderLinkResolveBody):
    """
    По folder_token вернуть папку и список карточек (read-only, без записи в user_content_cards).
    direct_only=True — только карточки этой папки, без подпапок.
    """
    user_id = await _resolve_content_cards_user_id(body.init_data, body.fab_token)

    token = str(body.folder_token or "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="folder_token обязателен")

    async with async_session_maker() as session:
        link_dao = ContentCardFolderLinkDAO(session)
        link = await link_dao.find_by_token(token)
        if not link:
            raise HTTPException(status_code=404, detail="Ссылка не найдена или неактивна")

        folder_dao = ContentCardFolderDAO(session)
        folder = await folder_dao.get_folder_by_id(link.folder_id)
        if not folder:
            raise HTTPException(status_code=404, detail="Папка не найдена")

        if body.direct_only:
            card_ids = await folder_dao.get_folder_card_ids(link.folder_id)
        else:
            card_ids = await folder_dao.collect_card_ids_for_folder_tree(
                root_folder_id=link.folder_id, include_children=True
            )

        child_folders: list[dict] = []
        all_folders = await folder_dao.get_all_folders()
        counts_res = await session.execute(
            select(ContentCardFolderItem.folder_id, func.count(ContentCardFolderItem.id))
            .group_by(ContentCardFolderItem.folder_id)
        )
        direct_counts: dict[int, int] = {row[0]: row[1] for row in counts_res.all()}
        for f in all_folders:
            if f.parent_id == link.folder_id:
                child_folders.append({
                    "id": f.id,
                    "name": f.name,
                    "parent_id": f.parent_id,
                    "direct_cards_count": direct_counts.get(f.id, 0),
                })

        cards_data: list[dict] = []
        if card_ids:
            cards_res = await session.execute(
                select(ContentCard).where(ContentCard.id.in_(card_ids))
            )
            cards_by_id: dict[int, ContentCard] = {
                c.id: c for c in cards_res.scalars().all()
            }
            for cid in card_ids:
                c = cards_by_id.get(cid)
                if c:
                    cards_data.append({
                        "id": c.id,
                        "file_name": c.file_name,
                        "notes": c.notes,
                        "labels": c.labels or [],
                        "board_xgid": c.board_xgid,
                    })

        return {
            "folder": _serialize_folder(folder),
            "card_ids": card_ids,
            "cards": cards_data,
            "child_folders": child_folders,
            "is_root_admin": user_id in settings.ROOT_ADMIN_IDS,
        }


flask_app, _ = create_app()
app.mount("/admin", WSGIMiddleware(flask_app))
