import os
import sys
import logging
from redis import Redis  # ✅ Правильный импорт
from rq import Worker, Queue  # ✅ БЕЗ Connection
from bot.common.func.hint_viewer import process_mat_file
from bot.common.service.sync_folder_service import SyncthingSync

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


syncthing_sync = SyncthingSync()  # ← Глобальный экземпляр

def analyze_backgammon_job(mat_path: str, json_path: str, user_id: str):
    """ .mat worker- . """
    try:
        logger.info(f"Job Start matpath={mat_path}, userid={user_id}")
        
        process_mat_file(mat_path, json_path, user_id)
        
        logger.info(f"Starting Syncthing sync for {mat_path}")
        sync_success = syncthing_sync.sync_and_wait(max_wait=30)
        if not sync_success:
            logger.warning(f"Syncthing sync failed/timeout for {mat_path}")
        gamesdir = json_path.rsplit('.', 1)[0] + '/games'
        has_games = (os.path.exists(gamesdir) and 
                   any(f.endswith('.json') for f in os.listdir(gamesdir)))
        
        logger.info(f"Job Completed matpath={mat_path} -> jsonpath={json_path} hasgames={has_games}")
        
        return {
            "status": "success",
            "mat_path": mat_path,
            "json_path": json_path,
            "games_dir": gamesdir,
            "has_games": has_games,
            'syncthing_sync': sync_success
        }
        
    except Exception as e:
        logger.exception(f"Job Failed matpath={mat_path}")
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