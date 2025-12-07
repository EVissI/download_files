import requests
import asyncio
import os
from loguru import logger
from bot.config import settings
class SyncthingSync:
    """Управление синхронизацией Syncthing"""
    
    def __init__(self):
        self.api_key = settings.SYNCTHING_API_KEY
        self.host = os.getenv("SYNCTHING_HOST", "localhost:8384")
        self.folder_id = os.getenv("SYNCTHING_FOLDER", "backgammon-files")
        
        if not self.api_key:
            logger.warning("⚠️ SYNCTHING_API_KEY не установлен!")
        
        self.headers = {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json"
        }
        self.base_url = f"http://{self.host}/rest"
    
    async def sync_and_wait(self, max_wait=30) -> bool:
        """Синхронизировать и ждать завершения"""
        if not self.api_key:
            logger.warning("⚠️ Syncthing API ключ не установлен, пропускаю синхронизацию")
            return True  # Не блокировать обработку
        
        try:
            logger.info("🔄 Синхронизирую файлы Syncthing...")
            
            # 1. Запустить пересканирование
            response = requests.post(
                f"{self.base_url}/db/scan",
                params={"folder": self.folder_id},
                headers=self.headers,
                timeout=5
            )
            
            if response.status_code != 200:
                logger.warning(f"⚠️ Ошибка пересканирования: {response.status_code}")
                return False
            
            # 2. Ждём завершения
            import time
            start_time = time.time()
            
            while time.time() - start_time < max_wait:
                status_response = requests.get(
                    f"{self.base_url}/db/status",
                    params={"folder": self.folder_id},
                    headers=self.headers,
                    timeout=5
                )
                status = status_response.json()
                
                if not status.get("syncing", False) and status.get("state") == "idle":
                    files_in_sync = status.get("filesInSync", 0)
                    logger.info(f"✅ Синхронизация завершена ({files_in_sync} файлов)")
                    return True
                
                await asyncio.sleep(1)
            
            logger.warning(f"⚠️ Timeout синхронизации (max_wait={max_wait}s)")
            return False
            
        except Exception as e:
            logger.error(f"❌ Ошибка Syncthing: {e}")
            return False