from datetime import datetime, timedelta, timezone
from collections import defaultdict
import enum
from typing import Any, Optional
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    true as sa_true,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from bot.db.database import Base
from flask_appbuilder.models.decorators import renders


class User(Base):
    __tablename__ = "users"

    class Role(enum.Enum):
        USER = "user"
        ADMIN = "admin"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str | None]
    player_username: Mapped[str | None] = mapped_column(String(50), nullable=True)
    first_name: Mapped[str | None]
    last_name: Mapped[str | None]
    admin_insert_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    lang_code: Mapped[str | None] = mapped_column(
        String(3), nullable=True, default="en"
    )
    phone_number: Mapped[str | None]
    email: Mapped[str | None]
    role: Mapped["Role"] = mapped_column(
        String(5), default=Role.USER.value, nullable=False
    )
    user_game_analisis: Mapped[list["Analysis"]] = relationship(
        "Analysis", back_populates="user", cascade="all, delete-orphan"
    )
    detailed_analyzes: Mapped[list["DetailedAnalysis"]] = relationship(
        "DetailedAnalysis", back_populates="user", cascade="all, delete-orphan"
    )
    used_promocodes: Mapped[list["UserPromocode"]] = relationship(
        "UserPromocode", back_populates="user", cascade="all, delete-orphan"
    )
    analize_payments_assoc: Mapped[list["UserAnalizePayment"]] = relationship(
        "UserAnalizePayment", back_populates="user", cascade="all, delete-orphan"
    )
    broadcasts: Mapped[list["Broadcast"]] = relationship(
        "Broadcast", back_populates="user", cascade="all, delete-orphan"
    )
    groups: Mapped[list["UserInGroup"]] = relationship(
        "UserInGroup",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    broadcast_recipients: Mapped[list["Broadcast"]] = relationship(
        "Broadcast", secondary="broadcast_users", back_populates="recipients"
    )
    user_content_cards: Mapped[list["UserContentCard"]] = relationship(
        "UserContentCard",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    @property
    @renders("active_promocodes")
    def active_promocodes(self):
        """Список активных промокодов пользователя"""
        active_promocodes = [
            p.promocode.code for p in self.used_promocodes if p.is_active
        ]
        return ", ".join(active_promocodes) if active_promocodes else "—"

    @property
    @renders("active_payments")
    def active_payments(self):
        """Список активных покупок пользователя"""
        active_payments = [
            p.analize_payment.name for p in self.analize_payments_assoc if p.is_active
        ]
        return ", ".join(active_payments) if active_payments else "—"

    @property
    @renders("total_balance")
    def total_balance(self):
        """Детальный баланс услуг по сервисам"""
        from collections import defaultdict

        service_totals = defaultdict(int)

        # Промокоды
        for promocode in [p for p in self.used_promocodes if p.is_active]:
            for service in promocode.remaining_services:
                service_totals[service.service_type.value] += (
                    service.remaining_quantity or 0
                )

        # Платежи
        for payment in [p for p in self.analize_payments_assoc if p.is_active]:
            for service in payment.remaining_services:
                service_totals[service.service_type.value] += service.remaining_quantity

        if not service_totals:
            return "—"

        return ", ".join(
            f"{service}: {count}" for service, count in service_totals.items()
        )

    @property
    @renders("total_cards_count")
    def total_cards_count(self):
        """Общее количество карточек пользователя."""
        return str(len(self.user_content_cards or []))

    def __repr__(self) -> str:
        label = self.admin_insert_name or self.username or self.first_name or "user"
        return f"{self.id} | {label}"


class Analysis(Base):
    __tablename__ = "analyzes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mistake_total: Mapped[int]
    mistake_doubling: Mapped[int]
    mistake_taking: Mapped[int]
    luck: Mapped[float]
    pr: Mapped[float]

    file_name: Mapped[str] = mapped_column(String(255), nullable=True)
    file_path: Mapped[str] = mapped_column(String(255), nullable=True)
    game_id: Mapped[str | None] = mapped_column(String(50), nullable=True)

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))

    user: Mapped["User"] = relationship("User", back_populates="user_game_analisis")


