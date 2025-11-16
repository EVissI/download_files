from datetime import datetime
import enum
from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, Enum, String, Text
from bot.db.database import Base


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
        "Analysis", back_populates="user"
    )
    detailed_analyzes: Mapped[list["DetailedAnalysis"]] = relationship(
        "DetailedAnalysis", back_populates="user"
    )
    used_promocodes: Mapped[list["UserPromocode"]] = relationship(
        "UserPromocode", back_populates="user"
    )
    analize_payments_assoc: Mapped[list["UserAnalizePayment"]] = relationship(
        "UserAnalizePayment", back_populates="user"
    )
    broadcasts: Mapped[list["Broadcast"]] = relationship(
        "Broadcast", back_populates="user"
    )
    groups: Mapped[list["UserInGroup"]] = relationship(
        "UserInGroup",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    broadcast_recipients: Mapped[list["Broadcast"]] = relationship(
        "Broadcast",
        secondary="broadcast_users",
        back_populates="recipients"
    )

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


class Promocode(Base):
    __tablename__ = "promocode"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    max_usage: Mapped[Optional[int]] = mapped_column(Integer, default=None)
    activate_count: Mapped[Optional[int]] = mapped_column(Integer, default=None)
    duration_days: Mapped[Optional[int]] = mapped_column(Integer, default=None)

    services: Mapped[list["PromocodeServiceQuantity"]] = relationship(
        "PromocodeServiceQuantity",
        back_populates="promocode",
        cascade="all, delete-orphan",
    )

    users: Mapped[list["UserPromocode"]] = relationship(
        "UserPromocode", back_populates="promocode"
    )

class ServiceType(str, enum.Enum):
        MATCH = "Матч"
        MONEYGAME = "Moneygame"
        SHORT_BOARD = "Плеер"
        HINTS = "Подсказки"

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


class UserPromocode(Base):
    __tablename__ = "user_promocode"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    promocode_id: Mapped[int] = mapped_column(Integer, ForeignKey("promocode.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    remaining_services: Mapped[list["UserPromocodeService"]] = relationship(
        "UserPromocodeService",
        back_populates="user_promocode",
        cascade="all, delete-orphan",
    )

    user: Mapped["User"] = relationship("User", back_populates="used_promocodes")
    promocode: Mapped["Promocode"] = relationship("Promocode", back_populates="users")


class UserPromocodeService(Base):
    __tablename__ = "user_promocode_services"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_promocode_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("user_promocode.id")
    )
    service_type: Mapped[ServiceType] = mapped_column(
        Enum(ServiceType), nullable=False
    )
    remaining_quantity: Mapped[int|None] = mapped_column(Integer, nullable=True)

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
        "UserAnalizePayment", back_populates="analize_payment"
    )


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
    group_id:Mapped[int | None] = mapped_column(Integer, nullable=True)
    group: Mapped[str] = mapped_column(String(30), nullable=False)
    run_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped["BroadcastStatus"] = mapped_column(
        Enum(BroadcastStatus),
        default=BroadcastStatus.SCHEDULED.value,
        nullable=False
    )
    created_by: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False
    )
    user: Mapped["User"] = relationship("User", back_populates="broadcasts")
    recipients: Mapped[list["User"]] = relationship(
        "User",
        secondary="broadcast_users",
        back_populates="broadcast_recipients"
    )


class BroadcastUser(Base):
    __tablename__ = "broadcast_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    broadcast_id: Mapped[int] = mapped_column(Integer, ForeignKey("broadcasts.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)


class MessageForNew(Base):
    __tablename__ = "messages_for_new"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    lang_code: Mapped[str] = mapped_column(String(3), nullable=False, default="en")
    dispatch_day: Mapped[str] = mapped_column(String, nullable=False)  # День рассылки, например, "Monday"
    dispatch_time: Mapped[str] = mapped_column(String(5), nullable=False)  # Время рассылки в формате "HH:MM"

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
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    group_id: Mapped[int] = mapped_column(Integer, ForeignKey("user_groups.id"), nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="groups")
    group: Mapped["UserGroup"] = relationship("UserGroup", back_populates="users")