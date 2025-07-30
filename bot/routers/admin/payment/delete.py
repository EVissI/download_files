from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext

from bot.common.general_states import GeneralStates
from bot.common.kbds.inline.paginate import (
    AnalizePaymentCallback,
    get_analize_payments_kb,
)
from bot.common.kbds.markup.payment_kb import PaymentKeyboard
from bot.db.dao import AnalizePaymentDAO
from bot.db.schemas import SAnalizePayment

delete_payment_router = Router()


@delete_payment_router.message(
    F.text == PaymentKeyboard.get_kb_text()["delete"],
    StateFilter(GeneralStates.payment_view),
)
async def handle_delete_payment(
    message: Message, state: FSMContext, session_without_commit: AsyncSession
):
    """
    Handles the delete payment command in the payment view state.
    """
    dao = AnalizePaymentDAO(session_without_commit)
    payment_packages = await dao.find_all(SAnalizePayment(is_active=True))
    if not payment_packages:
        await message.answer("Нет доступных пакетов для удаления.")
        await state.set_state(GeneralStates.payment_view)
        return
    await message.answer(
        "Выберите пакет для удаления:",
        reply_markup=get_analize_payments_kb(payment_packages, context="delete"),
    )


@delete_payment_router.callback_query(
    AnalizePaymentCallback.filter(((F.action == "select") & (F.context == "delete")))
)
async def handle_delete_payment_select(
    callback: CallbackQuery,
    callback_data: AnalizePaymentCallback,
    session_without_commit: AsyncSession,
):
    """
    Handles the selection of a payment package for deletion (деактивация).
    """
    await callback.message.delete()
    dao = AnalizePaymentDAO(session_without_commit)
    payment_package = await dao.find_one_or_none_by_id(callback_data.payment_id)

    if not payment_package:
        await callback.message.answer("Пакет не найден.")
        return

    success = await dao.deactivate(payment_package.id)
    if success:
        await callback.message.answer(
            f"Пакет '{payment_package.name}' успешно деактивирован.",
            reply_markup=PaymentKeyboard.build(),
        )
        await session_without_commit.commit()
    else:
        await callback.message.answer(
            "Ошибка при деактивации пакета.", reply_markup=PaymentKeyboard.build()
        )
        await session_without_commit.rollback()