class DetailedAnalysis(Base):
    __tablename__ = "detailed_analyzes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    player_name: Mapped[str] = mapped_column(String(50))

    # Chequerplay
    moves_marked_bad: Mapped[int]
    moves_marked_very_bad: Mapped[int]
    error_rate_chequer: Mapped[float]
    chequerplay_rating: Mapped[str]

    # Luck
    rolls_marked_very_lucky: Mapped[int]
    rolls_marked_lucky: Mapped[int]
    rolls_marked_unlucky: Mapped[int]
    rolls_marked_very_unlucky: Mapped[int]
    rolls_rate_chequer: Mapped[float]
    luck_rating: Mapped[str]

    # Cube (добавлены новые поля)
    missed_doubles_below_cp: Mapped[int]
    missed_doubles_above_cp: Mapped[int]
    wrong_doubles_below_sp: Mapped[int]
    wrong_doubles_above_tg: Mapped[int]
    wrong_takes: Mapped[int]
    wrong_passes: Mapped[int]
    cube_error_rate: Mapped[float]
    cube_decision_rating: Mapped[str]

    # Overall
    snowie_error_rate: Mapped[float]
    overall_rating: Mapped[str]

    # File info
    file_name: Mapped[str] = mapped_column(String(255), nullable=True)
    file_path: Mapped[str] = mapped_column(String(255), nullable=True)
    game_id: Mapped[str | None] = mapped_column(String(50), nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="detailed_analyzes")


class PromocodeType(str, enum.Enum):
    REGULAR = "regular"
    CARDS = "cards"


class Promocode(Base):
    __tablename__ = "promocode"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    max_usage: Mapped[Optional[int]] = mapped_column(Integer, default=None)
    activate_count: Mapped[Optional[int]] = mapped_column(
        Integer, default=0, server_default="0"
    )
    duration_days: Mapped[Optional[int]] = mapped_column(Integer, default=None)
    promocode_type: Mapped["PromocodeType"] = mapped_column(
        Enum(PromocodeType, name="promocodetype"),
        default=PromocodeType.REGULAR,
        nullable=False,
    )
    cards_issue_quantity: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    services: Mapped[list["PromocodeServiceQuantity"]] = relationship(
        "PromocodeServiceQuantity",
        back_populates="promocode",
        cascade="all, delete-orphan",
    )

    users: Mapped[list["UserPromocode"]] = relationship(
        "UserPromocode", back_populates="promocode", cascade="all, delete-orphan"
    )
    content_cards: Mapped[list["PromocodeContentCard"]] = relationship(
        "PromocodeContentCard",
        back_populates="promocode",
        cascade="all, delete-orphan",
        order_by="PromocodeContentCard.position",
    )

    @property
    @renders("max_usage_display")
    def max_usage_display(self):
        return "∞" if self.max_usage is None else str(self.max_usage)

    @property
    @renders("duration_days_display")
    def duration_days_display(self):
        return "∞" if self.duration_days is None else str(self.duration_days)

    @property
    @renders("activate_count_display")
    def activate_count_display(self):
        return str(self.activate_count or 0)

    @property
    @renders("services_summary")
    def services_summary(self):
        if not self.services:
            return "—"
        return ", ".join(str(s) for s in self.services)


class ServiceType(str, enum.Enum):
    MATCH = "Матч"
    MONEYGAME = "Moneygame"
    SHORT_BOARD = "Плеер"
    HINTS = "Ошибки"
    POKAZ = "Позиция"
    COMMENTS = "Комментарии"
    SCRINSHOT = "Скриншоты"


service_type_enum = Enum(ServiceType, name="servicetype", metadata=Base.metadata)


class PromocodeServiceQuantity(Base):
    __tablename__ = "promocode_service_quantities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    promocode_id: Mapped[int] = mapped_column(Integer, ForeignKey("promocode.id"))
    service_type: Mapped["ServiceType"] = mapped_column(
        Enum(ServiceType, name="servicetype"), nullable=False
    )
    quantity: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    promocode: Mapped["Promocode"] = relationship(
        "Promocode", back_populates="services"
    )

    def __str__(self):
        """Отображение услуги в админке"""
        if self.quantity is not None and self.quantity > 0:
            return f"{self.service_type.value}: {self.quantity}"
        else:
            return f"{self.service_type.value}: ∞"


