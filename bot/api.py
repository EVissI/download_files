import mimetypes
import uuid

from fastapi import FastAPI, Request, Response, HTTPException, File, Form, UploadFile, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.wsgi import WSGIMiddleware
from sqlalchemy import select
from typing import Any, Optional
import secrets

from pydantic import BaseModel, Field

from bot.routers.hint_viewer_router import hint_viewer_api_router
from bot.routers.short_board import short_board_api_router
from bot.flask_admin.appbuilder_main import create_app
from bot.common.utils.tg_auth import verify_telegram_webapp_data
from bot.common.service.hint_s3_service import HintS3Storage
from bot.config import settings
from bot.config import bot, SUPPORT_TG_ID, translator_hub
from bot.common.utils.i18n import get_text_for_locale
from bot.db.redis import redis_client
from bot.common.kbds.inline.activate_promo import get_activate_promo_keyboard
from bot.common.func.pokaz_func import get_hints_for_xgid
from bot.db.database import async_session_maker
from bot.db.dao import (
    UserDAO,
    MessagesTextsDAO,
    ContentCardDAO,
    UserContentCardDAO,
)
from bot.db.models import ContentCard, ServiceType, UserContentCardStatus
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
    return templates.TemplateResponse(
        "pokaz.html",
        {
            "request": request,
            "chat_id": chat_id,
            "xgid": xgid,
            "lang": lang,
            "i18n": translations,
        },
    )


@app.get("/content-card-view")
async def content_card_view_page(request: Request):
    """Просмотр сохранённой карточки контента (кадры, только переключение)."""
    cache_timestamp = int(time.time())
    response = templates.TemplateResponse(
        "content_card_view.html",
        {"request": request, "cache_timestamp": cache_timestamp},
    )
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@app.get("/cards-cabinet")
async def cards_cabinet_page(request: Request):
    """Личный кабинет: сетка карточек пользователя (Telegram WebApp)."""
    cache_timestamp = int(time.time())
    response = templates.TemplateResponse(
        "cards_cabinet.html",
        {"request": request, "cache_timestamp": cache_timestamp},
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
    return templates.TemplateResponse("admin_login.html", {"request": request})


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
    Допустимый ключ для публичного чтения: content_cards/media/{user_id}/{filename}.
    Доступ по знанию полного ключа (в JSON карточки) — чтобы другие пользователи могли
    открыть карточку после шаринга; перебор ключей не предполагается (случайное имя файла).
    """
    parts = key.split("/")
    if len(parts) != 4:
        return False
    if parts[0] != "content_cards" or parts[1] != "media":
        return False
    if not parts[2].isdigit():
        return False
    name = parts[3]
    if not name or len(name) > 220 or ".." in name:
        return False
    return all(c.isalnum() or c in "._-" for c in name)


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


def _content_card_view_webapp_markup(view_url: str) -> InlineKeyboardMarkup:
    """Кнопка Web App — иначе при открытии ссылки из чата init_data в Telegram не передаётся."""
    kb = InlineKeyboardBuilder()
    kb.button(text="Открыть карточку", web_app=WebAppInfo(url=view_url))
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


class ContentCardFetchBody(BaseModel):
    """Загрузка сохранённой карточки для просмотра (Telegram WebApp)."""

    init_data: str | None = None
    fab_token: str | None = None
    content_card_id: int = Field(..., ge=1)


class ContentCardMyListBody(BaseModel):
    """Список карточек пользователя для личного кабинета (Telegram WebApp)."""

    init_data: str | None = None
    fab_token: str | None = None


class ContentCardMarkViewedBody(BaseModel):
    """Отметка карточки как просмотренной для текущего пользователя."""

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

    init_data: str = Field(..., min_length=1)
    continuation_token: str | None = None
    limit: int = Field(48, ge=1, le=100)


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
        await card_dao.update(body.content_card_id, {"frames": body.frames})
        await session.commit()

    return {"ok": True, "content_card_id": body.content_card_id}


@app.post("/api/content_cards/update_meta")
async def update_content_card_meta(body: ContentCardMetaUpdateBody):
    """
    Обновляет labels/notes у существующей карточки. Только ROOT_ADMIN_IDS.
    """
    user_id = await _resolve_content_cards_user_id(body.init_data, body.fab_token)
    _require_content_card_admin(user_id)

    labels = _normalize_content_card_labels(body.labels)
    notes = (str(body.notes).strip() if body.notes is not None else "").strip()
    notes = notes[:4000] if notes else None

    async with async_session_maker() as session:
        card_dao = ContentCardDAO(session)
        card = await card_dao.find_one_or_none_by_id(body.content_card_id)
        if not card:
            raise HTTPException(status_code=404, detail="Карточка не найдена")
        await card_dao.update(
            body.content_card_id,
            {
                "labels": labels,
                "notes": notes,
            },
        )
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

    async with async_session_maker() as session:
        ucc_dao = UserContentCardDAO(session)
        links = await ucc_dao.get_all_by_user(user_id)
        links.sort(key=lambda row: row.id)
        cards = [
            {
                "content_card_id": row.content_card_id,
                "status": (
                    row.card_status.value
                    if hasattr(row.card_status, "value")
                    else str(row.card_status)
                ),
                "labels": (
                    list(row.content_card.labels)
                    if is_root_admin and row.content_card and row.content_card.labels
                    else []
                ),
            }
            for row in links
        ]

    return {"cards": cards, "is_root_admin": is_root_admin}


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
    await redis_client.delete(f"hint_mat_dl:{token}")

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
    user_data = verify_telegram_webapp_data(body.init_data)
    if not user_data:
        raise HTTPException(
            status_code=401, detail="Недействительные данные Telegram"
        )
    tg_user = user_data.get("user") or {}
    uid = tg_user.get("id")
    if uid is None:
        raise HTTPException(status_code=401, detail="В init_data нет user")
    uid = int(uid)
    _require_content_card_admin(uid)
    s3 = HintS3Storage.from_settings()
    items, next_tok = s3.list_content_card_media_for_user(
        uid,
        max_keys=body.limit,
        continuation_token=body.continuation_token,
        image_only=True,
    )
    return {"items": items, "continuation_token": next_tok}


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


flask_app, _ = create_app()
app.mount("/admin", WSGIMiddleware(flask_app))
