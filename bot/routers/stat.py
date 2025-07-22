from aiogram import Router, F
from aiogram.types import Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from bot.common.func.func import determine_rank
from bot.common.kbds.markup.main_kb import MainKeyboard
from bot.db.dao import AnalisisDAO, DetailedAnalysisDAO
from bot.db.models import DetailedAnalysis

stat_router = Router()


@stat_router.message(F.text == MainKeyboard.get_user_kb_text().get("my_stat"))
async def handle_user_statistics(
    message: Message, session_without_commit: AsyncSession
):
    try:
        async with session_without_commit.begin():
            user_id = message.from_user.id

            # Проверяем наличие детального анализа
            detailed_dao = DetailedAnalysisDAO(session_without_commit)
            count_query = (
                select(func.count())
                .select_from(DetailedAnalysis)
                .where(DetailedAnalysis.user_id == user_id)
            )
            detailed_count = await session_without_commit.scalar(count_query)

            # Получаем статистику
            basic_dao = AnalisisDAO(session_without_commit)
            basic_averages = await basic_dao.get_average_analysis_by_user(user_id)
            basic_rank = determine_rank(float(basic_averages["pr"]))

            basic_statistics = (
                f"<b>📊 XG Stats:</b>\n\n"
                f"<b>Average Mistakes:</b> {float(basic_averages['mistake_total']):.1f}\n"
                f"<b>Average Doubling Errors:</b> {float(basic_averages['mistake_doubling']):.1f}\n"
                f"<b>Average Take Errors:</b> {float(basic_averages['mistake_taking']):.1f}\n"
                f"<b>Average Luck:</b> {float(basic_averages['luck']):.1f}\n"
                f"<b>Average Game Quality (PR):</b> {float(basic_averages['pr']):.1f}\n"
                f"<b>Your Rank:</b> {basic_rank}\n"
            )

            # Если есть детальный анализ, показываем его
            if detailed_count > 0:
                detailed_averages = await detailed_dao.get_average_analysis_by_user(
                    user_id
                )
                detailed_rank = determine_rank(
                    float(detailed_averages["snowie_error_rate"])
                )

                detailed_statistics = (
                    f"<b>🎯 Gnu({detailed_count} games):</b>\n\n"
                    f"<b>Playing checkers:</b>\n"
                    f"├ Total Marked Moves: {detailed_averages['moves_marked_bad'] + detailed_averages['moves_marked_very_bad']:.1f}\n"  # Approx. total moves
                    f"├ Bad Moves: {detailed_averages['moves_marked_bad']:.1f}\n"
                    f"└ Very Bad Moves: {detailed_averages['moves_marked_very_bad']:.1f}\n\n"
                    f"<b>Luck:</b>\n"
                    f"├ Very Lucky: {detailed_averages['rolls_marked_very_lucky']:.1f}\n"
                    f"├ Lucky: {detailed_averages['rolls_marked_lucky']:.1f}\n"
                    f"├ Unlucky: {detailed_averages['rolls_marked_unlucky']:.1f}\n"
                    f"└ Very Unlucky: {detailed_averages['rolls_marked_very_unlucky']:.1f}\n\n"
                    f"<b>Overall Stats:</b>\n"
                    f"├ Error Rate: {detailed_averages['snowie_error_rate']:.1f}\n"
                    f"\n<b>Your Rank:</b> {detailed_rank}"
                )

        await message.answer(basic_statistics, parse_mode="HTML")
        if detailed_count > 0:
            await message.answer(detailed_statistics, parse_mode="HTML")

    except Exception as e:
        logger.error(
            f"Error retrieving statistics for user {message.from_user.id}: {e}"
        )
        await message.answer("There was an error retrieving your statistics.")
