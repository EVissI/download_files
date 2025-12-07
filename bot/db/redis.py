import redis.asyncio as redis
from redis.asyncio.connection import ConnectionPool
from typing import Optional, List, Tuple
from loguru import logger
from bot.config import settings  

class RedisClient:
    def __init__(self, url: str = settings.REDIS_URL):  
        self.url = url
        self.pool: Optional[ConnectionPool] = None
        self.redis: Optional[redis.Redis] = None
        self._connected = False

    async def ensure_connection(self):
        """Ensures Redis connection is established using a connection pool"""
        if not self._connected:
            try:
                self.pool = ConnectionPool.from_url(
                    self.url,
                    decode_responses=True,
                    max_connections=10
                )
                self.redis = redis.Redis(connection_pool=self.pool)
                self._connected = True
                logger.info("Successfully connected to Redis with connection pool")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                raise

    async def connect(self):
        await self.ensure_connection()

    async def close(self):
        if self.redis:
            await self.redis.close()
            if self.pool:
                await self.pool.disconnect()
            self._connected = False

    async def set(self, key: str, value: str, expire: int = None):
        await self.ensure_connection()
        await self.redis.set(key, value, ex=expire)

    async def get(self, key: str):
        await self.ensure_connection()
        return await self.redis.get(key)

    async def add_admin_message(self, user_id: int, admin_id: int, message_id: int):
        await self.ensure_connection()
        key = f"admin_msgs:{user_id}"
        value = f"{admin_id}:{message_id}"
        await self.redis.rpush(key, value)

    async def get_admin_messages(self, user_id: int) -> List[Tuple[int, int]]:
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
        key = f"admin_msgs:{user_id}"
        await self.redis.delete(key)

    async def delete(self, key: str) -> bool:
        await self.ensure_connection()
        result = await self.redis.delete(key)
        return bool(result)

redis_client = RedisClient()

from redis import Redis
sync_redis_client = Redis.from_url(
    settings.REDIS_URL,
    decode_responses=False
)