"""Расписание автодобавления анализов матча в папки кабинета."""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from loguru import logger
from sqlalchemy import select

from bot.common.tasks.folder_schedule import (
    normalize_weekdays,
    validate_issue_time_msk,
)
from bot.config import scheduler
from bot.db.database import async_session_maker
from bot.db.models import MatchAnalysis, MatchAnalysisFolderSchedule


def ma_folder_schedule_job_id(schedule_id: int) -> str:
    return f"match_analysis_folder_schedule:{schedule_id}"


def upsert_ma_folder_schedule_job(schedule: MatchAnalysisFolderSchedule) -> None:
    if not schedule.is_active:
        remove_ma_folder_schedule_job(schedule, clear_job_id=False)
        schedule.scheduler_job_id = None
        return

    if not getattr(scheduler, "running", False):
        raise RuntimeError(
            "Планировщик APScheduler не запущен. "
            "Запустите API/бот с активным scheduler.start()."
        )

    validate_issue_time_msk(schedule.issue_time_msk)
    weekdays = normalize_weekdays(schedule.weekdays)
    schedule.weekdays = weekdays
    hour, minute = map(int, schedule.issue_time_msk.split(":"))
    job_id = schedule.scheduler_job_id or ma_folder_schedule_job_id(schedule.id)
    scheduler.add_job(
        run_match_analysis_folder_schedule,
        "cron",
        day_of_week=",".join(weekdays),
        hour=hour,
        minute=minute,
        timezone=ZoneInfo("Europe/Moscow"),
        id=job_id,
        replace_existing=True,
        args=[schedule.id],
        coalesce=True,
        max_instances=1,
        misfire_grace_time=3600,
    )
    schedule.scheduler_job_id = job_id


def remove_ma_folder_schedule_job(
    schedule: MatchAnalysisFolderSchedule,
    *,
    clear_job_id: bool = True,
) -> None:
    job_id = str(schedule.scheduler_job_id or "").strip()
    if not job_id:
        if clear_job_id:
            schedule.scheduler_job_id = None
        return
    job = scheduler.get_job(job_id)
    if job:
        scheduler.remove_job(job_id)
    if clear_job_id:
        schedule.scheduler_job_id = None


async def run_match_analysis_folder_schedule(schedule_id: int) -> None:
    """
    Добавляет анализы матча в папку по расписанию:
    по возрастанию ID, пропуская уже добавленные; не более items_per_run.
    """
    async with async_session_maker() as session:
        try:
            schedule = await session.get(MatchAnalysisFolderSchedule, schedule_id)
            if not schedule:
                logger.warning("MA folder schedule {} not found", schedule_id)
                return
            if not schedule.is_active:
                logger.info("MA folder schedule {} is inactive, skip", schedule_id)
                return

            folder_id = int(schedule.folder_id)
            items_per_run = max(1, int(schedule.items_per_run))

            from bot.db.dao import MatchAnalysisFolderDAO

            folder_dao = MatchAnalysisFolderDAO(session)
            folder = await folder_dao.get_folder_by_id(folder_id)
            if not folder:
                logger.warning(
                    "MA folder schedule {} target folder {} not found",
                    schedule_id,
                    folder_id,
                )
                return

            all_ids_result = await session.execute(
                select(MatchAnalysis.id).order_by(MatchAnalysis.id.asc())
            )
            all_match_ids = [
                int(mid)
                for mid in all_ids_result.scalars().all()
                if mid is not None
            ]
            if not all_match_ids:
                schedule.last_run_at = datetime.now(timezone.utc)
                await session.commit()
                return

            existing_ids = set(await folder_dao.get_folder_match_ids(folder_id))
            to_add_ids: list[int] = []
            for mid in all_match_ids:
                if mid in existing_ids:
                    continue
                to_add_ids.append(mid)
                if len(to_add_ids) >= items_per_run:
                    break

            if not to_add_ids:
                schedule.last_run_at = datetime.now(timezone.utc)
                await session.commit()
                return

            added = await folder_dao.add_matches_to_folder(folder_id, to_add_ids)
            schedule.last_run_at = datetime.now(timezone.utc)
            await session.commit()
            logger.info(
                "MA folder schedule {} added {} matches to folder {}",
                schedule_id,
                added,
                folder_id,
            )
        except Exception as exc:
            await session.rollback()
            logger.exception(
                "MA folder schedule {} failed: {}",
                schedule_id,
                exc,
            )
