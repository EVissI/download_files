import os
import sys
import logging
from redis import Redis  # ✅ ИСПРАВЛЕНО
from rq import Worker, Queue  # ✅ Убран Connection
from bot.common.func.hint_viewer import process_mat_file

# Логирование
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Подключение к Redis
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', None)

logger.info(f"Connecting to Redis at {REDIS_HOST}:{REDIS_PORT}")

redis_conn = Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    password=REDIS_PASSWORD,
    decode_responses=True
)

def analyze_backgammon_job(mat_path: str, json_path: str, user_id: str):
    """Анализирует один .mat файл"""
    try:
        logger.info(f"[Job Start] mat_path={mat_path}, user_id={user_id}")
        
        process_mat_file(mat_path, json_path, user_id)
        
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
        logger.info(f"✅ Connected to Redis: {REDIS_HOST}:{REDIS_PORT}")
    except Exception as e:
        logger.error(f"❌ Failed to connect to Redis: {e}")
        sys.exit(1)
    
    # ✅ ИСПРАВЛЕНО: убран with Connection(...)
    try:
        queue = Queue('backgammon_analysis', connection=redis_conn)
        worker = Worker([queue])
        logger.info(f"🚀 Starting Worker (connected to {REDIS_HOST})...")
        worker.work()
    except Exception as e:
        logger.exception("Worker crashed")
        sys.exit(1)