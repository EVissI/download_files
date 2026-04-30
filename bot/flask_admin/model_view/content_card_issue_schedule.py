from zoneinfo import ZoneInfo

from flask import flash
from flask_appbuilder import ModelView
from flask_appbuilder.models.sqla.interface import SQLAInterface
from flask_babel import lazy_gettext as _
from loguru import logger
from wtforms import BooleanField, IntegerField, SelectMultipleField, StringField, widgets
from wtforms.validators import DataRequired, NumberRange, Regexp

from bot.common.tasks.card_issue_schedule import run_content_card_issue_schedule
from bot.config import scheduler
from bot.db.models import ContentCardIssueSchedule


WEEKDAY_CHOICES = [
    ("mon", "Понедельник"),
    ("tue", "Вторник"),
    ("wed", "Среда"),
    ("thu", "Четверг"),
    ("fri", "Пятница"),
    ("sat", "Суббота"),
    ("sun", "Воскресенье"),
]
WEEKDAY_ORDER = {day: idx for idx, (day, _title) in enumerate(WEEKDAY_CHOICES)}


class MultiCheckboxField(SelectMultipleField):
    widget = widgets.ListWidget(prefix_label=False)
    option_widget = widgets.CheckboxInput()


class ContentCardIssueScheduleModelView(ModelView):
    datamodel = SQLAInterface(ContentCardIssueSchedule)
    base_permissions = ["can_list", "can_show", "can_add", "can_edit", "can_delete"]
    page_size = 50

    list_title = _("Расписание выдачи карточек")
    add_title = _("Добавить расписание выдачи карточек")
    edit_title = _("Редактировать расписание выдачи карточек")
    show_title = _("Расписание выдачи карточек")

    list_columns = [
        "id",
        "target_user_id",
        "cards_per_run",
        "weekdays_display",
        "issue_time_msk",
        "is_active",
        "last_run_at",
    ]
    show_columns = [
        "id",
        "target_user_id",
        "cards_per_run",
        "weekdays_display",
        "issue_time_msk",
        "is_active",
        "scheduler_job_id",
        "last_run_at",
        "created_at",
        "updated_at",
    ]
    add_columns = ["target_user_id", "cards_per_run", "weekdays", "issue_time_msk", "is_active"]
    edit_columns = ["target_user_id", "cards_per_run", "weekdays", "issue_time_msk", "is_active"]
    search_columns = ["target_user_id", "issue_time_msk", "scheduler_job_id"]
    order_columns = ["id", "target_user_id", "issue_time_msk", "last_run_at", "is_active"]

    label_columns = {
        "id": _("ID"),
        "target_user_id": _("ID пользователя"),
        "cards_per_run": _("Карточек за запуск"),
        "weekdays": _("Дни недели"),
        "weekdays_display": _("Дни недели"),
        "issue_time_msk": _("Время (МСК)"),
        "is_active": _("Активно"),
        "scheduler_job_id": _("ID задачи APScheduler"),
        "last_run_at": _("Последний запуск"),
        "created_at": _("Создано"),
        "updated_at": _("Обновлено"),
    }

    description_columns = {
        "target_user_id": _("Пользователь, которому по расписанию выдаются карточки."),
        "cards_per_run": _("Сколько новых карточек выдать за один запуск."),
        "weekdays": _("Выберите дни недели запуска."),
        "issue_time_msk": _("Формат: ЧЧ:ММ (Europe/Moscow)."),
    }

    form_extra_fields = {
        "cards_per_run": IntegerField(
            _("Карточек за запуск"),
            validators=[DataRequired(), NumberRange(min=1, max=3000)],
            default=1,
        ),
        "weekdays": MultiCheckboxField(
            _("Дни недели"),
            choices=WEEKDAY_CHOICES,
            validators=[DataRequired()],
        ),
        "issue_time_msk": StringField(
            _("Время (МСК)"),
            validators=[
                DataRequired(),
                Regexp(r"^\d{2}:\d{2}$", message=_("Формат: ЧЧ:ММ")),
            ],
        ),
        "is_active": BooleanField(_("Активно"), default=True),
    }

    def post_add(self, item):
        self._upsert_scheduler_job(item)

    def post_update(self, item):
        self._upsert_scheduler_job(item)

    def post_delete(self, item):
        self._remove_scheduler_job(item)

    @staticmethod
    def _normalize_weekdays(raw_weekdays):
        allowed = set(WEEKDAY_ORDER.keys())
        out = []
        for day in raw_weekdays or []:
            day_text = str(day or "").strip().lower()
            if day_text not in allowed:
                continue
            out.append(day_text)
        if not out:
            raise ValueError("Нужно выбрать хотя бы один день недели.")
        out = sorted(set(out), key=lambda day: WEEKDAY_ORDER[day])
        return out

    @staticmethod
    def _validate_time(value: str):
        try:
            hour, minute = map(int, str(value).split(":"))
        except Exception as exc:
            raise ValueError("Некорректное время. Используйте формат ЧЧ:ММ.") from exc
        if hour < 0 or hour > 23 or minute < 0 or minute > 59:
            raise ValueError("Некорректное время. Используйте диапазон 00:00-23:59.")

    @staticmethod
    def _ensure_scheduler_started():
        if getattr(scheduler, "running", False):
            return
        scheduler.start()
        logger.info("APScheduler started from FAB for card issue schedules")

    def _upsert_scheduler_job(self, item: ContentCardIssueSchedule):
        session = self.datamodel.session
        try:
            self._ensure_scheduler_started()
            if not item.is_active:
                self._remove_scheduler_job(item, commit=False)
                item.scheduler_job_id = None
                session.commit()
                flash(_("Расписание сохранено как неактивное, задача отключена."), "info")
                return

            self._validate_time(item.issue_time_msk)
            weekdays = self._normalize_weekdays(item.weekdays)
            item.weekdays = weekdays
            hour, minute = map(int, item.issue_time_msk.split(":"))
            job_id = item.scheduler_job_id or f"content_card_issue_schedule:{item.id}"
            scheduler.add_job(
                run_content_card_issue_schedule,
                "cron",
                day_of_week=",".join(weekdays),
                hour=hour,
                minute=minute,
                timezone=ZoneInfo("Europe/Moscow"),
                id=job_id,
                replace_existing=True,
                args=[item.id],
                coalesce=True,
                max_instances=1,
                misfire_grace_time=3600,
            )
            item.scheduler_job_id = job_id
            session.commit()
            flash(_("Задача APScheduler создана/обновлена."), "success")
        except ValueError as exc:
            session.rollback()
            flash(str(exc), "warning")
        except Exception as exc:
            session.rollback()
            logger.exception("Failed to upsert card issue schedule job: {}", exc)
            flash(
                _("Расписание сохранено, но задачу APScheduler обновить не удалось."),
                "warning",
            )

    def _remove_scheduler_job(self, item: ContentCardIssueSchedule, commit: bool = True):
        session = self.datamodel.session
        try:
            job_id = str(item.scheduler_job_id or "").strip()
            if not job_id:
                if commit:
                    session.commit()
                return
            job = scheduler.get_job(job_id)
            if job:
                scheduler.remove_job(job_id)
            item.scheduler_job_id = None
            if commit:
                session.commit()
        except Exception as exc:
            if commit:
                session.rollback()
            logger.exception("Failed to remove card issue schedule job: {}", exc)