class UserPromocode(Base):
    __tablename__ = "user_promocode"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    promocode_id: Mapped[int] = mapped_column(Integer, ForeignKey("promocode.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    issued_cards_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )

    remaining_services: Mapped[list["UserPromocodeService"]] = relationship(
        "UserPromocodeService",
        back_populates="user_promocode",
        cascade="all, delete-orphan",
    )

    user: Mapped["User"] = relationship("User", back_populates="used_promocodes")
    promocode: Mapped["Promocode"] = relationship("Promocode", back_populates="users")
    issued_content_cards: Mapped[list["UserContentCard"]] = relationship(
        "UserContentCard",
        back_populates="source_user_promocode",
    )

    @property
    @renders("promo_date_range")
    def promo_date_range(self) -> str:
        """Период действия промо: с даты активации по дату окончания (или ∞)"""
        if not self.created_at:
            return "—"
        start = self.created_at
        if isinstance(start, datetime) and start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        start_str = start.strftime("%d.%m.%Y") if isinstance(start, datetime) else str(start)
        if self.promocode and self.promocode.duration_days is not None:
            end = start + timedelta(days=self.promocode.duration_days)
            end_str = end.strftime("%d.%m.%Y") if isinstance(end, datetime) else str(end)
            return f"{start_str} — {end_str}"
        return f"{start_str} — ∞"

    @property
    @renders("remaining_balance_display")
    def remaining_balance_display(self) -> str:
        """Остаток по услугам: Матч: 3, Ошибки: 5 и т.д."""
        if not self.remaining_services:
            return "—"
        parts = []
        for s in self.remaining_services:
            qty = "∞" if s.remaining_quantity is None else str(s.remaining_quantity)
            parts.append(f"{s.service_type.value}: {qty}")
        return ", ".join(parts)

    @property
    @renders("created_at_display")
    def created_at_display(self) -> str:
        """Дата активации в читаемом формате"""
        if not self.created_at:
            return "—"
        d = self.created_at
        return d.strftime("%d.%m.%Y %H:%M") if isinstance(d, datetime) else str(d)

    @property
    @renders("is_active_display")
    def is_active_display(self) -> str:
        """Отображение статуса: Активен / Нет"""
        return "Активен" if self.is_active else "Нет"


class UserPromocodeService(Base):
    __tablename__ = "user_promocode_services"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_promocode_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("user_promocode.id")
    )
    service_type: Mapped[ServiceType] = mapped_column(Enum(ServiceType), nullable=False)
    remaining_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)

    user_promocode: Mapped["UserPromocode"] = relationship(
        "UserPromocode", back_populates="remaining_services"
    )


class AnalizePaymentServiceQuantity(Base):
    """
    Модель для хранения типов услуг и их количества, связанных с платежами.
    """

    __tablename__ = "analize_payment_service_quantities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    analize_payment_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("analize_payments.id")
    )
    service_type: Mapped["ServiceType"] = mapped_column(
        Enum(ServiceType), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    analize_payment: Mapped["AnalizePayment"] = relationship(
        "AnalizePayment", back_populates="services"
    )

    def __str__(self):
        if self.quantity is not None and self.quantity > 0:
            return f"{self.service_type.value}: {self.quantity}"
        else:
            return f"{self.service_type.value}: ∞"


class UserAnalizePaymentService(Base):
    """
    Модель для отслеживания оставшегося баланса услуг для пользователя, связанных с платежами.
    """

    __tablename__ = "user_analize_payment_services"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_analize_payment_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("user_analize_payments.id")
    )
    service_type: Mapped[ServiceType] = mapped_column(
        Enum(ServiceType, name="servicetype"), nullable=False
    )
    remaining_quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    user_analize_payment: Mapped["UserAnalizePayment"] = relationship(
        "UserAnalizePayment", back_populates="remaining_services"
    )


class AnalizePayment(Base):
    __tablename__ = "analize_payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    price: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_days: Mapped[Optional[int]] = mapped_column(Integer, default=None)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    services: Mapped[list["AnalizePaymentServiceQuantity"]] = relationship(
        "AnalizePaymentServiceQuantity",
        back_populates="analize_payment",
        cascade="all, delete-orphan",
    )
    users_assoc: Mapped[list["UserAnalizePayment"]] = relationship(
        "UserAnalizePayment",
        back_populates="analize_payment",
        cascade="all, delete-orphan",
    )

    @property
    @renders("duration_days_display")
    def duration_days_display(self) -> str:
        """Отображает длительность как '∞' если None, иначе число дней"""
        return "∞" if self.duration_days is None else str(self.duration_days)

    @property
    @renders("services_summary")
    def services_summary(self) -> str:
        """Красивое сводное отображение услуг в списке и деталях"""
        if not self.services:
            return "—"
        return ", ".join(str(service) for service in self.services)


