import secrets

from aiogram import Router, F
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    WebAppInfo,
)
from aiogram.fsm.context import FSMContext
from aiogram.filters import CommandObject, CommandStart
from sqlalchemy.ext.asyncio import AsyncSession
from bot.common.kbds.markup.main_kb import MainKeyboard
from bot.db.dao import (
    ContentCardActivationLinkDAO,
    ContentCardFolderDAO,
    ContentCardFolderLinkDAO,
    MessageForNewDAO,
    MessagesTextsDAO,
    UserDAO,
)
from bot.db.models import ContentCardActivationLinkStatus, User
from bot.db.schemas import SUser
from bot.config import settings, translator_hub
from html import escape
from typing import TYPE_CHECKING
from urllib.parse import quote
from fluentogram import TranslatorRunner
from bot.common.kbds.inline.activate_promo import (
    get_activate_promo_without_link_keyboard,
)
from bot.common.service.hint_s3_service import HintS3Storage
from bot.db.redis import redis_client
from bot.routers.support_reply_router import (
    FOLDER_REPLY_START_PREFIX,
    build_folder_admin_reply_markup,
    handle_folder_reply_deeplink,
    save_folder_admin_reply_context,
)
from loguru import logger

if TYPE_CHECKING:
    from locales.stub import TranslatorRunner

start_router = Router()
CARD_LINK_START_PREFIX = "cardlink_"
CARD_LINK_ACTIVATE_PREFIX = "activate_card_link:"
GALLERY_IMG_START_PREFIX = "imglink_"
GALLERY_IMG_REDIS_PREFIX = "cabinet_gallery_img_share:"
FOLDER_LINK_START_PREFIX = "folderlink_"


def _is_cards_cabinet_deeplink(start_payload: str | None) -> bool:
    """Deep-link из кабинета карточек: только ответ по ссылке, без приветствия /start."""
    payload = str(start_payload or "").strip()
    if not payload:
        return False
    return (
        payload.startswith(CARD_LINK_START_PREFIX)
        or payload.startswith(FOLDER_LINK_START_PREFIX)
        or payload.startswith(GALLERY_IMG_START_PREFIX)
    )


def _extract_gallery_img_share_token(start_payload: str | None) -> str | None:
    payload = str(start_payload or "").strip()
    if not payload.startswith(GALLERY_IMG_START_PREFIX):
        return None
    token = payload[len(GALLERY_IMG_START_PREFIX) :].strip()
    return token or None


async def _send_gallery_image_from_start_if_needed(
    message: Message,
    start_payload: str | None,
) -> None:
    token = _extract_gallery_img_share_token(start_payload)
    if not token:
        return
    redis_key = f"{GALLERY_IMG_REDIS_PREFIX}{token}"
    s3_key_raw = await redis_client.get(redis_key)
    if not s3_key_raw:
        await message.answer("Ссылка недействительна или срок её действия истёк.")
        return
    s3_key = str(s3_key_raw).strip()
    if not HintS3Storage.is_cabinet_gallery_media_key(s3_key):
        await redis_client.delete(redis_key)
        return
    s3 = HintS3Storage.from_settings()
    if not s3.exists(s3_key):
        await redis_client.delete(redis_key)
        await message.answer("Изображение больше не найдено.")
        return
    try:
        blob = s3.download_bytes(s3_key)
    except Exception as e:
        logger.warning("cabinet gallery share S3 read failed: {}", e)
        await message.answer("Не удалось загрузить изображение.")
        return
    fname = s3_key.rsplit("/", 1)[-1] or "image.jpg"
    photo = BufferedInputFile(blob, filename=fname)
    try:
        await message.answer_photo(photo)
    except Exception as e:
        logger.warning("cabinet gallery share send_photo failed: {}", e)
        await message.answer("Не удалось отправить изображение в Telegram.")


def _extract_card_link_token(start_payload: str | None) -> str | None:
    payload = str(start_payload or "").strip()
    if not payload.startswith(CARD_LINK_START_PREFIX):
        return None
    token = payload[len(CARD_LINK_START_PREFIX) :].strip()
    return token or None


