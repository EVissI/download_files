import asyncio
import os
import re

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.types import BufferedInputFile, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder
from flask import flash, redirect, url_for
from flask_appbuilder import ModelView, expose, has_access, permission_name
from flask_appbuilder.models.filters import BaseFilter
from flask_appbuilder.models.sqla.filters import SQLAFilterConverter, get_field_setup_query
from flask_appbuilder.models.sqla.interface import SQLAInterface
from flask_babel import lazy_gettext as _
from loguru import logger
from sqlalchemy import func
from wtforms import StringField, validators

from bot.common.service.hint_s3_service import HintS3Storage
from bot.config import SUPPORT_TG_ID, create_bot_for_sync_context, settings
from bot.db.models import ContentCard

# Разделитель для array_to_string: непечатный символ, чтобы не сливать реальные метки
_LABELS_JOIN_DELIM = "\x1f"


def _escape_ilike_pattern(s: str) -> str:
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _run_telegram_sync(action):
    """
    Flask/Starlette WSGI в отдельном потоке: нельзя использовать глобальный bot из config —
    его aiohttp-сессия привязана к другому (уже закрытому) event loop.
    На каждый вызов — свой Bot, asyncio.run() и явное закрытие сессии.
    action: async (Bot) -> None
    """

    async def _runner() -> None:
        tg_bot = create_bot_for_sync_context()
        try:
            await action(tg_bot)
        finally:
            await tg_bot.session.close()

    asyncio.run(_runner())


def _content_card_view_webapp_markup(view_url: str):
    """Как в api.py: кнопка Web App для открытия карточки в Telegram."""
    kb = InlineKeyboardBuilder()
    kb.button(text="Открыть карточку", web_app=WebAppInfo(url=view_url))
    kb.adjust(1)
    return kb.as_markup()


class FilterLabelsSubstring(BaseFilter):
    """Подстрока в любой из меток (без учёта регистра)."""

    name = _("Подстрока в метке")
    arg_name = "lbl_ct"

    def apply(self, query, value):
        if not value or not str(value).strip():
            return query
        query, field = get_field_setup_query(query, self.model, self.column_name)
        sub = str(value).strip()
        joined = func.array_to_string(field, _LABELS_JOIN_DELIM)
        pat = f"%{_escape_ilike_pattern(sub)}%"
        return query.filter(joined.ilike(pat, escape="\\"))


class FilterLabelsExact(BaseFilter):
    """Метка в массиве целиком (совпадение одного элемента)."""

    name = _("Точная метка")
    arg_name = "lbl_eq"

    def apply(self, query, value):
        if not value or not str(value).strip():
            return query
        query, field = get_field_setup_query(query, self.model, self.column_name)
        sub = str(value).strip()
        return query.filter(field.contains([sub]))


class ContentCardSQLAFilterConverter(SQLAFilterConverter):
    """Добавляет фильтры для PostgreSQL ARRAY (метки) до стандартных типов."""

    conversion_table = (
        (
            "is_content_card_labels_array",
            [
                FilterLabelsSubstring,
                FilterLabelsExact,
            ],
        ),
    ) + SQLAFilterConverter.conversion_table


class ContentCardSQLAInterface(SQLAInterface):
    filter_converter_class = ContentCardSQLAFilterConverter

    def is_content_card_labels_array(self, col_name: str) -> bool:
        return col_name == "labels"


