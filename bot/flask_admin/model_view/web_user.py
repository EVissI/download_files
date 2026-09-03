from datetime import timezone
from zoneinfo import ZoneInfo

from flask import flash, redirect, request, url_for
from flask_appbuilder import ModelView, expose, has_access, permission_name
from flask_appbuilder.models.sqla.interface import SQLAInterface
from flask_wtf.csrf import generate_csrf
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from wtforms import BooleanField, DateTimeLocalField, IntegerField, PasswordField
from wtforms.validators import DataRequired, Length, NumberRange, Optional

from bot.common.service.web_grant_user import ensure_web_grant_user_sync, web_grant_user_id
from bot.common.utils.password import store_password
from bot.db.models import ContentCard, ContentCardPool, MatchAnalysis, UserMatchAnalysis, WebUser
from bot.flask_admin.content_card_grant import grant_content_cards_from_pool_sync
from bot.flask_admin.match_analysis_grant import grant_match_analyses_sync

try:
    from flask_appbuilder.fieldwidgets import BS3PasswordFieldWidget
except ImportError:  # pragma: no cover
    BS3PasswordFieldWidget = None

MSK = ZoneInfo("Europe/Moscow")


def _password_field(label: str, required: bool) -> PasswordField:
    validators = [Length(min=6, max=128)]
    validators.insert(0, DataRequired() if required else Optional())
    kwargs = {"validators": validators}
    if BS3PasswordFieldWidget is not None:
        kwargs["widget"] = BS3PasswordFieldWidget()
    return PasswordField(label, **kwargs)


def _unlimited_checked() -> bool:
    return request.form.get("unlimited") in ("y", "on", "1", "true", "True")


def _is_admin_checked() -> bool:
    return request.form.get("is_admin") in ("y", "on", "1", "true", "True")


