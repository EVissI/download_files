from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.wsgi import WSGIMiddleware
from typing import Optional
import secrets

from bot.routers.hint_viewer_router import hint_viewer_api_router
from bot.routers.short_board import short_board_api_router
from bot.flask_admin.appbuilder_main import create_app
from bot.common.utils.tg_auth import verify_telegram_webapp_data
from bot.config import settings
from bot.config import bot, SUPPORT_TG_ID, translator_hub
from bot.db.redis import redis_client
from bot.common.kbds.inline.activate_promo import get_activate_promo_keyboard
from bot.common.func.pokaz_func import get_hints_for_xgid
from bot.db.database import async_session_maker
from bot.db.dao import UserDAO, MessagesTextsDAO
from bot.db.models import ServiceType
from loguru import logger
import traceback
import json
import os
from pathlib import Path
from aiogram.types import BufferedInputFile, InlineKeyboardMarkup, InlineKeyboardButton

BASE_DIR = Path(__file__).parent.parent

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


@app.get("/pokaz")
async def get_pokaz(request: Request, chat_id: str = None, xgid: str = None):
    """
    Возвращает HTML-страницу редактора доски нардов.
    Может принимать XGID строку для автоматической загрузки позиции.
    """
    return templates.TemplateResponse(
        "pokaz.html", {"request": request, "chat_id": chat_id, "xgid": xgid}
    )


@app.get("/pokaz/hints")
async def get_pokaz_hints(xgid: str, chat_id: Optional[int] = None):
    """
    Возвращает подсказки для заданной позиции XGID.
    Проверяет баланс пользователя и списывает при успешной обработке.
    """
    try:
        logger.info(f"Получен запрос /pokaz/hints с параметрами: xgid={xgid}, chat_id={chat_id}")
        
        # Проверяем наличие chat_id
        if chat_id is None:
            logger.warning("Запрос без chat_id")
            raise HTTPException(status_code=400, detail="Параметр chat_id обязателен")
        
        # Создаем сессию БД
        async with async_session_maker() as session:
            user_dao = UserDAO(session)
            
            # Получаем баланс пользователя для сервиса POKAZ
            balance = await user_dao.get_total_analiz_balance(chat_id, ServiceType.POKAZ)
            
            # Проверяем баланс (None означает безлимитный)
            if balance is not None and balance < 1:
                logger.warning(f"Недостаточно баланса для пользователя {chat_id}. Баланс: {balance}")
                raise HTTPException(status_code=402, detail="Недостаточно баланса")
            
            # Получаем подсказки
            hints = get_hints_for_xgid(xgid)
            logger.info(f"Hints для пользователя {chat_id}: {hints}")
            
            # Списываем баланс только если массив hints не пустой
            if hints and len(hints) > 0:
                success = await user_dao.decrease_analiz_balance(
                    user_id=chat_id, 
                    service_type=ServiceType.POKAZ.name
                )
                if success:
                    await session.commit()
                    logger.info(f"Баланс успешно списан для пользователя {chat_id}")
                else:
                    logger.warning(f"Не удалось списать баланс для пользователя {chat_id}")
            else:
                logger.info(f"Hints пустой, баланс не списан для пользователя {chat_id}")
            
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
                    status_code=402, detail="Недостаточно баланса для отправки комментария"
                )

            # Читаем файл и отправляем в саппорт
            photo_bytes = await photo.read()
            photo_file = BufferedInputFile(photo_bytes, filename="admin_comment_screenshot.png")
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


flask_app, _ = create_app()
app.mount("/admin", WSGIMiddleware(flask_app))
