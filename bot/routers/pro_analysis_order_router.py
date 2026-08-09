from aiogram import F, Router
from aiogram.types import CallbackQuery
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from bot.common.filters.user_info import UserInfo
from bot.common.func.pro_analysis_order import (
    delete_pro_order,
    fulfill_pro_order,
    load_pro_order,
)
from bot.common.kbds.inline.pro_analysis import PRO_ORDER_CALLBACK_PREFIX
from bot.db.models import User

pro_analysis_order_router = Router()


@pro_analysis_order_router.callback_query(
    F.data.startswith(PRO_ORDER_CALLBACK_PREFIX), UserInfo()
)
async def handle_pro_analysis_order(
    callback: CallbackQuery,
    user_info: User,
    session_without_commit: AsyncSession,
):
    request_id = (callback.data or "")[len(PRO_ORDER_CALLBACK_PREFIX) :].strip()
    if not request_id:
        await callback.answer("Заявка не найдена", show_alert=True)
        return

    order = await load_pro_order(request_id)
    if not order:
        await callback.answer(
            "Заявка устарела или уже отправлена", show_alert=True
        )
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        return

    if int(order.get("user_id") or 0) != int(callback.from_user.id):
        await callback.answer("Это не ваша заявка", show_alert=True)
        return

    await callback.answer("Отправляем админам…")
    try:
        await fulfill_pro_order(callback.bot, session_without_commit, order)
        await delete_pro_order(request_id)
    except FileNotFoundError:
        logger.warning(f"Pro order file missing request_id={request_id}")
        await callback.message.answer(
            "❌ Файл матча больше недоступен. Повторите анализ и закажите снова."
        )
        return
    except Exception as e:
        logger.exception(f"Pro order fulfill failed request_id={request_id}: {e}")
        await callback.message.answer(
            "❌ Не удалось отправить заказ админам. Попробуйте позже."
        )
        return

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    await callback.message.answer(
        "✅ Заявка отправлена профи. Администратор ответит вам в этом чате."
    )