def _cards_cabinet_webapp_markup() -> InlineKeyboardMarkup:
    cabinet_url = f"{settings.MINI_APP_URL.rstrip('/')}/cards-cabinet"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Открыть кабинет",
                    web_app=WebAppInfo(url=cabinet_url),
                )
            ]
        ]
    )


def _confirm_link_activation_markup(link_token: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Активировать",
                    callback_data=f"{CARD_LINK_ACTIVATE_PREFIX}{link_token}",
                )
            ]
        ]
    )


def _normalize_card_ids(card_ids: list[int] | None) -> list[int]:
    seen: set[int] = set()
    normalized: list[int] = []
    for raw_id in card_ids or []:
        try:
            card_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        if card_id < 1 or card_id in seen:
            continue
        seen.add(card_id)
        normalized.append(card_id)
    return normalized


def _extract_folder_link_token(start_payload: str | None) -> str | None:
    payload = str(start_payload or "").strip()
    if not payload.startswith(FOLDER_LINK_START_PREFIX):
        return None
    token = payload[len(FOLDER_LINK_START_PREFIX) :].strip()
    return token or None


def _folder_cabinet_webapp_markup(folder_token: str) -> InlineKeyboardMarkup:
    cabinet_url = (
        f"{settings.MINI_APP_URL.rstrip('/')}/cards-cabinet"
        f"?folder_token={quote(folder_token, safe='')}"
    )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Открыть папку",
                    web_app=WebAppInfo(url=cabinet_url),
                )
            ]
        ]
    )


async def _notify_admins_folder_link_opened(
    message: Message,
    *,
    folder_link,
    folder,
    cards_count: int,
) -> None:
    user = message.from_user
    if not user or not message.bot:
        return
    user_ref = (
        f"@{user.username}" if user.username else f"tg://user?id={user.id}"
    )
    folder_name = escape(str(folder.name or ""))
    notify_text = (
        "<b>Активирована ссылка на папку кабинета</b>\n"
        f"Пользователь: {escape(user.first_name or '')} ({user_ref})\n"
        f"ID пользователя: {user.id}\n"
        f"Папка: «{folder_name}» (id={folder.id})\n"
        f"ID ссылки: {folder_link.id}\n"
        f"Карточек в папке: {cards_count}"
    )
    try:
        sent = await message.bot.send_message(
            settings.CHAT_GROUP_ID,
            notify_text,
            parse_mode="HTML",
        )
        reply_token = secrets.token_urlsafe(12)
        await save_folder_admin_reply_context(
            reply_token,
            {
                "target_user_id": user.id,
                "source_chat_id": settings.CHAT_GROUP_ID,
                "source_message_id": sent.message_id,
                "source_text": notify_text,
            },
        )
        bot_info = await message.bot.get_me()
        await message.bot.edit_message_reply_markup(
            chat_id=settings.CHAT_GROUP_ID,
            message_id=sent.message_id,
            reply_markup=build_folder_admin_reply_markup(
                reply_token,
                bot_info.username or "",
            ),
        )
    except Exception as e:
        logger.warning("folder link admin notify failed: {}", e)


async def _send_folder_link_prompt_if_needed(
    message: Message,
    session: AsyncSession,
    start_payload: str | None,
) -> None:
    link_token = _extract_folder_link_token(start_payload)
    if not link_token:
        return

    link_dao = ContentCardFolderLinkDAO(session)
    folder_link = await link_dao.find_by_token(link_token)
    if not folder_link:
        await message.answer("Ссылка на папку недействительна или не найдена.")
        return

    folder_dao = ContentCardFolderDAO(session)
    folder = await folder_dao.get_folder_by_id(folder_link.folder_id)
    if not folder:
        await message.answer("Папка по ссылке не найдена.")
        return

    card_ids = await folder_dao.get_folder_card_ids(folder_link.folder_id)
    cards_count = len(card_ids)
    if cards_count < 1:
        text = f"Вам доступна папка «{folder.name}»."
    else:
        text = f"Вам доступна папка «{folder.name}». Карточек: {cards_count}."
    await message.answer(
        text,
        reply_markup=_folder_cabinet_webapp_markup(link_token),
    )
    await _notify_admins_folder_link_opened(
        message,
        folder_link=folder_link,
        folder=folder,
        cards_count=cards_count,
    )


