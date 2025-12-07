import os
import sys
import logging
from redis import Redis  # ✅ Правильный импорт
from rq import Worker, Queue  # ✅ БЕЗ Connection
from bot.common.func.hint_viewer import process_mat_file

# Логирование
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ✅ Подключение к Redis с ACL-пользователем
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
REDIS_DB = int(os.getenv('REDIS_DB', 0))

# Два варианта подключения:
# 1. Если используешь ACL-пользователя
REDIS_USER = os.getenv('REDIS_USER')
REDIS_USER_PASSWORD = os.getenv('REDIS_USER_PASSWORD')

# 2. Если используешь default пароль
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD')

# Выбираем какой использовать
if REDIS_USER and REDIS_USER_PASSWORD:
    # С ACL-пользователем
    redis_url = f'redis://{REDIS_USER}:{REDIS_USER_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}'
    logger.info(f"Connecting to Redis with ACL user: {REDIS_USER}")
else:
    # С default пользователем (только пароль)
    redis_url = f'redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}'
    logger.info(f"Connecting to Redis with default user")

logger.info(f"Redis URL: redis://<user>:<pass>@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}")

redis_conn = Redis.from_url(redis_url, decode_responses=False)


def analyze_backgammon_job(mat_path: str, json_path: str, user_id: str):
    """
    Анализирует один .mat файл (запускается в worker-е).
    
    Args:
        mat_path: Путь к исходному .mat файлу
        json_path: Путь для сохранения результата .json
        user_id: ID пользователя (для логирования)
    
    Returns:
        dict: Результат анализа (success/error)
    """
    try:
        logger.info(f"[Job Start] mat_path={mat_path}, user_id={user_id}")
        
        # Запускаем твою существующую функцию
        process_mat_file(mat_path, json_path, user_id)
        
        # Проверяем что результат создан
        games_dir = json_path.rsplit(".", 1)[0] + "_games"
        has_games = os.path.exists(games_dir) and any(
            f.endswith(".json") for f in os.listdir(games_dir)
        )
        
        logger.info(f"[Job Completed] {mat_path} -> {json_path} (has_games={has_games})")
        
        return {
            "status": "success",
            "mat_path": mat_path,
            "json_path": json_path,
            "games_dir": games_dir,
            "has_games": has_games
        }
        
    except Exception as e:
        logger.exception(f"[Job Failed] {mat_path}")
        return {
            "status": "error",
            "error": str(e),
            "mat_path": mat_path
        }


if __name__ == '__main__':
    try:
        redis_conn.ping()
        logger.info(f"✅ Connected to Redis: {REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}")
    except Exception as e:
        logger.error(f"❌ Failed to connect to Redis: {e}")
        sys.exit(1)

    # Queue и Worker используют тот же connection с decode_responses=False
    try:
        queue = Queue('backgammon_analysis', connection=redis_conn)
        worker = Worker([queue], connection=redis_conn)
        logger.info(f"🚀 Starting Worker on queue 'backgammon_analysis'...")
        worker.work()
    except Exception as e:
        logger.exception("Worker crashed with error")
        sys.exit(1)