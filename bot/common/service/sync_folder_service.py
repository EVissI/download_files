import asyncio
import aiohttp
from loguru import logger
from bot.config import settings

class SyncthingSync:
    """Управление синхронизацией Syncthing"""

    def __init__(self):
        self.api_key = settings.SYNCTHING_API_KEY
        self.host = settings.SYNCTHING_HOST
        self.folder_id = settings.SYNCTHING_FOLDER
        
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
            return True

        try:
            logger.info("🔄 Синхронизирую файлы Syncthing...")
            
            async with aiohttp.ClientSession() as session:
                # 1. Запустить пересканирование папки
                async with session.post(
                    f"{self.base_url}/db/scan",
                    params={"folder": self.folder_id},
                    headers=self.headers,
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    if response.status != 200:
                        logger.warning(f"⚠️ Ошибка пересканирования: {response.status}")
                        return False

                # 2. Ждём завершения синхронизации
                start_time = asyncio.get_event_loop().time()
                
                while asyncio.get_event_loop().time() - start_time < max_wait:
                    async with session.get(
                        f"{self.base_url}/db/status",
                        params={"folder": self.folder_id},
                        headers=self.headers,
                        timeout=aiohttp.ClientTimeout(total=5)
                    ) as status_response:
                        status = await status_response.json()
                        
                        # ✅ ИСПРАВЛЕНО: используем правильные поля
                        state = status.get("state")
                        need_items = status.get("needItems", 0)
                        need_deletes = status.get("needDeletes", 0)
                        global_files = status.get("globalFiles", 0)
                        
                        logger.debug(f"Syncthing status: state={state}, "
                                   f"needItems={need_items}, needDeletes={need_deletes}, "
                                   f"globalFiles={global_files}")
                        
                        # Проверяем: папка не в процессе синхронизации
                        if state == "idle" and status.get("needBytes", 0) == 0:
                            logger.info(f"✅ Синхронизация завершена ({global_files} файлов)")
                            return True
                    
                    await asyncio.sleep(0.5)  # Уменьшил до 0.5 сек для быстрее отклика

                logger.warning(f"⚠️ Timeout синхронизации (max_wait={max_wait}s)")
                return False

        except Exception as e:
            logger.error(f"❌ Ошибка Syncthing: {e}")
            return False
    
    async def wait_for_file(self, file_path: str, max_wait: int = 30) -> bool:
        """Ждать, пока конкретный файл появится на диске"""
        import os
        
        start_time = asyncio.get_event_loop().time()
        
        while asyncio.get_event_loop().time() - start_time < max_wait:
            if os.path.exists(file_path):
                file_size = os.path.getsize(file_path)
                logger.info(f"✅ Файл найден: {file_path} ({file_size} bytes)")
                return True
            
            await asyncio.sleep(0.2)
        
        logger.error(f"❌ Файл не найден после ожидания: {file_path}")
        return False