async def _send_card_link_prompt_if_needed(
    message: Message,
    session: AsyncSession,
    start_payload: str | None,
) -> None:
    link_token = _extract_card_link_token(start_payload)
    if not link_token:
        return

    link_dao = ContentCardActivationLinkDAO(session)
    activation_link = await link_dao.find_one_by_link(link_token)
    if not activation_link:
        await message.answer("Ссылка недействительна или не найдена.")
        return
    if activation_link.status == ContentCardActivationLinkStatus.ACTIVATE:
        await message.answer("Эта ссылка уже активирована.")
        return

    cards_count = len(_normalize_card_ids(activation_link.card_ids))
    if cards_count < 1:
        await message.answer("В ссылке нет доступных карточек для активации.")
        return

    await message.answer(
        f"Хотите активировать карточки по ссылке? Доступно карточек: {cards_count}.",
        reply_markup=_confirm_link_activation_markup(link_token),
    )


async def _ensure_user_on_start(
    message: Message,
    session: AsyncSession,
) -> User:
    """Регистрация / обновление пользователя без приветственного сообщения."""
    user_data = message.from_user
    user_id = user_data.id
    user_dao = UserDAO(session)
    user_info = await user_dao.find_one_or_none_by_id(user_id)
    if (
        user_info
        and user_data.id in settings.ROOT_ADMIN_IDS
        and user_info.role != User.Role.ADMIN.value
    ):
        user_info.role = User.Role.ADMIN.value
        await user_dao.update(user_info.id, SUser.model_validate(user_info.to_dict()))
        return user_info
    if user_info is None:
        role = User.Role.USER.value
        if user_data.id in settings.ROOT_ADMIN_IDS:
            role = User.Role.ADMIN.value
        user_schema = SUser(
            id=user_id,
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            username=user_data.username,
            role=role,
        )
        return await user_dao.add(user_schema)
    return user_info


async def _handle_cards_cabinet_deeplink_start(
    message: Message,
    session: AsyncSession,
    start_payload: str,
) -> None:
    await _ensure_user_on_start(message, session)
    await _send_card_link_prompt_if_needed(message, session, start_payload)
    await _send_folder_link_prompt_if_needed(message, session, start_payload)
    await _send_gallery_image_from_start_if_needed(message, start_payload)


