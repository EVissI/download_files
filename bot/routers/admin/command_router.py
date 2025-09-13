from aiogram import Router, F
from aiogram.types import Message
from bot.db.dao import UserDAO
from bot.db.models import User
from loguru import logger

from bot.db.schemas import SUser

commands_router = Router()

@commands_router.message(F.text.startswith("/makeadmin"))
async def make_admin(message: Message, session_without_commit):
    try:
        parts = message.text.split()
        if len(parts) != 2 or not parts[1].isdigit():
            return await message.answer("Использование: /makeadmin <user_id>")

        user_id = int(parts[1])

        user_dao = UserDAO(session_without_commit)
        user = await user_dao.find_one_or_none_by_id(user_id)

        if not user:
            return await message.answer(f"Пользователь с ID {user_id} не найден.")

        user.role = User.Role.ADMIN.value
        await session_without_commit.commit()

        await message.answer(f"Пользователь с ID {user_id} теперь администратор.")
    except Exception as e:
        logger.error(f"Ошибка при выполнении команды /makeadmin: {e}")
        await message.answer("Произошла ошибка при выполнении команды.")

@commands_router.message(F.text.startswith("/delete_user"))
async def make_admin(message: Message, session_without_commit):
    try:
        parts = message.text.split()
        if len(parts) != 2 or not parts[1].isdigit():
            return await message.answer("Использование: /makeadmin <user_id>")

        user_id = int(parts[1])

        user_dao = UserDAO(session_without_commit)
        user = await user_dao.find_one_or_none_by_id(user_id)

        if not user:
            return await message.answer(f"Пользователь с ID {user_id} не найден.")

        await user_dao.delete(SUser(id=user_id))
        await session_without_commit.commit()

        await message.answer(f"Пользователь с ID {user_id} удален")
    except Exception as e:
        logger.error(f"Ошибка при выполнении команды /delete_user: {e}")
        await message.answer("Произошла ошибка при выполнении команды.")

@commands_router.message(F.text.startswith("/listusers"))
async def list_users(message: Message, session_without_commit):
    try:
        user_dao = UserDAO(session_without_commit)
        users:list[User] = await user_dao.find_all()

        if not users:
            return await message.answer("Нет зарегистрированных пользователей.")

        user_list = "\n".join(
            [f"ID: <code>{user.id}</code>, Username: <code>{user.username or 'нет'}</code>, Role: {user.role}" for user in users]
        )
        await message.answer(f"Список пользователей:\n{user_list}")
    except Exception as e:
        logger.error(f"Ошибка при выполнении команды /listusers: {e}")
        await message.answer("Произошла ошибка при выполнении команды.")