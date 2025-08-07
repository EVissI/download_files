import random
import asyncio
import typer
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from bot.db.models import (
    User, UserPromocode, UserAnalizePayment, Promocode, AnalizePayment
)
from bot.db.database import Base
from bot.config import settings

app = typer.Typer()

DATABASE_URL = settings.DB_URL

engine = create_async_engine(DATABASE_URL, echo=True, future=True)
AsyncSessionLocal = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def create_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

@app.command()
def init_db():
    """Создать структуру БД."""
    asyncio.run(create_db())
    typer.echo("База данных создана.")

@app.command()
def mock_users(count: int = 10):
    """Создать мок-пользователей и вывести их id."""
    async def _mock():
        ids = []
        async with AsyncSessionLocal() as session:
            for i in range(count):
                user = User(
                    id=1000 + i,
                    username=f"user{i}",
                    player_username=f"player{i}",
                    first_name=f"First{i}",
                    last_name=f"Last{i}",
                    lang_code="ru" if i % 2 == 0 else "en",
                    phone_number=f"+70000000{i:02d}",
                    email=f"user{i}@test.com",
                    role="user"
                )
                session.add(user)
                ids.append(user.id)
            await session.commit()
        typer.echo(f"Создано {count} пользователей. Их id: {ids}")
    asyncio.run(_mock())

@app.command()
def mock_user_promocode(
    user_id: int = typer.Option(..., help="ID пользователя"),
    promocode_id: int = typer.Option(None, help="ID промокода (если не указан, будет выбран случайно)")
):
    """Создать UserPromocode для пользователя."""
    async def _mock():
        async with AsyncSessionLocal() as session:
            if promocode_id is None:
                promos = (await session.execute(Promocode.__table__.select())).scalars().all()
                if not promos:
                    typer.echo("Нет промокодов в базе.")
                    return
                promo = random.choice(promos)
                promocode_id_ = promo.id
            else:
                promocode_id_ = promocode_id
            up = UserPromocode(
                user_id=user_id,
                promocode_id=promocode_id_,
                is_active=True,
                current_analize_balance=random.randint(1, 10)
            )
            session.add(up)
            await session.commit()
        typer.echo(f"UserPromocode создан для user_id={user_id}, promocode_id={promocode_id_}")
    asyncio.run(_mock())

@app.command()
def mock_user_payment(
    user_id: int = typer.Option(..., help="ID пользователя"),
    payment_id: int = typer.Option(None, help="ID пакета оплаты (если не указан, будет выбран случайно)")
):
    """Создать UserAnalizePayment для пользователя."""
    async def _mock():
        async with AsyncSessionLocal() as session:
            if payment_id is None:
                payments = (await session.execute(AnalizePayment.__table__.select())).scalars().all()
                if not payments:
                    typer.echo("Нет пакетов оплаты в базе.")
                    return
                payment = random.choice(payments)
                payment_id_ = payment.id
            else:
                payment_id_ = payment_id
            up = UserAnalizePayment(
                user_id=user_id,
                analize_payment_id=payment_id_,
                tranzaction_id=f"TXN{random.randint(10000,99999)}",
                current_analize_balance=random.randint(1, 10),
                is_active=True
            )
            session.add(up)
            await session.commit()
        typer.echo(f"UserAnalizePayment создан для user_id={user_id}, analize_payment_id={payment_id_}")
    asyncio.run(_mock())

if __name__ == "__main__":
    app()