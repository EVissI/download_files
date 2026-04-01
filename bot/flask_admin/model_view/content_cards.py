from flask_appbuilder import ModelView
from flask_appbuilder.models.filters import BaseFilter
from flask_appbuilder.models.sqla.filters import SQLAFilterConverter, get_field_setup_query
from flask_appbuilder.models.sqla.interface import SQLAInterface
from flask_babel import lazy_gettext as _
from sqlalchemy import func
from wtforms import StringField, validators

from bot.db.models import ContentCard

# Разделитель для array_to_string: непечатный символ, чтобы не сливать реальные метки
_LABELS_JOIN_DELIM = "\x1f"


def _escape_ilike_pattern(s: str) -> str:
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


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
    base_permissions = ["can_list", "can_show"]

    list_title = _("Карточки")
    show_title = _("Карточка")

    page_size = 30
    list_columns = ["id", "file_name", "labels", "created_at", "updated_at"]
    show_columns = ["id", "file_name", "labels", "created_at", "updated_at"]
    search_columns = ["id", "file_name", "labels"]
    order_columns = ["id", "file_name", "created_at", "updated_at"]

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
        "labels": _("Метки"),
        "frames": _("Кадры (JSON)"),
        "created_at": _("Создано"),
        "updated_at": _("Обновлено"),
    }

    description_columns = {
        "labels": _(
            "Массив меток в PostgreSQL. «Подстрока в метке» — вхождение в любую метку; "
            "«Точная метка» — элемент массива равен введённой строке."
        ),
    }