class WebUserModelView(ModelView):
    datamodel = SQLAInterface(WebUser)

    list_title = "Веб-пользователи"
    show_title = "Веб-пользователь"
    add_title = "Создать веб-пользователя"
    edit_title = "Изменить веб-пользователя"
    show_template = "show_web_user.html"

    list_columns = [
        "id",
        "login",
        "is_admin",
        "account_status",
        "expires_at_display",
        "max_sessions",
        "password_masked",
    ]
    show_columns = [
        "id",
        "login",
        "is_admin",
        "account_status",
        "expires_at_display",
        "max_sessions",
        "password_display",
    ]
    add_columns = ["login", "password", "is_admin", "unlimited", "expires_at", "max_sessions"]
    edit_columns = ["login", "password", "is_admin", "unlimited", "expires_at", "max_sessions"]
    search_columns = ["login"]
    exclude_columns = ["password_hash", "password_encrypted", "uploads", "support_thread"]

    label_columns = {
        "id": "ID",
        "login": "Логин",
        "password": "Пароль",
        "is_admin": "Админ",
        "unlimited": "Бессрочный",
        "expires_at": "Активен до",
        "expires_at_display": "Активен до",
        "account_status": "Статус",
        "password_masked": "Пароль",
        "password_display": "Пароль",
        "max_sessions": "Одновременных сессий",
    }
    description_columns = {
        "is_admin": "Админ?",
        "password": "Не короче 6 символов. При редактировании оставьте пустым, чтобы не менять.",
        "password_masked": "В списке пароль скрыт. Откройте карточку пользователя, чтобы увидеть исходный пароль.",
        "password_display": "Расшифрованная копия. Для входа используется отдельный хеш.",
        "unlimited": "Если отмечено, срок не ограничен и вход всегда разрешён.",
        "expires_at": "Московское время. После этой даты войти нельзя. Не нужно, если аккаунт бессрочный.",
        "max_sessions": (
            "Сколько браузеров/устройств могут быть в кабинете одновременно. "
            "Повторный вход с того же браузера не занимает новый слот. "
            "Если лимит уже занят, вход с нового устройства блокируется."
        ),
    }

    add_form_extra_fields = {
        "password": _password_field("Пароль", required=True),
        "is_admin": BooleanField(
            "Админ",
            default=False,
            false_values=(False, "false", "0", ""),
            render_kw={"required": False},
        ),
        "unlimited": BooleanField("Бессрочный", default=False),
        "expires_at": DateTimeLocalField(
            "Активен до",
            validators=[Optional()],
            format="%Y-%m-%dT%H:%M",
        ),
        "max_sessions": IntegerField(
            "Одновременных сессий",
            default=1,
            validators=[DataRequired(), NumberRange(min=1, max=99)],
        ),
    }
    edit_form_extra_fields = {
        "password": _password_field("Новый пароль (оставьте пустым, чтобы не менять)", required=False),
        "is_admin": BooleanField(
            "Админ",
            default=False,
            false_values=(False, "false", "0", ""),
            render_kw={"required": False},
        ),
        "unlimited": BooleanField("Бессрочный", default=False),
        "expires_at": DateTimeLocalField(
            "Активен до",
            validators=[Optional()],
            format="%Y-%m-%dT%H:%M",
        ),
        "max_sessions": IntegerField(
            "Одновременных сессий",
            validators=[DataRequired(), NumberRange(min=1, max=99)],
        ),
    }

    @staticmethod
    def _raw_password(item: WebUser) -> str:
        raw = getattr(item, "password", None)
        if not isinstance(raw, str) or not raw.strip():
            raw = request.form.get("password")
        return (raw or "").strip()

    @staticmethod
    def _drop_transient_password(item: WebUser) -> None:
        for name in ("password", "unlimited"):
            if hasattr(item, name):
                try:
                    delattr(item, name)
                except Exception:
                    pass

    def _apply_expiry(self, item: WebUser) -> None:
        if _unlimited_checked():
            item.expires_at = None
            return
        expires_at = item.expires_at
        if expires_at is None:
            flash("Укажите срок действия или отметьте «Бессрочный»", "danger")
            raise ValueError("expires_at required")
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=MSK)
        item.expires_at = expires_at.astimezone(timezone.utc)

    def prefill_form(self, form, pk):
        item = self.datamodel.get(pk)
        if item is None:
            return
        if getattr(form, "unlimited", None) is not None:
            form.unlimited.data = item.expires_at is None
        if getattr(form, "is_admin", None) is not None:
            form.is_admin.data = bool(item.is_admin)
        if item.expires_at is not None and getattr(form, "expires_at", None) is not None:
            local = item.expires_at
            if local.tzinfo is None:
                local = local.replace(tzinfo=timezone.utc)
            form.expires_at.data = local.astimezone(MSK).replace(tzinfo=None)

    def pre_add(self, item: WebUser) -> None:
        item.login = (item.login or request.form.get("login") or "").strip()
        if not item.login:
            flash("Логин обязателен", "danger")
            raise ValueError("login required")
        existing = (
            self.datamodel.session.query(WebUser)
            .filter(WebUser.login == item.login)
            .first()
        )
        if existing:
            flash("Такой логин уже занят", "danger")
            raise ValueError("duplicate login")
        raw = self._raw_password(item)
        if len(raw) < 6:
            flash("Пароль должен быть не короче 6 символов", "danger")
            raise ValueError("password too short")
        item.password_hash, item.password_encrypted = store_password(raw)
        item.is_admin = _is_admin_checked()
        item.max_sessions = WebUser.clamp_max_sessions(getattr(item, "max_sessions", 1))
        self._apply_expiry(item)
        self._drop_transient_password(item)

    def pre_update(self, item: WebUser) -> None:
        item.login = (item.login or request.form.get("login") or "").strip()
        if not item.login:
            flash("Логин обязателен", "danger")
            raise ValueError("login required")
        existing = (
            self.datamodel.session.query(WebUser)
            .filter(WebUser.login == item.login, WebUser.id != item.id)
            .first()
        )
        if existing:
            flash("Такой логин уже занят", "danger")
            raise ValueError("duplicate login")
        raw = self._raw_password(item)
        if raw:
            if len(raw) < 6:
                flash("Пароль должен быть не короче 6 символов", "danger")
                raise ValueError("password too short")
            item.password_hash, item.password_encrypted = store_password(raw)
        item.is_admin = _is_admin_checked()
        item.max_sessions = WebUser.clamp_max_sessions(getattr(item, "max_sessions", 1))
        self._apply_expiry(item)
        self._drop_transient_password(item)

    def post_add(self, item: WebUser) -> None:
        try:
            from bot.common.service.cabinet_admin import grant_all_cabinet_content_sync

            grant_id = ensure_web_grant_user_sync(
                self.datamodel.session, int(item.id), item.login
            )
            if item.is_admin:
                grant_all_cabinet_content_sync(
                    self.datamodel.session, grant_id, commit=False
                )
            self.datamodel.session.commit()
            from bot.common.service.hint_viewer_web_service import (
                invalidate_web_account_cache_sync,
            )

            invalidate_web_account_cache_sync(item.id)
        except Exception:
            self.datamodel.session.rollback()
            flash(
                "Пользователь создан, но теневой аккаунт для карточек не создан.",
                "warning",
            )

    def post_update(self, item: WebUser) -> None:
        try:
            from bot.common.service.cabinet_admin import grant_all_cabinet_content_sync

            grant_id = ensure_web_grant_user_sync(
                self.datamodel.session, int(item.id), item.login
            )
            if item.is_admin:
                grant_all_cabinet_content_sync(
                    self.datamodel.session, grant_id, commit=False
                )
            self.datamodel.session.commit()
        except Exception:
            self.datamodel.session.rollback()
        try:
            from bot.common.service.hint_viewer_web_service import (
                invalidate_web_account_cache_sync,
            )

            invalidate_web_account_cache_sync(item.id)
        except Exception:
            pass

    def render_template(self, template, **kwargs):
        kwargs.setdefault(
            "user_fab_endpoint", getattr(self, "endpoint", self.__class__.__name__)
        )
        kwargs.setdefault("csrf_token_value", generate_csrf())
        if template == self.show_template:
            current_pk = kwargs.get("pk")
            session = self.datamodel.session
            ma_count = 0
            ready_available = 0
            try:
                if current_pk is not None:
                    grant_id = web_grant_user_id(int(current_pk))
                    ma_count = int(
                        session.scalar(
                            select(func.count())
                            .select_from(UserMatchAnalysis)
                            .where(UserMatchAnalysis.user_id == grant_id)
                        )
                        or 0
                    )
                    owned = select(UserMatchAnalysis.match_analysis_id).where(
                        UserMatchAnalysis.user_id == grant_id
                    )
                    ready_available = int(
                        session.scalar(
                            select(func.count())
                            .select_from(MatchAnalysis)
                            .where(
                                MatchAnalysis.is_ready.is_(True),
                                MatchAnalysis.id.not_in(owned),
                            )
                        )
                        or 0
                    )
            except SQLAlchemyError:
                ma_count = 0
                ready_available = 0
            kwargs.setdefault("match_analyses_count", ma_count)
            kwargs.setdefault("match_analyses_ready_available", ready_available)
        return super().render_template(template, **kwargs)

    def _grant_user_id_or_redirect(self, pk: int):
        user = self.datamodel.get(pk)
        if not user:
            flash("Веб-пользователь не найден", "danger")
            return None, redirect(url_for(f"{self.endpoint}.list"))
        grant_id = ensure_web_grant_user_sync(
            self.datamodel.session, int(pk), user.login
        )
        return grant_id, None

    @expose("/grant_cards/<int:pk>", methods=["POST"])
    @has_access
    @permission_name("show")
    def grant_cards(self, pk: int):
        return self._grant_cards_for_pool(pk, ContentCardPool.CARDS)

    @expose("/grant_pip_count_cards/<int:pk>", methods=["POST"])
    @has_access
    @permission_name("show")
    def grant_pip_count_cards(self, pk: int):
        return self._grant_cards_for_pool(pk, ContentCardPool.PIP_COUNT)

    @expose("/grant_match_analyses/<int:pk>", methods=["POST"])
    @has_access
    @permission_name("show")
    def grant_match_analyses(self, pk: int):
        grant_id, err = self._grant_user_id_or_redirect(pk)
        if err is not None:
            return err

        raw_qty = (request.form.get("cards_quantity") or "").strip()
        try:
            quantity = int(raw_qty)
        except (TypeError, ValueError):
            quantity = 0

        if quantity <= 0:
            flash("Введите корректное количество анализов (целое число > 0).", "warning")
            return redirect(url_for(f"{self.endpoint}.show", pk=str(pk)))

        session = self.datamodel.session
        issued_count = 0
        try:
            issued_count = grant_match_analyses_sync(
                session, user_id=grant_id, quantity=quantity
            )
            if issued_count == 0:
                any_ready = session.execute(
                    select(MatchAnalysis.id)
                    .where(MatchAnalysis.is_ready.is_(True))
                    .limit(1)
                ).first()
                if not any_ready:
                    flash(
                        "Нет готовых к выдаче анализов матча (is_ready).",
                        "warning",
                    )
                else:
                    flash(
                        "У пользователя уже есть все доступные анализы матча.",
                        "warning",
                    )
                return redirect(url_for(f"{self.endpoint}.show", pk=str(pk)))
        except SQLAlchemyError as e:
            session.rollback()
            flash(f"Ошибка выдачи анализов матча: {e}", "danger")
            return redirect(url_for(f"{self.endpoint}.show", pk=str(pk)))

        if issued_count < quantity:
            flash(
                f"Выдано {issued_count} из {quantity}: больше доступных анализов нет.",
                "warning",
            )
        else:
            flash(f"Пользователю выдано {issued_count} анализов матча.", "success")

        return redirect(url_for(f"{self.endpoint}.show", pk=str(pk)))

    def _grant_cards_for_pool(self, pk: int, card_pool: ContentCardPool):
        grant_id, err = self._grant_user_id_or_redirect(pk)
        if err is not None:
            return err

        raw_qty = (request.form.get("cards_quantity") or "").strip()
        try:
            cards_quantity = int(raw_qty)
        except (TypeError, ValueError):
            cards_quantity = 0

        if cards_quantity <= 0:
            flash("Введите корректное количество карточек (целое число > 0).", "warning")
            return redirect(url_for(f"{self.endpoint}.show", pk=str(pk)))

        is_pip = card_pool == ContentCardPool.PIP_COUNT
        pool_label = "карточек (пипсы)" if is_pip else "карточек"
        empty_pool_msg = (
            "В системе нет карточек пула «Подсчёт пипсов» для выдачи."
            if is_pip
            else "В системе нет карточек для выдачи."
        )

        session = self.datamodel.session
        issued_count = 0
        try:
            issued_count = grant_content_cards_from_pool_sync(
                session,
                user_id=grant_id,
                quantity=cards_quantity,
                card_pool=card_pool,
            )
            if issued_count == 0:
                all_in_pool = session.execute(
                    select(ContentCard.id)
                    .where(ContentCard.card_pool == card_pool.value)
                    .limit(1)
                ).first()
                if not all_in_pool:
                    flash(empty_pool_msg, "warning")
                else:
                    flash(
                        "У пользователя уже есть все доступные карточки из этого пула.",
                        "warning",
                    )
                return redirect(url_for(f"{self.endpoint}.show", pk=str(pk)))
        except SQLAlchemyError as e:
            session.rollback()
            flash(f"Ошибка выдачи карточек: {e}", "danger")
            return redirect(url_for(f"{self.endpoint}.show", pk=str(pk)))

        if issued_count < cards_quantity:
            flash(
                f"Выдано {issued_count} из {cards_quantity}: больше доступных карточек в пуле нет.",
                "warning",
            )
        else:
            flash(f"Пользователю выдано {issued_count} {pool_label}.", "success")

        return redirect(url_for(f"{self.endpoint}.show", pk=str(pk)))
