import redis
import redis.asyncio as aioredis
from redis import Redis
from redis.asyncio.connection import ConnectionPool
from typing import Optional, List, Tuple, Any
from functools import wraps
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

class RQRedisWrapper:
    """
    Обёртка вокруг sync Redis для RQ.
    Автоматически декодирует bytes в strings ДЛЯ ВСЕХ МЕТОДОВ.
    """
    
    def __init__(self, redis_instance):
        self._redis = redis_instance
    
    def _decode_bytes(self, obj: Any) -> Any:
        """Рекурсивно декодирует bytes во всех структурах данных"""
        if isinstance(obj, bytes):
            try:
                return obj.decode('utf-8')
            except (UnicodeDecodeError, AttributeError):
                # Если не UTF-8, возвращаем как есть
                return obj
        elif isinstance(obj, dict):
            return {self._decode_bytes(k): self._decode_bytes(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._decode_bytes(item) for item in obj]
        elif isinstance(obj, tuple):
            return tuple(self._decode_bytes(item) for item in obj)
        elif isinstance(obj, set):
            return {self._decode_bytes(item) for item in obj}
        return obj
    
    def __getattr__(self, name: str):
        """Перехватывает ВСЕ атрибуты и методы"""
        attr = getattr(self._redis, name)
        
        # Если это метод - оборачиваем его для декодирования результата
        if callable(attr):
            @wraps(attr)
            def wrapper(*args, **kwargs):
                result = attr(*args, **kwargs)
                return self._decode_bytes(result)
            return wrapper
        
        # Если это не метод - возвращаем как есть
        return attr
    
    def __setattr__(self, name: str, value: Any) -> None:
        """Позволяет сохранять атрибуты wrapper-а"""
        if name.startswith('_'):
            super().__setattr__(name, value)
        else:
            setattr(self._redis, name, value)


_raw_sync_redis = Redis.from_url(
    settings.REDIS_URL,
    decode_responses=False,  
    socket_keepalive=True
)


sync_redis_client = RQRedisWrapper(_raw_sync_redis)