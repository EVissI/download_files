﻿from datetime import datetime
import enum
from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, Enum, String
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
    lang_code: Mapped[str | None] = mapped_column(
        String(3), nullable=True, default="en"
    )
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
    analiz_count: Mapped[Optional[int]] 
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    max_usage: Mapped[Optional[int]] = mapped_column(Integer, default=None)
    activate_count: Mapped[Optional[int]] = mapped_column(Integer, default=None)
    duration_days: Mapped[Optional[int]] = mapped_column(Integer, default=None)

    users: Mapped[list["UserPromocode"]] = relationship(
        "UserPromocode", back_populates="promocode"
    )


class UserPromocode(Base):
    __tablename__ = "user_promocode"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    promocode_id: Mapped[int] = mapped_column(Integer, ForeignKey("promocode.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    current_analize_balance: Mapped[Optional[int]]

    user: Mapped["User"] = relationship("User", back_populates="used_promocodes")
    promocode: Mapped["Promocode"] = relationship("Promocode", back_populates="users")


class UserAnalizePayment(Base):
    __tablename__ = "user_analize_payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False
    )
    analize_payment_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("analize_payments.id"), nullable=False
    )
    current_analize_balance: Mapped[int]
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    user: Mapped["User"] = relationship("User", back_populates="analize_payments_assoc")
    analize_payment: Mapped["AnalizePayment"] = relationship(
        "AnalizePayment", back_populates="users_assoc"
    )


class AnalizePayment(Base):
    __tablename__ = "analize_payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_days: Mapped[Optional[int]] = mapped_column(Integer, default=None)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    users_assoc: Mapped[list["UserAnalizePayment"]] = relationship(
        "UserAnalizePayment", back_populates="analize_payment"
    )
