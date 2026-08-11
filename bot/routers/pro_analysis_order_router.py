import os
import uuid

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from fluentogram import TranslatorRunner
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from bot.common.filters.user_info import UserInfo
from bot.common.func.pro_analysis_order import (
    delete_pro_order,
    fulfill_pro_order,
    load_pro_order,
)
from bot.common.kbds.inline.pro_analysis import (
    PRO_ANALYZE_CALLBACK_PREFIX,
    PRO_ORDER_CALLBACK_PREFIX,
    get_pro_analysis_admin_reply_kb,
)
from bot.config import settings
from bot.db.models import User

pro_analysis_order_router = Router()


def _is_pro_admin(user_info: User) -> bool:
    return (
        getattr(user_info, "role", None) == User.Role.ADMIN.value
        or int(user_info.id) in (settings.ROOT_ADMIN_IDS or [])
    )


@pro_analysis_order_router.callback_query(
    F.data.startswith(PRO_ORDER_CALLBACK_PREFIX), UserInfo()
)
async def handle_pro_analysis_order(
    callback: CallbackQuery,
    user_info: User,
    session_without_commit: AsyncSession,
    i18n: TranslatorRunner,
):
    request_id = (callback.data or "")[len(PRO_ORDER_CALLBACK_PREFIX) :].strip()
    if not request_id:
        await callback.answer(i18n.pro.analysis.order_not_found(), show_alert=True)
        return

    order = await load_pro_order(request_id)
    if not order:
        await callback.answer(
            i18n.pro.analysis.order_expired(), show_alert=True
        )
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        return

    if int(order.get("user_id") or 0) != int(callback.from_user.id):
        await callback.answer(i18n.pro.analysis.order_not_yours(), show_alert=True)
        return

    await callback.answer(i18n.pro.analysis.order_sending())
    try:
        await fulfill_pro_order(callback.bot, session_without_commit, order)
        await delete_pro_order(request_id)
    except FileNotFoundError:
        logger.warning(f"Pro order file missing request_id={request_id}")
        await callback.message.answer(i18n.pro.analysis.order_file_missing())
        return
    except Exception as e:
        logger.exception(f"Pro order fulfill failed request_id={request_id}: {e}")
        await callback.message.answer(i18n.pro.analysis.order_send_failed())
        return

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    await callback.message.answer(i18n.pro.analysis.order_sent())


@pro_analysis_order_router.callback_query(
    F.data.startswith(PRO_ANALYZE_CALLBACK_PREFIX), UserInfo()
)
async def handle_pro_admin_send_to_analysis(
    callback: CallbackQuery,
    user_info: User,
    state: FSMContext,
    session_without_commit: AsyncSession,
    i18n: TranslatorRunner,
):
    """Админ запускает hint_viewer для .mat из заказа эксперту."""
    if not _is_pro_admin(user_info):
        await callback.answer(
            i18n.pro.analysis.admin_analyze_forbidden(), show_alert=True
        )
        return

    raw_user_id = (callback.data or "")[len(PRO_ANALYZE_CALLBACK_PREFIX) :].strip()
    try:
        order_user_id = int(raw_user_id)
    except ValueError:
        order_user_id = 0

    doc = callback.message.document if callback.message else None
    if not doc:
        await callback.answer(
            i18n.pro.analysis.admin_no_document(), show_alert=True
        )
        return

    await callback.answer()

    from bot.routers.hint_viewer_router import start_hint_viewer_from_local_mat

    os.makedirs("files", exist_ok=True)
    fname = doc.file_name or "match.mat"
    if not str(fname).lower().endswith(".mat"):
        fname = f"{fname}.mat"
    local_mat = os.path.join(
        "files", f"pro_{callback.from_user.id}_{uuid.uuid4().hex[:8]}_{fname}"
    )

    try:
        file = await callback.bot.get_file(doc.file_id)
        with open(local_mat, "wb") as f:
            await callback.bot.download_file(file.file_path, f)

        job_id = await start_hint_viewer_from_local_mat(
            local_mat=local_mat,
            chat_id=callback.message.chat.id,
            user_info=user_info,
            state=state,
            session_without_commit=session_without_commit,
            i18n=i18n,
            bot_instance=callback.bot,
            username=callback.from_user.username,
        )
        if job_id and order_user_id:
            try:
                await callback.message.edit_reply_markup(
                    reply_markup=get_pro_analysis_admin_reply_kb(
                        order_user_id, i18n, with_analyze=False
                    )
                )
            except Exception:
                pass
    except Exception as e:
        logger.exception(f"Pro admin hint analyze failed: {e}")
        await callback.message.answer(f"❌ Ошибка при запуске анализа: {e}")
    finally:
        if os.path.isfile(local_mat):
            try:
                os.remove(local_mat)
            except OSError:
                pass