@start_router.message(CommandStart())
async def start_command(
    message: Message,
    state: FSMContext,
    session_with_commit: AsyncSession,
    command: CommandObject | None = None,
):
    user_data = message.from_user
    user_id = user_data.id
    start_payload = (command.args if command else "") or ""

    if start_payload.startswith(FOLDER_REPLY_START_PREFIX):
        if await handle_folder_reply_deeplink(message, start_payload):
            await state.clear()
            return

    if _is_cards_cabinet_deeplink(start_payload):
        await _handle_cards_cabinet_deeplink_start(
            message, session_with_commit, start_payload
        )
        await state.clear()
        return

    message_dao = MessagesTextsDAO(session_with_commit)
    user_info: User = await UserDAO(session_with_commit).find_one_or_none_by_id(user_id)
    if (
        user_info
        and user_data.id in settings.ROOT_ADMIN_IDS
        and user_info.role != User.Role.ADMIN.value
    ):
        user_info.role = User.Role.ADMIN.value
        await UserDAO(session_with_commit).update(
            user_info.id, SUser.model_validate(user_info.to_dict())
        )
        i18n: TranslatorRunner = translator_hub.get_translator_by_locale(
            user_info.lang_code if user_info.lang_code else "en"
        )
        await message.answer(
            await message_dao.get_text(
                "start", user_info.lang_code if user_info.lang_code else "en"
            ),
            reply_markup=MainKeyboard.build(user_info.role, i18n),
        )
        await state.clear()
        return
    if user_info is None:
        role = User.Role.USER.value
        if user_data.id in settings.ROOT_ADMIN_IDS:
            role = User.Role.ADMIN.value
        user_schema = SUser(
            id=user_id,
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            username=user_data.username,
            role=role,
        )

        user_info = await UserDAO(session_with_commit).add(user_schema)
        i18n: TranslatorRunner = translator_hub.get_translator_by_locale(
            user_info.lang_code if user_info.lang_code else "en"
        )
        message_for_new = await MessageForNewDAO(session_with_commit).get_by_lang_code(
            user_info.lang_code
        )
        await message.answer(
            await message_dao.get_text(
                "start", user_info.lang_code if user_info.lang_code else "en"
            ),
            reply_markup=MainKeyboard.build(user_info.role, i18n),
        )
        if message_for_new:
            await message.answer(
                message_for_new.text,
                reply_markup=get_activate_promo_without_link_keyboard(i18n),
            )
        await state.clear()
        return
    i18n: TranslatorRunner = translator_hub.get_translator_by_locale(
        user_info.lang_code if user_info.lang_code else "en"
    )
    await message.answer(
        await message_dao.get_text(
            "start", user_info.lang_code if user_info.lang_code else "en"
        ),
        reply_markup=MainKeyboard.build(user_info.role, i18n),
    )
    await state.clear()


@start_router.callback_query(F.data.startswith(CARD_LINK_ACTIVATE_PREFIX))
async def activate_cards_from_link(
    callback: CallbackQuery,
    session_with_commit: AsyncSession,
):
    data = str(callback.data or "")
    link_token = data[len(CARD_LINK_ACTIVATE_PREFIX) :].strip()
    if not link_token:
        await callback.answer("Некорректная ссылка", show_alert=True)
        return

    if not callback.from_user:
        await callback.answer("Не удалось определить пользователя", show_alert=True)
        return

    link_dao = ContentCardActivationLinkDAO(session_with_commit)
    result = await link_dao.activate_link_and_issue_cards(
        link_value=link_token,
        user_id=callback.from_user.id,
    )

    reason = str(result.get("reason") or "unknown")
    if int(result.get("ok") or 0) != 1:
        error_map = {
            "invalid_link": "Некорректная ссылка.",
            "not_found": "Ссылка не найдена.",
            "already_activated": "Эта ссылка уже активирована.",
            "user_not_found": "Пользователь не найден.",
            "no_cards": "В ссылке нет карточек для активации.",
            "cards_not_found": "Карточки по ссылке не найдены.",
        }
        text = error_map.get(reason, "Не удалось активировать карточки.")
        if callback.message:
            await callback.message.edit_text(text)
        await callback.answer()
        return

    await session_with_commit.commit()

    issued_count = int(result.get("issued_count") or 0)
    total_count = int(result.get("total_count") or 0)
    link_id = int(result.get("link_id") or 0)
    if callback.message:
        await callback.message.edit_text(
            f"Вам доступны {total_count} карточек, посмотреть их можете в кабинете",
            reply_markup=_cards_cabinet_webapp_markup(),
        )

    user_ref = (
        f"@{callback.from_user.username}"
        if callback.from_user.username
        else f"tg://user?id={callback.from_user.id}"
    )
    try:
        await callback.bot.send_message(
            settings.CHAT_GROUP_ID,
            (
                "<b>Активирована ссылка на карточки</b>\n"
                f"Пользователь: {callback.from_user.first_name} ({user_ref})\n"
                f"ID ссылки: {link_id}\n"
                f"Всего карточек в ссылке: {total_count}\n"
                f"Новых добавлено: {issued_count}"
            ),
            parse_mode="HTML",
        )
    except Exception:
        # Не блокируем пользовательский flow, если уведомление в группу не ушло.
        pass

    await callback.answer("Карточки активированы")
