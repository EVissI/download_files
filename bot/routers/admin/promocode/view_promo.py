from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext

from bot.common.general_states import GeneralStates
from bot.common.kbds.markup.promo_code import PromoKeyboard
from bot.db.dao import PromoCodeDAO

view_promo_router = Router()

@view_promo_router.message(F.text == PromoKeyboard.get_kb_text()['view_promo'], StateFilter(GeneralStates.promo_view))
async def view_active_promos(message: Message, session_without_commit):
    dao = PromoCodeDAO(session_without_commit)
    promo_codes = await dao.get_active_promo_codes()
    if not promo_codes:
        await message.answer("Нет активных промокодов.")
        return
    text = "<b>Активные промокоды:</b>\n"
    for promo in promo_codes:
        text = (
            f"Код: <code>{promo.code}</code>\n"
            f"Дней: {promo.discount_days}\n"
            f"Максимум использований: {promo.max_usage if promo.max_usage is not None else '∞'}\n"
            f"Активировано: {promo.activate_count or 0}\n"
            f"Статус: {'Активен' if promo.is_active else 'Неактивен'}\n"
        )
        await message.answer(text, parse_mode="HTML", reply_markup=PromoKeyboard.build())