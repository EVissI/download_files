import asyncio
from datetime import timezone
from zoneinfo import ZoneInfo

from flask import flash, redirect, url_for
from flask_appbuilder import ModelView, expose, has_access, permission_name
from flask_appbuilder.models.sqla.interface import SQLAInterface
from flask_babel import lazy_gettext as _
from flask_wtf.csrf import generate_csrf
from loguru import logger
from wtforms import BooleanField, DateTimeLocalField, IntegerField, StringField
from wtforms.validators import DataRequired, NumberRange, Optional

from bot.common.service.telegram_proxy_service import mask_proxy_url, send_proxy_test_message
from bot.common.telegram_proxy_config import clear_telegram_proxy_cache, get_effective_telegram_proxies
from bot.config import admins, format_telegram_api_error
from bot.db.models import TelegramProxy

MSK = ZoneInfo("Europe/Moscow")


def _run_telegram_sync(action):
    async def _runner() -> None:
        await action()

    asyncio.run(_runner())


class TelegramProxyModelView(ModelView):
    datamodel = SQLAInterface(TelegramProxy)
    show_template = "show_telegram_proxy.html"

    list_title = _("Прокси Telegram")
    add_title = _("Добавить прокси")
    edit_title = _("Редактировать прокси")
    show_title = _("Просмотр прокси")

    list_columns = [
        "name",
        "status_display",
        "priority",
        "expires_at_display",
        "is_active",
        "url",
    ]
    show_columns = [
        "id",
        "name",
        "url",
        "is_active",
        "priority",
        "expires_at",
        "expiry_warning_sent_at",
        "status_display",
        "created_at",
        "updated_at",
    ]
    add_columns = edit_columns = [
        "name",
        "url",
        "is_active",
        "priority",
        "expires_at",
    ]

    label_columns = {
        "id": _("ID"),
        "name": _("Название"),
        "url": _("URL прокси"),
        "is_active": _("Активен"),
        "priority": _("Приоритет"),
        "expires_at": _("Дата окончания"),
        "expires_at_display": _("Окончание"),
        "expiry_warning_sent_at": _("Предупреждение отправлено"),
        "status_display": _("Статус"),
        "created_at": _("Создано"),
        "updated_at": _("Обновлено"),
    }

    base_order = ("priority", "asc")

    description_columns = {
        "url": _(
            "Формат: http://user:pass@host:8080 или socks5://user:pass@host:1080"
        ),
        "priority": _("Меньшее число = выше приоритет при failover"),
        "expires_at": _("За 2 суток до этой даты админам придёт уведомление в Telegram"),
    }

    add_form_extra_fields = edit_form_extra_fields = {
        "name": StringField(_("Название"), validators=[DataRequired()]),
        "url": StringField(_("URL прокси"), validators=[DataRequired()]),
        "is_active": BooleanField(_("Активен"), default=True),
        "priority": IntegerField(
            _("Приоритет"),
            validators=[DataRequired(), NumberRange(min=0, max=100000)],
            default=100,
        ),
        "expires_at": DateTimeLocalField(
            _("Дата окончания"),
            validators=[Optional()],
            format="%Y-%m-%dT%H:%M",
        ),
    }

    def render_template(self, template, **kwargs):
        kwargs.setdefault("tp_fab_endpoint", getattr(self, "endpoint", self.__class__.__name__))
        kwargs.setdefault("csrf_token_value", generate_csrf())
        return super().render_template(template, **kwargs)

    @expose("/test_proxy/<int:pk>", methods=["POST"])
    @has_access
    @permission_name("show")
    def test_proxy(self, pk: int):
        item = self.datamodel.get(pk)
        if not item:
            flash(_("Прокси не найден"), "danger")
            return redirect(url_for(f"{self.endpoint}.list"))

        proxy_url = str(item.url or "").strip()
        if not proxy_url:
            flash(_("У прокси не задан URL"), "warning")
            return redirect(url_for(f"{self.endpoint}.show", pk=str(pk)))

        if not admins:
            flash(_("ROOT_ADMIN_IDS пуст — некому отправить тест"), "warning")
            return redirect(url_for(f"{self.endpoint}.show", pk=str(pk)))

        async def _send() -> int:
            return await send_proxy_test_message(
                proxy_url=proxy_url,
                proxy_name=item.name,
                chat_ids=admins,
            )

        try:
            sent_count = _run_telegram_sync(_send)
            flash(
                _(
                    "Тестовое сообщение через прокси «%(name)s» отправлено "
                    "(%(count)s из %(total)s админов). URL: %(url)s"
                )
                % {
                    "name": item.name,
                    "count": sent_count,
                    "total": len(admins),
                    "url": mask_proxy_url(proxy_url),
                },
                "success",
            )
        except Exception as exc:
            logger.exception("test_proxy id={}: {}", pk, exc)
            flash(
                f"Прокси «{item.name}» не сработал: {format_telegram_api_error(exc)}",
                "danger",
            )

        return redirect(url_for(f"{self.endpoint}.show", pk=str(pk)))

    def pre_add(self, item):
        self._normalize_item(item)

    def pre_update(self, item):
        old = self.datamodel.get(item.id)
        old_expires = old.expires_at if old else None
        self._normalize_item(item)
        if item.expires_at != old_expires:
            item.expiry_warning_sent_at = None

    def _normalize_item(self, item: TelegramProxy) -> None:
        item.name = str(item.name or "").strip()
        item.url = str(item.url or "").strip()
        if item.expires_at is not None:
            expires_at = item.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=MSK)
            item.expires_at = expires_at.astimezone(timezone.utc)

    def post_add(self, item):
        self._after_change(item, created=True)

    def post_update(self, item):
        self._after_change(item, created=False)

    def post_delete(self, item):
        clear_telegram_proxy_cache()
        flash(_("Кэш прокси сброшен"), "info")

    def _after_change(self, item: TelegramProxy, *, created: bool) -> None:
        clear_telegram_proxy_cache()
        urls = get_effective_telegram_proxies(refresh=True)
        action = _("добавлен") if created else _("обновлён")
        flash(
            f"Прокси «{item.name}» {action}. Активных URL: {len(urls)}",
            "success",
        )
        if urls:
            flash(f"Первый в очереди: {mask_proxy_url(urls[0])}", "info")
