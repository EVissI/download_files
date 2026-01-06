"""
Фоновая задача для проверки уведомлений мониторинга.
Проверяет очереди RQ и отправляет уведомления админам при достижении порога.
"""

from redis import Redis
from rq import Queue
from rq.registry import StartedJobRegistry
from bot.config import settings, bot, admins
from bot.db.redis import sync_redis_client
from loguru import logger


async def check_for_user(admin_id: int, threshold: int):
    """
    Проверяет total_active для конкретного админа и отправляет уведомление,
    если значение совпадает. Устанавливает cooldown 10 минут после отправки.
    """
    try:
        redis_conn = Redis.from_url(settings.REDIS_URL, decode_responses=False)
        queue_names = ["backgammon_analysis", "backgammon_batch_analysis"]

        total_active = 0
        for qname in queue_names:
            q = Queue(qname, connection=redis_conn)
            registry = StartedJobRegistry(queue=q)
            total_active += len(registry)

        cooldown_key = f"monitor:notification:cooldown:{admin_id}"
        if sync_redis_client.exists(cooldown_key):
            return

        if total_active >= threshold:
            try:
                await bot.send_message(
                    chat_id=admin_id,
                    text=f"🔔 Мониторинг: кол-во активных воркеров достигло {threshold}!",
                )
                logger.info(
                    f"Monitor notification sent to {admin_id}: total_active={total_active}"
                )
                sync_redis_client.set(cooldown_key, "1", ex=600)
            except Exception as e:
                logger.error(f"Failed to send notification to {admin_id}: {e}")
    except Exception as e:
        logger.exception(f"Error in check_for_user for {admin_id}: {e}")
