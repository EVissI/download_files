"""Расписание автодобавления файлов пользователя в папки веб-кабинета (ошибки / плеер)."""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from loguru import logger

from bot.common.tasks.folder_schedule import (
    normalize_labels,
    normalize_weekdays,
    validate_issue_time_msk,
)
from bot.config import scheduler
from bot.db.database import async_session_maker
from bot.db.models import HintWebFolder, HintWebFolderSchedule


def hint_web_folder_schedule_job_id(schedule_id: int) -> str:
    return f"hint_web_folder_schedule:{schedule_id}"


def upsert_hint_web_folder_schedule_job(schedule: HintWebFolderSchedule) -> None:
    if not schedule.is_active:
        remove_hint_web_folder_schedule_job(schedule, clear_job_id=False)
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
    job_id = schedule.scheduler_job_id or hint_web_folder_schedule_job_id(schedule.id)
    scheduler.add_job(
        run_hint_web_folder_schedule,
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


def remove_hint_web_folder_schedule_job(
    schedule: HintWebFolderSchedule,
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


async def run_hint_web_folder_schedule(schedule_id: int) -> None:
    """
    Добавляет файлы пользователя в папку по расписанию:
    - с выбранными метками или из всей истории сервиса, если метки не заданы;
    - по возрастанию ID, пропуская уже лежащие в папке;
    - не более files_per_run за запуск.
    """
    async with async_session_maker() as session:
        try:
            schedule = await session.get(HintWebFolderSchedule, schedule_id)
            if not schedule:
                logger.warning("Hint web folder schedule {} not found", schedule_id)
                return
            if not schedule.is_active:
                logger.info("Hint web folder schedule {} is inactive, skip", schedule_id)
                return

            folder_id = int(schedule.folder_id)
            files_per_run = max(1, int(schedule.files_per_run))
            filter_labels = normalize_labels(schedule.labels)

            from bot.db.dao import HintViewerWebUploadDAO, HintWebFolderDAO

            folder_dao = HintWebFolderDAO(session)
            folder = await session.get(HintWebFolder, folder_id)
            if not folder:
                logger.warning(
                    "Hint web folder schedule {} target folder {} not found",
                    schedule_id,
                    folder_id,
                )
                return

            upload_dao = HintViewerWebUploadDAO(session)
            all_upload_ids = await upload_dao.list_ids_for_schedule(
                user_id=int(folder.user_id),
                service=str(folder.service or "hints"),
                labels=filter_labels,
            )
            if not all_upload_ids:
                schedule.last_run_at = datetime.now(timezone.utc)
                await session.commit()
                return

            existing_ids = set(await folder_dao.get_folder_upload_ids(folder_id))
            to_add_ids: list[int] = []
            for upload_id in all_upload_ids:
                if upload_id in existing_ids:
                    continue
                to_add_ids.append(upload_id)
                if len(to_add_ids) >= files_per_run:
                    break

            if not to_add_ids:
                schedule.last_run_at = datetime.now(timezone.utc)
                await session.commit()
                return

            added = await folder_dao.add_uploads_to_folder(folder_id, to_add_ids)
            schedule.last_run_at = datetime.now(timezone.utc)
            await session.commit()
            logger.info(
                "Hint web folder schedule {} added {} files to folder {}",
                schedule_id,
                added,
                folder_id,
            )
        except Exception as exc:
            await session.rollback()
            logger.exception(
                "Hint web folder schedule {} failed: {}",
                schedule_id,
                exc,
            )
