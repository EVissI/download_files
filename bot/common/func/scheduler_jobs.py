"""Безопасная регистрация задач APScheduler (общая таблица apscheduler_jobs)."""

from __future__ import annotations

from typing import Any

from apscheduler.jobstores.base import JobLookupError
from loguru import logger

from bot.config import scheduler


def upsert_scheduler_job(
    func,
    trigger,
    job_id: str,
    **job_kwargs: Any,
) -> None:
    """
    Создаёт или обновляет job в SQLAlchemyJobStore.
    Сначала удаляет запись с тем же id — иначе возможен duplicate key при рестарте.
    """
    for jobstore in scheduler._jobstores.values():
        try:
            jobstore.remove_job(job_id)
        except JobLookupError:
            pass
        except Exception as exc:
            logger.warning("Could not remove scheduler job {} from store: {}", job_id, exc)

    scheduler.add_job(
        func,
        trigger,
        id=job_id,
        replace_existing=True,
        **job_kwargs,
    )
