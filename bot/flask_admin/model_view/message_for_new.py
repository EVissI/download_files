# admin/views/message_for_new.py
from flask_appbuilder import ModelView, has_access
from flask_appbuilder.models.sqla.interface import SQLAInterface
from flask_appbuilder.fieldwidgets import BS3TextAreaFieldWidget
from flask_appbuilder.forms import DynamicForm
from flask import flash
from wtforms import StringField, TextAreaField
from wtforms.validators import DataRequired, Regexp, Length
from flask_babel import lazy_gettext as _
from zoneinfo import ZoneInfo
from loguru import logger

from bot.db.models import MessageForNew
from bot.config import scheduler
from bot.common.tasks.gift import check_and_notify_gift


class MessageForNewModelView(ModelView):
    datamodel = SQLAInterface(MessageForNew)

    can_create = False
    can_delete = False
    can_edit = True
    can_show = True
    can_list = True

    page_size = 50

    list_title = _("Сообщения для новых пользователей")
    edit_title = _("Редактировать сообщение для новых пользователей")

    list_columns = [
        "lang_code",
        "dispatch_day_display",
        "dispatch_time",
        "text_preview",
    ]

    show_columns = [
        "lang_code",
        "dispatch_day",
        "dispatch_time",
        "text",
    ]
    
    edit_exclude_columns = ["created_at", "updated_at"]
    # Форма редактирования с валидацией
    form_columns = ["lang_code", "text", "dispatch_day", "dispatch_time"]

    search_columns = ["lang_code", "text"]

    label_columns = {
        "lang_code": _("Язык"),
        "text": _("Текст сообщения"),
        "dispatch_day": _("Дни недели (mon,tue,wed...)"),
        "dispatch_time": _("Время отправки (ЧЧ:ММ)"),
        "dispatch_day_display": _("Дни недели"),
        "text_preview": _("Предпросмотр текста"),
    }

    description_columns = {
        "text": _("Поддерживается HTML-разметка. Максимум 1000 символов."),
        "dispatch_day": _("Через запятую на английском: mon,tue,wed,thu,fri,sat,sun. Изменяйте в одной записи — будет скопировано в другую."),
        "dispatch_time": _("Формат: 14:30. Изменяйте в одной записи — будет скопировано в другую."),
    }

    order_columns = ["lang_code"]

    # Переопределяем форму для красивого поля текста и валидации
    form_extra_fields = {
        "text": TextAreaField(
            _("Текст сообщения"),
            widget=BS3TextAreaFieldWidget(),
            validators=[DataRequired(), Length(max=1000)],
            description=_("Поддерживается HTML. Максимум 1000 символов.")
        ),
        "dispatch_day": StringField(
            _("Дни недели"),
            validators=[
                DataRequired(),
                Regexp(r'^([a-z]{3})(,[a-z]{3})*$', message=_("Формат: mon,tue,wed (через запятую, без пробелов)"))
            ]
        ),
        "dispatch_time": StringField(
            _("Время отправки"),
            validators=[
                DataRequired(),
                Regexp(r'^\d{2}:\d{2}$', message=_("Формат: ЧЧ:ММ, например 10:00"))
            ]
        ),
    }

    # Главная магия: после сохранения — синхронизация + обновление планировщика
    def post_update(self, item):
        self._sync_schedule_fields(item)
        self._update_gift_scheduler(item)

    def post_add(self, item):  # на всякий случай
        self._sync_schedule_fields(item)
        self._update_gift_scheduler(item)

    def _sync_schedule_fields(self, item):
        """Копирует dispatch_day и dispatch_time в запись другого языка"""
        other_lang = 'en' if item.lang_code == 'ru' else 'ru'
        session = self.datamodel.session
        other = session.query(MessageForNew).filter_by(lang_code=other_lang).first()
        if other and (other.dispatch_day != item.dispatch_day or other.dispatch_time != item.dispatch_time):
            other.dispatch_day = item.dispatch_day
            other.dispatch_time = item.dispatch_time
            session.commit()
            logger.info(f"Синхронизировано расписание из {item.lang_code} в {other_lang}")

    def _update_gift_scheduler(self, item):
        """Обновляет задачу gift_notification в APScheduler"""
        if not item.dispatch_day or not item.dispatch_time:
            logger.warning("Не хватает данных для обновления планировщика gift_notification")
            return

        try:
            hour, minute = map(int, item.dispatch_time.split(":"))
            moscow_tz = ZoneInfo("Europe/Moscow")

            scheduler.add_job(
                check_and_notify_gift,
                "cron",
                day_of_week=item.dispatch_day,
                hour=hour,
                minute=minute,
                timezone=moscow_tz,
                id="gift_notification",
                replace_existing=True
            )
            logger.info(f"Задача gift_notification обновлена: {item.dispatch_day} {item.dispatch_time}")
            flash(_("Расписание рассылки успешно обновлено"), "success")
        except Exception as e:
            logger.error(f"Ошибка при обновлении gift_notification: {e}")
            flash(_("Сообщение сохранено, но не удалось обновить расписание рассылки"), "warning")