class ContentCardModelView(ModelView):
    """Карточки редактора контента — только просмотр и список."""

    datamodel = ContentCardSQLAInterface(ContentCard)
    base_permissions = ["can_list", "can_show", "can_delete"]

    list_title = _("Карточки")
    show_title = _("Карточка")

    show_template = "show_content_card.html"

    page_size = 30
    list_columns = ["id", "file_name", "notes", "labels"]
    show_columns = ["id", "file_name", "notes", "labels"]
    search_columns = ["id", "file_name", "notes", "labels"]
    order_columns = ["id", "file_name"]

    # ARRAY не конвертируется в поле поиска автоматически — явное поле, иначе KeyError в SearchWidget
    search_form_extra_fields = {
        "labels": StringField(
            _("Метки"),
            description=_(
                "Массив PostgreSQL TEXT[]. «Подстрока в метке» — вхождение в любую метку; "
                "«Точная метка» — элемент массива целиком."
            ),
            validators=[validators.Optional()],
        ),
    }

    label_columns = {
        "id": _("ID"),
        "file_name": _("Имя файла"),
        "notes": _("Примечания"),
        "labels": _("Метки"),
    }

    description_columns = {
        "labels": _(
            "Массив меток в PostgreSQL. «Подстрока в метке» — вхождение в любую метку; "
            "«Точная метка» — элемент массива равен введённой строке."
        ),
    }

    def render_template(self, template, **kwargs):
        kwargs.setdefault("cc_fab_endpoint", getattr(self, "endpoint", self.__class__.__name__))
        return super().render_template(template, **kwargs)

    @expose("/send_card_to_support/<int:pk>")
    @has_access
    @permission_name("show")
    def send_card_to_support(self, pk: int):
        """Отправить в SUPPORT_TG_ID сообщение со ссылкой на Web App карточки (как notify после save в api.py)."""
        item = self.datamodel.get(pk)
        if not item:
            flash(_("Карточка не найдена"), "danger")
            return redirect(url_for(f"{self.endpoint}.list"))
        view_url = (
            f"{settings.MINI_APP_URL.rstrip('/')}/content-card-view?content_card_id={pk}"
        )
        text = f"Карточка (id={pk}, файл: {item.file_name})."

        async def _send(tg_bot: Bot) -> None:
            await tg_bot.send_message(
                chat_id=SUPPORT_TG_ID,
                text=text,
                reply_markup=_content_card_view_webapp_markup(view_url),
            )

        try:
            _run_telegram_sync(_send)
            flash(_("Ссылка на карточку отправлена в чат"), "success")
        except Exception as e:
            logger.exception("send_card_to_support: {}", e)
            flash(f"Ошибка отправки в Telegram: {e}", "danger")

        return redirect(url_for(f"{self.endpoint}.show", pk=str(pk)))

    @expose("/send_mat_to_support/<int:pk>")
    @has_access
    @permission_name("show")
    def send_mat_to_support(self, pk: int):
        """
        По file_name карточки (формат {game_id}.mat) взять hints/{game_id}.mat из S3 и отправить документ в SUPPORT_TG_ID.
        Логика согласована с POST /api/content_cards/hint_mat_download.
        """
        item = self.datamodel.get(pk)
        if not item:
            flash(_("Карточка не найдена"), "danger")
            return redirect(url_for(f"{self.endpoint}.list"))

        fname = os.path.basename((item.file_name or "").strip())[:255]
        if not fname:
            flash(_("У карточки не задано имя файла."), "warning")
            return redirect(url_for(f"{self.endpoint}.show", pk=str(pk)))

        stem, _dot, ext = fname.rpartition(".")
        if ext.lower() != "mat" or not stem:
            flash(
                _(
                    "Исходный файл в S3 ожидается как имя вида {game_id}.mat (как в hint viewer)."
                ),
                "warning",
            )
            return redirect(url_for(f"{self.endpoint}.show", pk=str(pk)))

        game_id = stem
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,220}", game_id):
            flash(_("Некорректный game_id в имени файла."), "danger")
            return redirect(url_for(f"{self.endpoint}.show", pk=str(pk)))

        key = HintS3Storage.mat_key(game_id)
        s3 = HintS3Storage.from_settings()
        if not s3.exists(key):
            flash(_("Файл .mat не найден в хранилище S3."), "warning")
            return redirect(url_for(f"{self.endpoint}.show", pk=str(pk)))

        try:
            blob = s3.download_bytes(key)
        except Exception as e:
            logger.exception("send_mat_to_support S3: {}", e)
            flash(f"Ошибка чтения из S3: {e}", "danger")
            return redirect(url_for(f"{self.endpoint}.show", pk=str(pk)))

        caption = f"Исходный .mat карточки id={pk}, game_id={game_id}"

        async def _send(tg_bot: Bot) -> None:
            await tg_bot.send_document(
                chat_id=SUPPORT_TG_ID,
                document=BufferedInputFile(blob, filename=fname),
                caption=caption,
            )

        try:
            _run_telegram_sync(_send)
            flash(_("Файл .mat отправлен в чат."), "success")
        except Exception as e:
            logger.exception("send_mat_to_support Telegram: {}", e)
            flash(f"Ошибка отправки в Telegram: {e}", "danger")

        return redirect(url_for(f"{self.endpoint}.show", pk=str(pk)))
