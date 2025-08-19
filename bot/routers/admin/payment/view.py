from aiogram import Router, F
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
    payments = await payments_dao.get_active_payments()
    payments_activate = UserAnalizePaymentDAO(session_without_commit)
    if not payments:
        await message.answer("Нет доступных пакетов для покупки.")
        return
    for payment in payments:
        # Формируем список услуг и их количества
        services_text = "\n".join(
            [
                f"- {service.service_type.value}: <b>{service.quantity if service.quantity is not None else '∞'}</b>"
                for service in payment.services
            ]
        )

        activates = await payments_activate.find_all(
            SUserAnalizePayment(analize_payment_id=payment.id)
        )
        activates_count = len(activates)

        text = (
            f"Название: <b>{payment.name}</b>\n"
            f"Услуги:\n{services_text}\n"
            f"Цена: <b>{payment.price}₽</b>\n"
            f"Активировано: <b>{activates_count}</b>\n"
            f"Срок действия: <b>{payment.duration_days if payment.duration_days is not None else '∞'}</b> дней\n"
        )
        await message.answer(
            text, parse_mode="HTML", reply_markup=PaymentKeyboard.build()
        )
