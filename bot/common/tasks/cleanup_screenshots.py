import os
import shutil
import asyncio
from datetime import datetime, timedelta
from loguru import logger

from bot.config import settings


async def cleanup_screenshots():
    """
    Clean up screenshot buffers older than 1 hour.
    Runs every 30 minutes.
    """
    try:
        screenshots_dir = "files/screenshots"
        if not os.path.exists(screenshots_dir):
            return

        now = datetime.now()
        cutoff = now - timedelta(hours=1)

        for user_dir in os.listdir(screenshots_dir):
            user_path = os.path.join(screenshots_dir, user_dir)
            if os.path.isdir(user_path):
                # Check if directory is older than 1 hour
                mtime = datetime.fromtimestamp(os.path.getmtime(user_path))
                if mtime < cutoff:
                    shutil.rmtree(user_path)
                    logger.info(f"Cleaned up screenshot buffer for user {user_dir}")

    except Exception as e:
        logger.error(f"Error cleaning up screenshots: {e}")


# Schedule the task to run every 30 minutes
async def schedule_cleanup():
    while True:
        await asyncio.sleep(30 * 60)  # 30 minutes
        await cleanup_screenshots()
