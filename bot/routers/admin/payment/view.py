﻿from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext

from bot.common.general_states import GeneralStates
from bot.common.kbds.markup.payment_kb import PaymentKeyboard
from bot.db.dao import AnalizePaymentDAO, UserAnalizePaymentDAO
from bot.db.schemas import SAnalizePayment, SUserAnalizePayment

view_payment_router = Router()


@view_payment_router.message(
    F.text == PaymentKeyboard.get_kb_text()["view"],
    StateFilter(GeneralStates.payment_view),
)
async def view_active_payments(message: Message, session_without_commit):
    payments_dao = AnalizePaymentDAO(session_without_commit)
    payments = await payments_dao.find_all(SAnalizePayment(is_active=True))
    payments_activate = UserAnalizePaymentDAO(session_without_commit)
    if not payments:
        await message.answer("Нет доступных пакетов для покупки.")
        return
    for payment in payments:
        activates = await payments_activate.find_all(SUserAnalizePayment(
            analize_payment_id=payment.id
        ))
        activates_count = len(activates)
        text = (
            f"Название: <b>{payment.name}</b>\n"
            f"Количество анализов: <b>{payment.amount if payment.amount is not None else '∞'}</b>\n"
            f"Цена: <b>{payment.price}₽</b>\n"
            f"Активировано: <b>{activates_count}</b>\n"
            f"Срок действия: <b>{payment.duration_days if payment.duration_days is not None else '∞'}</b> дней\n"
        )
        await message.answer(
            text, parse_mode="HTML", reply_markup=PaymentKeyboard.build()
        )