class UserAnalizePayment(Base):
    __tablename__ = "user_analize_payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False
    )
    analize_payment_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("analize_payments.id"), nullable=False
    )
    tranzaction_id: Mapped[str]
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    remaining_services: Mapped[list["UserAnalizePaymentService"]] = relationship(
        "UserAnalizePaymentService",
        back_populates="user_analize_payment",
        cascade="all, delete-orphan",
    )

    user: Mapped["User"] = relationship("User", back_populates="analize_payments_assoc")
    analize_payment: Mapped["AnalizePayment"] = relationship(
        "AnalizePayment", back_populates="users_assoc"
    )


class BroadcastStatus(enum.Enum):
    SCHEDULED = "SCHEDULED"
    SENT = "SENT"
    CANCELLED = "CANCELLED"


class Broadcast(Base):
    __tablename__ = "broadcasts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    media_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    media_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    group_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    group: Mapped[str] = mapped_column(String(30), nullable=False)
    run_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped["BroadcastStatus"] = mapped_column(
        Enum(BroadcastStatus), default=BroadcastStatus.SCHEDULED.value, nullable=False
    )
    created_by: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False
    )
    user: Mapped["User"] = relationship("User", back_populates="broadcasts")
    recipients: Mapped[list["User"]] = relationship(
        "User", secondary="broadcast_users", back_populates="broadcast_recipients"
    )


class BroadcastUser(Base):
    __tablename__ = "broadcast_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    broadcast_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("broadcasts.id"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False
    )


class MessageForNew(Base):
    __tablename__ = "messages_for_new"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    lang_code: Mapped[str] = mapped_column(String(3), nullable=False, default="en")
    dispatch_day: Mapped[str] = mapped_column(
        String, nullable=False
    )  # День рассылки, например, "Monday"
    dispatch_time: Mapped[str] = mapped_column(
        String(5), nullable=False
    )  # Время рассылки в формате "HH:MM"

    @property
    @renders("dispatch_day_display")
    def dispatch_day_display(self) -> str:
        """Человекочитаемые дни недели"""
        if not self.dispatch_day:
            return "—"
        days_map = {
            "mon": "Понедельник",
            "tue": "Вторник",
            "wed": "Среда",
            "thu": "Четверг",
            "fri": "Пятница",
            "sat": "Суббота",
            "sun": "Воскресенье",
        }
        days = [d.strip().lower() for d in self.dispatch_day.split(",")]
        return ", ".join(days_map.get(d, d.capitalize()) for d in days)

    @property
    @renders("text_preview")
    def text_preview(self) -> str:
        """Короткий предпросмотр текста в списке"""
        if not self.text:
            return "—"
        preview = self.text.strip().replace("\n", " ")
        return (preview[:120] + "…") if len(preview) > 120 else preview


class UserGroup(Base):
    __tablename__ = "user_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)

    users: Mapped[list["UserInGroup"]] = relationship(
        "UserInGroup",
        back_populates="group",
        cascade="all, delete-orphan",
    )


class UserInGroup(Base):
    __tablename__ = "user_in_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False
    )
    group_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("user_groups.id"), nullable=False
    )

    user: Mapped["User"] = relationship("User", back_populates="groups")
    group: Mapped["UserGroup"] = relationship("UserGroup", back_populates="users")


class MessagesTexts(Base):
    __tablename__ = "messages_texts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(30), nullable=False)
    text_ru: Mapped[str] = mapped_column(String(1000))
    text_en: Mapped[str] = mapped_column(String(1000))


