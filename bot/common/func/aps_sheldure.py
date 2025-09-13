from loguru import logger
from bot.common.tasks.gift import check_and_notify_gift
from bot.db.dao import MessageForNewDAO
from bot.db.database import async_session_maker
from apscheduler.triggers.cron import CronTrigger
from bot.config import scheduler
from bot.db.models import MessageForNew

async def schedule_gift_job_from_db():
    """
    Читает расписание рассылки из базы и добавляет/обновляет задачу 'gift_notification'.
    Если в БД нет настроек — задача не создаётся.
    """
    try:
        async with async_session_maker() as session:
            message_dao = MessageForNewDAO(session)
            result:MessageForNew = message_dao.get_by_lang_code('en')
            if result is None:
                return
            dispatch_day = result.dispatch_day
            dispatch_time = result.dispatch_time
            if dispatch_day and dispatch_time:
                hour, minute = map(int, dispatch_time.split(":"))
                scheduler.add_job(
                    check_and_notify_gift,
                    CronTrigger(day_of_week=dispatch_day, hour=hour, minute=minute),
                    id="gift_notification",
                    replace_existing=True,
                )
    except Exception as e:
        logger.error(f"Ошибка при загрузке расписания рассылки из БД: {e}")