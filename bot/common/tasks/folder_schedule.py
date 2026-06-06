from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from loguru import logger
from sqlalchemy import select

from bot.config import scheduler
from bot.db.database import async_session_maker
from bot.db.models import ContentCard, ContentCardFolderSchedule


WEEKDAY_CHOICES = [
    ("mon", "Понедельник"),
    ("tue", "Вторник"),
    ("wed", "Среда"),
    ("thu", "Четверг"),
    ("fri", "Пятница"),
    ("sat", "Суббота"),
    ("sun", "Воскресенье"),
]
WEEKDAY_ORDER = {day: idx for idx, (day, _title) in enumerate(WEEKDAY_CHOICES)}


def normalize_weekdays(raw_weekdays: list[str] | None) -> list[str]:
    allowed = set(WEEKDAY_ORDER.keys())
    out: list[str] = []
    for day in raw_weekdays or []:
        day_text = str(day or "").strip().lower()
        if day_text not in allowed:
            continue
        out.append(day_text)
    if not out:
        raise ValueError("Нужно выбрать хотя бы один день недели.")
    return sorted(set(out), key=lambda day: WEEKDAY_ORDER[day])


def validate_issue_time_msk(value: str) -> None:
    try:
        hour, minute = map(int, str(value).split(":"))
    except Exception as exc:
        raise ValueError("Некорректное время. Используйте формат ЧЧ:ММ.") from exc
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        raise ValueError("Некорректное время. Используйте диапазон 00:00-23:59.")


def normalize_labels(raw_labels: list[str] | None) -> list[str]:
    """Пустой список — без фильтра по меткам (все карточки)."""
    out: list[str] = []
    seen: set[str] = set()
    for item in raw_labels or []:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def folder_schedule_job_id(schedule_id: int) -> str:
    return f"content_card_folder_schedule:{schedule_id}"


def upsert_folder_schedule_job(schedule: ContentCardFolderSchedule) -> None:
    if not schedule.is_active:
        remove_folder_schedule_job(schedule, clear_job_id=False)
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
    job_id = schedule.scheduler_job_id or folder_schedule_job_id(schedule.id)
    scheduler.add_job(
        run_content_card_folder_schedule,
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


def remove_folder_schedule_job(
    schedule: ContentCardFolderSchedule,
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


async def run_content_card_folder_schedule(schedule_id: int) -> None:
    """
    Добавляет карточки в папку по расписанию:
    - с выбранными метками или из всего пула, если метки не заданы;
    - по возрастанию ID, пропуская уже добавленные в папку;
    - не более cards_per_run за запуск.
    """
    async with async_session_maker() as session:
        try:
            schedule = await session.get(ContentCardFolderSchedule, schedule_id)
            if not schedule:
                logger.warning("Folder schedule {} not found", schedule_id)
                return
            if not schedule.is_active:
                logger.info("Folder schedule {} is inactive, skip", schedule_id)
                return

            folder_id = int(schedule.folder_id)
            cards_per_run = max(1, int(schedule.cards_per_run))
            filter_labels = normalize_labels(schedule.labels)

            from bot.db.dao import ContentCardFolderDAO

            folder_dao = ContentCardFolderDAO(session)
            folder = await folder_dao.get_folder_by_id(folder_id)
            if not folder:
                logger.warning(
                    "Folder schedule {} target folder {} not found",
                    schedule_id,
                    folder_id,
                )
                return

            card_ids_query = select(ContentCard.id).order_by(ContentCard.id.asc())
            if filter_labels:
                card_ids_query = card_ids_query.where(
                    ContentCard.labels.isnot(None),
                    ContentCard.labels.overlap(filter_labels),
                )
            all_card_ids_result = await session.execute(card_ids_query)
            all_card_ids = [
                int(card_id)
                for card_id in all_card_ids_result.scalars().all()
                if card_id is not None
            ]
            if not all_card_ids:
                schedule.last_run_at = datetime.now(timezone.utc)
                await session.commit()
                return

            existing_card_ids = set(await folder_dao.get_folder_card_ids(folder_id))
            to_add_ids: list[int] = []
            for card_id in all_card_ids:
                if card_id in existing_card_ids:
                    continue
                to_add_ids.append(card_id)
                if len(to_add_ids) >= cards_per_run:
                    break

            if not to_add_ids:
                schedule.last_run_at = datetime.now(timezone.utc)
                await session.commit()
                return

            added = await folder_dao.add_cards_to_folder(folder_id, to_add_ids)
            schedule.last_run_at = datetime.now(timezone.utc)
            await session.commit()
            logger.info(
                "Folder schedule {} added {} cards to folder {}",
                schedule_id,
                added,
                folder_id,
            )
        except Exception as exc:
            await session.rollback()
            logger.exception(
                "Folder schedule {} failed: {}",
                schedule_id,
                exc,
            )