class LabelPreset(Base):
    """
    Пресеты текстов для меток карточек (ContentCard.labels): админ задаёт список,
    при редактировании меток можно подставлять значения из пресетов.
    """

    __tablename__ = "label_presets"
    __table_args__ = (
        UniqueConstraint("value", name="uq_label_presets_value"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    value: Mapped[str] = mapped_column(String(255), nullable=False)


class TextStylePreset(Base):
    """
    Пресеты стилей для текстовых блоков редактора контента.
    Хранятся глобально для администраторов.
    """

    __tablename__ = "text_style_presets"
    __table_args__ = (
        UniqueConstraint("name", name="uq_text_style_presets_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class ContentFrameTemplate(Base):
    """
    Шаблоны кадра редактора контента: полный JSON payload кадра (глобально для ROOT_ADMIN).
    """

    __tablename__ = "content_frame_templates"
    __table_args__ = (
        UniqueConstraint("name", name="uq_content_frame_templates_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    # created_at / updated_at — из Base (как у TextStylePreset)


class WebAppSetting(Base):
    """
    Глобальные настройки WebApp, редактируемые через FAB.
    """

    __tablename__ = "webapp_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    webapp_fullscreen_hints_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    webapp_fullscreen_pokaz_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    webapp_fullscreen_cards_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    webapp_fullscreen_admin_login_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    webapp_fullscreen_player_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )


class ContentCardIssueSchedule(Base):
    """Расписание автовыдачи карточек конкретному пользователю (по МСК)."""

    __tablename__ = "content_card_issue_schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    target_user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    cards_per_run: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    weekdays: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    issue_time_msk: Mapped[str] = mapped_column(String(5), nullable=False)
    scheduler_job_id: Mapped[str | None] = mapped_column(
        String(128), unique=True, nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    target_user: Mapped["User"] = relationship("User")

    @property
    @renders("weekdays_display")
    def weekdays_display(self) -> str:
        day_map = {
            "mon": "Пн",
            "tue": "Вт",
            "wed": "Ср",
            "thu": "Чт",
            "fri": "Пт",
            "sat": "Сб",
            "sun": "Вс",
        }
        values = []
        for day in self.weekdays or []:
            key = str(day or "").strip().lower()
            if not key:
                continue
            values.append(day_map.get(key, key))
        return ", ".join(values) if values else "—"

    @property
    @renders("target_user_display")
    def target_user_display(self) -> str:
        if not self.target_user:
            return str(self.target_user_id)
        username = f"@{self.target_user.username}" if self.target_user.username else "—"
        title = (
            self.target_user.admin_insert_name
            or self.target_user.first_name
            or self.target_user.last_name
            or "—"
        )
        return f"{self.target_user_id} | {title} | {username}"


class ContentCard(Base):
    """
    Сохранённая карточка редактора контента (hint viewer и т.п.).
    Привязка к пользователям — только через таблицу user_content_cards (many-to-many).

    frames — JSONB со структурой кадров, например:
      {"version": 1,
       "sharedContext": {"board": {...}, "cardData": {...}},
       "frames": [
        {"frameId": "...", "saveSlotIndex": 0, "order": 0,
         "payload": {"elements": [
           {"toolId": "upload-image", "imageS3Key": "content_cards/media/{user_id}/{uuid}.png"},
           {"toolId": "audio-file", "audioS3Key": "content_cards/media/..."},
           {"toolId": "attach-file", "attachmentS3Key": "...", "attachmentFileName": "..."},
           {"toolId": "board-illustration", "boardImageS3Key": "..."}
         ], ...}}
      ]}
      sharedContext — опционально: общие для всех кадров снимок доски и данные таблиц (hint viewer);
      подставляются в редактор пустого кадра на /content-card-view без дублирования в каждом payload.
      Медиа в S3; отображение GET /api/content_cards/media?key= (доступ по ключу из JSON карточки, в т.ч. для других пользователей после шаринга).
      labels — нативный PostgreSQL-массив строк (TEXT[]).
      board_xgid — строка позиции GNU/XGID из снимка доски (если в карточке есть доска с полем xgid).
    """

    __tablename__ = "content_cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    frames: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    board_xgid: Mapped[str | None] = mapped_column(Text, nullable=True)
    labels: Mapped[list[str] | None] = mapped_column(ARRAY[str](String(255)), nullable=True)

    users: Mapped[list["UserContentCard"]] = relationship(
        "UserContentCard",
        back_populates="content_card",
        cascade="all, delete-orphan",
    )
    promocodes: Mapped[list["PromocodeContentCard"]] = relationship(
        "PromocodeContentCard",
        back_populates="content_card",
        cascade="all, delete-orphan",
    )


class PromocodeContentCard(Base):
    """Связь промокода с карточками и порядком выдачи."""

    __tablename__ = "promocode_content_cards"
    __table_args__ = (
        UniqueConstraint(
            "promocode_id",
            "position",
            name="uq_promocode_content_cards_promocode_id_position",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    promocode_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("promocode.id", ondelete="CASCADE"), nullable=False
    )
    content_card_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("content_cards.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    promocode: Mapped["Promocode"] = relationship(
        "Promocode", back_populates="content_cards"
    )
    content_card: Mapped["ContentCard"] = relationship(
        "ContentCard", back_populates="promocodes"
    )


class UserContentCardStatus(str, enum.Enum):
    UNVIEWED = "UNVIEWED"
    VIEWED = "VIEWED"
    SOLVED = "SOLVED"
    FAVORITE = "FAVORITE"
    HARD = "HARD"


class ContentCardActivationLinkStatus(str, enum.Enum):
    UNACTIVATE = "unactivate"
    ACTIVATE = "activate"


class ContentCardActivationLink(Base):
    __tablename__ = "content_card_activation_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    link: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    status: Mapped["ContentCardActivationLinkStatus"] = mapped_column(
        Enum(
            ContentCardActivationLinkStatus,
            name="contentcardlinkstatus",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=ContentCardActivationLinkStatus.UNACTIVATE,
        server_default=ContentCardActivationLinkStatus.UNACTIVATE.value,
    )
    card_ids: Mapped[list[int]] = mapped_column(JSONB, nullable=False)
    activated_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    activated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    activated_by_user: Mapped[Optional["User"]] = relationship("User")


class ContentCardFolder(Base):
    """
    Иерархическая «папка» для группировки карточек.
    Используется для дерева в кабинете и ссылок на ветки.
    """

    __tablename__ = "content_card_folders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("content_card_folders.id", ondelete="SET NULL"),
        nullable=True,
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by_admin_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    parent: Mapped[Optional["ContentCardFolder"]] = relationship(
        "ContentCardFolder",
        remote_side="ContentCardFolder.id",
        back_populates="children",
    )
    children: Mapped[list["ContentCardFolder"]] = relationship(
        "ContentCardFolder",
        back_populates="parent",
        cascade="all, delete-orphan",
    )
    created_by_admin: Mapped[Optional["User"]] = relationship("User")


class ContentCardFolderItem(Base):
    """
    Привязка карточки к папке дерева (many-to-many).
    Одна карточка может находиться в нескольких папках.
    """

    __tablename__ = "content_card_folder_items"
    __table_args__ = (
        UniqueConstraint(
            "folder_id",
            "content_card_id",
            name="uq_content_card_folder_items_folder_id_content_card_id",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    folder_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("content_card_folders.id", ondelete="CASCADE"), nullable=False
    )
    content_card_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("content_cards.id", ondelete="CASCADE"), nullable=False
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    folder: Mapped["ContentCardFolder"] = relationship(
        "ContentCardFolder",
        backref="items",
    )
    content_card: Mapped["ContentCard"] = relationship("ContentCard")


class ContentCardFolderLink(Base):
    """
    Многоразовая ссылка на папку дерева карточек для read-only просмотра.
    """

    __tablename__ = "content_card_folder_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    link_token: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    folder_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("content_card_folders.id", ondelete="CASCADE"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=sa_true()
    )
    created_by_admin_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    folder: Mapped["ContentCardFolder"] = relationship("ContentCardFolder")
    created_by_admin: Mapped[Optional["User"]] = relationship("User")


class UserContentCard(Base):
    """Связь пользователь ↔ карточка (many-to-many), по аналогии с UserPromocode."""

    __tablename__ = "user_content_cards"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "content_card_id",
            name="uq_user_content_cards_user_id_content_card_id",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    content_card_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("content_cards.id", ondelete="CASCADE"), nullable=False
    )
    card_status: Mapped["UserContentCardStatus"] = mapped_column(
        Enum(UserContentCardStatus, name="usercontentcardstatus"),
        nullable=False,
        default=UserContentCardStatus.UNVIEWED,
        server_default=UserContentCardStatus.UNVIEWED.value,
    )
    source_user_promocode_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("user_promocode.id", ondelete="SET NULL"), nullable=True
    )

    user: Mapped["User"] = relationship("User", back_populates="user_content_cards")
    content_card: Mapped["ContentCard"] = relationship(
        "ContentCard", back_populates="users"
    )
    source_user_promocode: Mapped[Optional["UserPromocode"]] = relationship(
        "UserPromocode", back_populates="issued_content_cards"
    )


class UserContentCardInteractiveStat(Base):
    """
    Счётчики интерактива «лучший ход» по паре пользователь ↔ карточка
    (без привязки к кадру).
    """

    __tablename__ = "user_content_card_interactive_stats"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "content_card_id",
            name="uq_ucc_interactive_user_id_content_card_id",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    content_card_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("content_cards.id", ondelete="CASCADE"), nullable=False
    )
    correct_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    wrong_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
