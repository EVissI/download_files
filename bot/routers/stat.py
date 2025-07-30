from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from bot.common.filters.user_info import UserInfo
from bot.common.func.func import determine_rank, determine_rank_rate_chequer
from bot.common.kbds.inline.back import get_back_kb
from bot.common.kbds.inline.profile import ProfileCallback
from bot.common.kbds.markup.main_kb import MainKeyboard
from bot.db.dao import AnalisisDAO, DetailedAnalysisDAO
from bot.db.models import DetailedAnalysis, User

from typing import TYPE_CHECKING
from fluentogram import TranslatorRunner
from bot.common.utils.i18n import get_all_locales_for_key

if TYPE_CHECKING:
    from locales.stub import TranslatorRunner

stat_router = Router()


@stat_router.callback_query(ProfileCallback.filter(F.action == "stat"), UserInfo())
async def handle_user_statistics(
    callback: CallbackQuery,
    user_info: User,
    session_without_commit: AsyncSession,
    i18n: TranslatorRunner,
):
    try:
        user_id = callback.from_user.id

        detailed_dao = DetailedAnalysisDAO(session_without_commit)
        count_query = (
            select(func.count())
            .select_from(DetailedAnalysis)
            .where(DetailedAnalysis.user_id == user_id)
        )
        detailed_count = await session_without_commit.scalar(count_query)

        if detailed_count > 0:
            detailed_averages = await detailed_dao.get_average_analysis_by_user(user_id)
            detailed_rank_overall = determine_rank(
                float(detailed_averages["snowie_error_rate"]), i18n
            )
            detailed_rank_chequer = determine_rank(
                float(detailed_averages["error_rate_chequer"]), i18n
            )
            detailed_rank_cube = determine_rank(
                float(detailed_averages["cube_error_rate"]), i18n
            )

            # Форматируем значения
            def fmt(val):
                return "{:.1f}".format(float(val))

            detailed_statistics = i18n.user.profile.detailed_statistics(
                detailed_count=detailed_count,
                player_username=user_info.player_username or "Unknown",
                error_rate_chequer=fmt(detailed_averages["error_rate_chequer"]),
                detailed_rank_chequer=detailed_rank_chequer,
                rolls_marked_very_lucky=fmt(
                    detailed_averages["rolls_marked_very_lucky"]
                ),
                rolls_marked_lucky=fmt(detailed_averages["rolls_marked_lucky"]),
                rolls_marked_unlucky=fmt(detailed_averages["rolls_marked_unlucky"]),
                rolls_marked_very_unlucky=fmt(
                    detailed_averages["rolls_marked_very_unlucky"]
                ),
                snowie_error_rate=fmt(detailed_averages["snowie_error_rate"]),
                detailed_rank_overall=detailed_rank_overall,
                missed_doubles_below_cp=fmt(
                    detailed_averages["missed_doubles_below_cp"]
                ),
                missed_doubles_above_cp=fmt(
                    detailed_averages["missed_doubles_above_cp"]
                ),
                wrong_doubles_below_sp=fmt(detailed_averages["wrong_doubles_below_sp"]),
                wrong_doubles_above_tg=fmt(detailed_averages["wrong_doubles_above_tg"]),
                wrong_takes=fmt(detailed_averages["wrong_takes"]),
                wrong_passes=fmt(detailed_averages["wrong_passes"]),
                cube_error_rate=fmt(detailed_averages["cube_error_rate"]),
                detailed_rank_cube=detailed_rank_cube,
            )
            await callback.message.edit_text(
                detailed_statistics,
                parse_mode="HTML",
                reply_markup=get_back_kb(i18n, context="profile"),
            )
        else:
            await callback.answer(
                i18n.user.profile.no_detailed_statistics(), parse_mode="HTML"
            )

    except Exception as e:
        logger.error(
            f"Error retrieving statistics for user {callback.from_user.id}: {e}"
        )
        await callback.message.answer(i18n.user.profile.error_retrieving_statistics())
