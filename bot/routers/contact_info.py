from aiogram import Router, F
from aiogram.types import CallbackQuery,Message
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter

from sqlalchemy.ext.asyncio import AsyncSession
from bot.common.filters.user_info import UserInfo
from bot.common.func.validators import EmailValidator
from bot.common.kbds.inline.contact_info import build_contact_info_keyboard
from bot.common.kbds.markup.cancel import get_cancel_kb
from bot.common.kbds.markup.main_kb import MainKeyboard
from bot.common.kbds.markup.request_phone import get_contatct_request
from bot.db.dao import UserDAO
from typing import TYPE_CHECKING
from bot.config import translator_hub
from fluentogram import TranslatorRunner
from bot.common.utils.i18n import get_all_locales_for_key
from bot.db.models import User
if TYPE_CHECKING:
    from locales.stub import TranslatorRunner


class ShareContactDialog(StatesGroup):
    phone = State()
    email = State() 

contact_router = Router()

@contact_router.callback_query(F.data.startswith("contact:"))
async def handle_contact_action(
    callback: CallbackQuery,
    callback_data: str,
    state: FSMContext,
    i18n: TranslatorRunner
):

    action = callback_data.split(":")[1]

    if action == "phone":
        await callback.answer(i18n.user.static.phone_request_sent(), reply_markup=get_contatct_request(i18n))
        state.set_state(ShareContactDialog.phone)
    elif action == "email":
        await callback.message.answer(i18n.user.static.enter_email(),reply_markup=get_cancel_kb(i18n))
        state.set_state(ShareContactDialog.email)

    await callback.message.delete()

@contact_router.message(F.text.in_(get_all_locales_for_key(translator_hub, "keyboard-reply-cancel")), StateFilter(ShareContactDialog), UserInfo())
async def cancel_contact_share(
    message: Message,
    state: FSMContext,
    user_info: User,
    i18n: TranslatorRunner
):
    """
    Handles the cancel action in the contact sharing dialog.
    """
    await state.clear()
    await message.answer(
        message.text,
        reply_markup=MainKeyboard.build(user_role=user_info.role, i18n=i18n),
    )

@contact_router.message(F.contact, StateFilter(ShareContactDialog.phone), UserInfo())
async def handle_phone_share(
    message: Message,   
    state: FSMContext,
    user_info: User,
    session_without_commit: AsyncSession,
    i18n: TranslatorRunner
):
    """
    Handles the phone number sharing.
    """
    contact = message.contact
    if contact is None:
        await message.answer(
            i18n.user.static.missing_contact_info(),
            reply_markup=build_contact_info_keyboard(
                session=session_without_commit,
                user_id=user_info.id,
                i18n=i18n
            )
        )
        return
    user_dao = UserDAO(session_without_commit)
    user = await user_dao.find_one_or_none_by_id(user_info.id)
    await user_dao.update(user.id, {'phone_number':contact.phone_number})
    if not user.email:
        await message.answer(
            i18n.user.static.missing_contact_info(),
            reply_markup=build_contact_info_keyboard(
                session=session_without_commit,
                user_id=user_info.id,
                i18n=i18n
            )
        )
    else:
        await message.answer(
            i18n.user.static.contact_info_shared(),
            reply_markup=MainKeyboard.build(user_role=user_info.role, i18n=i18n)
        )
    await state.clear()
    await session_without_commit.commit()


@contact_router.message(F.text, StateFilter(ShareContactDialog.email), UserInfo())
async def handle_email_share(
    message: Message,
    state: FSMContext,
    user_info: User,
    session_without_commit: AsyncSession,
    i18n: TranslatorRunner
):
    """
    Handles the email sharing.
    """
    email = message.text.strip()
    is_valid, status = EmailValidator.validate(email)
    if not is_valid:
        await message.answer(i18n.user.static.invalid_email_format())
        return
    user_dao = UserDAO(session_without_commit)
    user = await user_dao.find_one_or_none_by_id(user_info.id)
    await user_dao.update(user.id, {'email': email})
    if not user.phone_number:
        await message.answer(
            i18n.user.static.missing_contact_info(),
            reply_markup=build_contact_info_keyboard(
                session=session_without_commit,
                user_id=user_info.id,
                i18n=i18n
            )
        )
    else:
        await message.answer(
            i18n.user.static.contact_info_shared(),
            reply_markup=MainKeyboard.build(user_role=user_info.role, i18n=i18n)
        )
    await state.clear()
    await session_without_commit.commit()