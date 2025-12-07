import redis.asyncio as redis
from redis.asyncio.connection import ConnectionPool
from typing import Optional, List, Tuple
from loguru import logger
from bot.config import settings  
from redis import Redis
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

class RQRedisWrapper:
    """
    Обёртка вокруг sync Redis для RQ.
    Автоматически декодирует bytes в strings где нужно.
    """
    
    def __init__(self, redis_instance):
        self._redis = redis_instance
    
    def __getattr__(self, name):
        """Проксирует все методы к реальному Redis"""
        return getattr(self._redis, name)
    
    def _decode_if_bytes(self, value):
        """Декодирует bytes в string если нужно"""
        if isinstance(value, bytes):
            try:
                return value.decode('utf-8')
            except Exception:
                return value
        return value
    
    def get(self, key):
        """Декодирует result"""
        result = self._redis.get(key)
        return self._decode_if_bytes(result)
    
    def lrange(self, key, start, end):
        """Декодирует весь list"""
        result = self._redis.lrange(key, start, end)
        return [self._decode_if_bytes(item) for item in result]
    
    def hgetall(self, key):
        """Декодирует весь hash"""
        result = self._redis.hgetall(key)
        return {
            self._decode_if_bytes(k): self._decode_if_bytes(v)
            for k, v in result.items()
        }
    
    def pipeline(self):
        """Возвращает pipeline для RQ"""
        return self._redis.pipeline()


_raw_sync_redis = Redis.from_url(
    settings.REDIS_URL,
    decode_responses=False,  
    socket_keepalive=True
)


sync_redis_client = RQRedisWrapper(_raw_sync_redis)