from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, PreCheckoutQuery
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from bot.common.kbds.inline.paginate import AnalizePaymentCallback, get_analize_payments_kb
from bot.common.kbds.inline.profile import ProfileCallback
from bot.config import translator_hub
from typing import TYPE_CHECKING
from fluentogram import TranslatorRunner
from bot.common.utils.i18n import get_all_locales_for_key
from bot.db.dao import AnalizePaymentDAO, UserDAO
from bot.config import settings
from bot.db.models import User, UserAnalizePayment
from bot.db.schemas import SAnalizePayment

if TYPE_CHECKING:
    from locales.stub import TranslatorRunner

payment_router = Router()

@payment_router.callback_query(ProfileCallback.filter(F.action == "payment"))
async def handle_payment(callback: CallbackQuery, i18n: TranslatorRunner, session_without_commit: AsyncSession):
    await callback.message.delete()
    payment_packages = await AnalizePaymentDAO(session_without_commit).find_all(SAnalizePayment(is_active=True))
    await callback.message.answer(
        i18n.user.profile.payment_text(),
        reply_markup=get_analize_payments_kb(payment_packages, context='payment')
    )

@payment_router.callback_query(AnalizePaymentCallback.filter(F.action.in_(["prev", "next"])))
async def handle_payment_paginate(callback: CallbackQuery, callback_data: AnalizePaymentCallback, i18n: TranslatorRunner, session_without_commit: AsyncSession):
    payment_packages = await AnalizePaymentDAO(session_without_commit).find_all(SAnalizePayment(is_active=True))
    await callback.message.edit_reply_markup(
        reply_markup=get_analize_payments_kb(payment_packages, page=callback_data.page, context=callback_data.context)
    )

@payment_router.callback_query(AnalizePaymentCallback.filter((F.action == "select") & (F.context == 'payment')))
async def handle_payment_select(callback: CallbackQuery, callback_data: AnalizePaymentCallback, i18n: TranslatorRunner, session_without_commit: AsyncSession):
    payment = await AnalizePaymentDAO(session_without_commit).find_one_or_none_by_id(callback_data.payment_id)
    if not payment:
        await callback.answer(i18n.user.profile.payment_not_found(), show_alert=True)
        return
    
    # Validate payment price
    if not isinstance(payment.price, (int, float)) or payment.price <= 0:
        logger.error(f"Invalid payment price for payment ID {payment.id}: {payment.price}")
        return
    
    amount = int(payment.price * 100)  # Convert to kopecks and ensure integer
    logger.debug(f"Sending invoice for payment ID {payment.id}, price: {payment.price} RUB, amount: {amount} kopecks")

    await callback.message.delete()
    await callback.bot.send_invoice(
        chat_id=callback.from_user.id,
        title=payment.name,
        description="Покупка пакета для автоматического анализа",
        payload=f"autoanalyze_{payment.id}",
        provider_token=settings.YO_KASSA_TEL_API_KEY,
        currency="RUB",
        prices=[{"label": "Руб", "amount": amount}],
    )

@payment_router.pre_checkout_query()
async def process_pre_check_out_query(
    pre_checkout_query: PreCheckoutQuery
):  
    await pre_checkout_query.bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@payment_router.message(F.successful_payment)
async def process_successful_payment(message: Message, i18n: TranslatorRunner, session_without_commit: AsyncSession):
    payment = message.successful_payment
    payload = payment.invoice_payload
    if not payload.startswith("autoanalyze_"):
        await message.answer(i18n.user.profile.payment_invalid_payload(), reply_markup=None)
        return
    try:
        # Получаем id пакета из payload
        payment_id = int(payload.replace("autoanalyze_", ""))
        # Получаем пакет
        payment_package = await AnalizePaymentDAO(session_without_commit).find_one_or_none_by_id(payment_id)
        if not payment_package:
            await message.answer(i18n.user.profile.payment_not_found(), reply_markup=None)
            return

        # Create UserAnalizePayment with current_analize_balance
        user_payment = UserAnalizePayment(
            user_id=message.from_user.id,
            analize_payment_id=payment_package.id,
            current_analize_balance=payment_package.amount,
            tranzaction_id=payment.provider_payment_charge_id
        )
        session_without_commit.add(user_payment)

        await message.answer(
            i18n.user.profile.payment_success(
                amount=payment_package.amount,
                name=payment_package.name
            ),
            reply_markup=None
        )
        await session_without_commit.commit()
    except Exception as e:
        await session_without_commit.rollback()
        await message.answer(i18n.user.profile.payment_error(), reply_markup=None)
        logger.error(f"Ошибка при обработке успешной оплаты: {e}")