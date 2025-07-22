import enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import BigInteger, ForeignKey, Integer, Enum, String
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
    role: Mapped["Role"] = mapped_column(
        String(5), default=Role.USER.value, nullable=False
    )
    user_game_analisis: Mapped[list["Analysis"]] = relationship(
        "Analysis", back_populates="user"
    )
    detailed_analyzes: Mapped[list["DetailedAnalysis"]] = relationship(
        "DetailedAnalysis", back_populates="user"
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

    # Cube
    cube_decision_rating: Mapped[str]

    # Overall
    snowie_error_rate: Mapped[float]
    overall_rating: Mapped[str]

    # File info
    file_name: Mapped[str] = mapped_column(String(255), nullable=True)
    file_path: Mapped[str] = mapped_column(String(255), nullable=True)
    game_id: Mapped[str | None] = mapped_column(String(50), nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="detailed_analyzes")
