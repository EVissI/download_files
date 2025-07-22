from aiogram import Router,F
from aiogram.types import Message
from aiogram.filters import CommandStart
from sqlalchemy.ext.asyncio import AsyncSession
from bot.common.kbds.markup.main_kb import MainKeyboard
from bot.common.texts import get_text
from bot.db.dao import UserDAO
from bot.db.models import User
from bot.db.schemas import SUser
from bot.config import settings
start_router = Router()

@start_router.message(CommandStart())
async def start_command(message: Message, session_with_commit: AsyncSession):
    user_data = message.from_user
    user_id = user_data.id
    user_info:User = await UserDAO(session_with_commit).find_one_or_none_by_id(user_id)
    if user_info and user_data.id in settings.ROOT_ADMIN_IDS:
        user_info.role = User.Role.ADMIN.value
        await UserDAO(session_with_commit).update(user_info.id, user_info.to_dict())
        await message.answer(
            get_text('start'), reply_markup=MainKeyboard.build(user_info.role)
        )
        return
    if user_info is None:
        role = User.Role.USER.value
        if user_info in settings.ROOT_ADMIN_IDS:
            role = User.Role.ADMIN.value
        user_schema = SUser(id=user_id, 
                            first_name=user_data.first_name,
                            last_name=user_data.last_name, 
                            username=user_data.username,
                            role=role)
        await UserDAO(session_with_commit).add(user_schema)
        await message.answer(
            get_text('start'), reply_markup=MainKeyboard.build(user_schema.role)
        )
        return
    await message.answer(
        get_text('start'), reply_markup=MainKeyboard.build(user_info.role)
    )