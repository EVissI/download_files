import redis.asyncio as redis
from typing import Optional, List, Tuple
from loguru import logger


class RedisClient:
    def __init__(self, url: str = "redis://redis:6379/0"):
        self.url = url
        self.redis: Optional[redis.Redis] = None
        self._connected = False

    async def ensure_connection(self):
        """Ensures Redis connection is established"""
        if not self._connected:
            try:
                self.redis = await redis.from_url(self.url, decode_responses=True)
                self._connected = True
                logger.info("Successfully connected to Redis")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                raise

    async def connect(self):
        await self.ensure_connection()

    async def close(self):
        if self.redis:
            await self.redis.close()
            self._connected = False

    async def set(self, key: str, value: str, expire: int = None):
        await self.ensure_connection()
        await self.redis.set(key, value, ex=expire)

    async def get(self, key: str):
        await self.ensure_connection()
        return await self.redis.get(key)

    async def add_admin_message(self, user_id: int, admin_id: int, message_id: int):
        await self.ensure_connection()
        """
        Добавить сообщение админа для конкретного пользователя.
        Хранится как список строк "admin_id:message_id" по ключу f"admin_msgs:{user_id}"
        """
        key = f"admin_msgs:{user_id}"
        value = f"{admin_id}:{message_id}"
        await self.redis.rpush(key, value)

    async def get_admin_messages(self, user_id: int) -> List[Tuple[int, int]]:
        """
        Получить список (admin_id, message_id) для пользователя.
        """
        key = f"admin_msgs:{user_id}"
        values = await self.redis.lrange(key, 0, -1)
        result = []
        for v in values:
            try:
                admin_id, message_id = map(int, v.split(":"))
                result.append((admin_id, message_id))
            except Exception:
                continue
        return result

    async def clear_admin_messages(self, user_id: int):
        """
        Удалить все сообщения админов для пользователя.
        """
        key = f"admin_msgs:{user_id}"
        await self.redis.delete(key)

    async def delete(self, key: str) -> bool:
        """
        Delete a key from Redis.

        Args:
            key: Key to delete

        Returns:
            bool: True if key was deleted, False otherwise
        """
        await self.ensure_connection()
        result = await self.redis.delete(key)
        return bool(result)


redis_client = RedisClient()
