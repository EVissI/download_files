from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext

from bot.common.general_states import GeneralStates
from bot.common.kbds.markup.promo_code import PromoKeyboard
from bot.db.dao import PromoCodeDAO

view_promo_router = Router()


@view_promo_router.message(
    F.text == PromoKeyboard.get_kb_text()["view_promo"],
    StateFilter(GeneralStates.promo_view),
)
async def view_active_promos(message: Message, session_without_commit):
    dao = PromoCodeDAO(session_without_commit)
    promo_codes = await dao.get_active_promo_codes()
    if not promo_codes:
        await message.answer("Нет активных промокодов.")
        return
    for promo in promo_codes:
        # Формируем список услуг и их количества
        services_text = "\n".join(
            [
                f"- {service.service_type.value}: <b>{service.quantity if service.quantity is not None else '∞'}</b>"
                for service in promo.services
            ]
        )

        text = (
            f"Код: <code>{promo.code}</code>\n"
            f"Услуги:\n{services_text}\n"
            f"Максимум использований: <b>{promo.max_usage if promo.max_usage is not None else '∞'}</b>\n"
            f"Срок действия: <b>{promo.duration_days if promo.duration_days is not None else '∞'}</b> дней\n"
            f"Активировано: <b>{promo.activate_count or 0}</b>\n"
            f"Статус: {'Активен' if promo.is_active else 'Неактивен'}\n"
        )
        await message.answer(
            text, parse_mode="HTML", reply_markup=PromoKeyboard.build()
        )
