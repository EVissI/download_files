from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext

from bot.common.general_states import GeneralStates
from bot.common.kbds.markup.payment_kb import PaymentKeyboard
from bot.db.dao import AnalizePaymentDAO
from bot.db.schemas import SAnalizePayment

view_payment_router = Router()


@view_payment_router.message(
    F.text == PaymentKeyboard.get_kb_text()["view"],
    StateFilter(GeneralStates.payment_view),
)
async def view_active_payments(message: Message, session_without_commit):
    dao = AnalizePaymentDAO(session_without_commit)
    payments = await dao.find_all(SAnalizePayment(is_active=True))
    if not payments:
        await message.answer("Нет доступных пакетов для покупки.")
        return
    for payment in payments:
        text = (
            f"Название: <b>{payment.name}</b>\n"
            f"Количество анализов: <b>{payment.amount if payment.amount is not None else '∞'}</b>\n"
            f"Цена: <b>{payment.price}₽</b>\n"
            f"Срок действия: <b>{payment.duration_days if payment.duration_days is not None else '∞'}</b> дней\n"
        )
        await message.answer(
            text, parse_mode="HTML", reply_markup=PaymentKeyboard.build()
        )
