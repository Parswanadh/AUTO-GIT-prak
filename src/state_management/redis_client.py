"""
Redis Client
============

Connection manager for Redis with automatic retries and health checks.
"""

import redis.asyncio as redis
from redis.asyncio import ConnectionPool
from typing import Optional
import asyncio
import logging

logger = logging.getLogger(__name__)


class RedisClient:
    """
    Async Redis client with connection pooling and health checks.
    
    Example:
        ```python
        client = RedisClient()
        await client.connect()
        
        await client.set("key", "value", ttl=3600)
        value = await client.get("key")
        
        await client.close()
        ```
    """
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        max_connections: int = 50,
        decode_responses: bool = True
    ):
        """
        Initialize Redis client.
        
        Args:
            host: Redis host
            port: Redis port
            db: Database number (0-15)
            password: Optional password
            max_connections: Connection pool size
            decode_responses: Auto-decode bytes to strings
        """
        self.host = host
        self.port = port
        self.db = db
        self.password = password
        self.decode_responses = decode_responses
        
        self.pool: Optional[ConnectionPool] = None
        self.client: Optional[redis.Redis] = None
        self._connected = False
    
    async def connect(self) -> None:
        """
        Establish connection to Redis.
        
        Raises:
            redis.ConnectionError: If connection fails
        """
        try:
            self.pool = ConnectionPool(
                host=self.host,
                port=self.port,
                db=self.db,
                password=self.password,
                max_connections=50,
                decode_responses=self.decode_responses
            )
            
            self.client = redis.Redis(connection_pool=self.pool)
            
            # Test connection
            await self.client.ping()
            self._connected = True
            
            logger.info(f"Connected to Redis at {self.host}:{self.port}")
        
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
    
    async def close(self) -> None:
        """Close connection and cleanup pool"""
        if self.client:
            await self.client.close()
        
        if self.pool:
            await self.pool.disconnect()
        
        self._connected = False
        logger.info("Redis connection closed")
    
    async def health_check(self) -> bool:
        """
        Check if Redis is healthy.
        
        Returns:
            True if connection is alive
        """
        try:
            if not self.client:
                return False
            
            await self.client.ping()
            return True
        
        except Exception as e:
            logger.warning(f"Redis health check failed: {e}")
            return False
    
    # Basic operations
    async def set(
        self,
        key: str,
        value: str,
        ttl: Optional[int] = None
    ) -> bool:
        """
        Set a key-value pair.
        
        Args:
            key: Key name
            value: Value to store
            ttl: Time-to-live in seconds (optional)
        
        Returns:
            True if successful
        """
        if not self.client:
            raise RuntimeError("Redis client not connected")
        
        return await self.client.set(key, value, ex=ttl)
    
    async def get(self, key: str) -> Optional[str]:
        """
        Get value by key.
        
        Args:
            key: Key name
        
        Returns:
            Value or None if key doesn't exist
        """
        if not self.client:
            raise RuntimeError("Redis client not connected")
        
        return await self.client.get(key)
    
    async def delete(self, *keys: str) -> int:
        """
        Delete one or more keys.
        
        Args:
            *keys: Keys to delete
        
        Returns:
            Number of keys deleted
        """
        if not self.client:
            raise RuntimeError("Redis client not connected")
        
        return await self.client.delete(*keys)
    
    async def exists(self, *keys: str) -> int:
        """
        Check if keys exist.
        
        Args:
            *keys: Keys to check
        
        Returns:
            Number of existing keys
        """
        if not self.client:
            raise RuntimeError("Redis client not connected")
        
        return await self.client.exists(*keys)
    
    async def expire(self, key: str, seconds: int) -> bool:
        """
        Set expiration on a key.
        
        Args:
            key: Key name
            seconds: TTL in seconds
        
        Returns:
            True if successful
        """
        if not self.client:
            raise RuntimeError("Redis client not connected")
        
        return await self.client.expire(key, seconds)
    
    # Hash operations
    async def hset(self, name: str, key: str, value: str) -> int:
        """Set hash field"""
        if not self.client:
            raise RuntimeError("Redis client not connected")
        
        return await self.client.hset(name, key, value)
    
    async def hget(self, name: str, key: str) -> Optional[str]:
        """Get hash field"""
        if not self.client:
            raise RuntimeError("Redis client not connected")
        
        return await self.client.hget(name, key)
    
    async def hgetall(self, name: str) -> dict:
        """Get all hash fields"""
        if not self.client:
            raise RuntimeError("Redis client not connected")
        
        return await self.client.hgetall(name)
    
    # List operations
    async def lpush(self, key: str, *values: str) -> int:
        """Push values to list (left)"""
        if not self.client:
            raise RuntimeError("Redis client not connected")
        
        return await self.client.lpush(key, *values)
    
    async def rpush(self, key: str, *values: str) -> int:
        """Push values to list (right)"""
        if not self.client:
            raise RuntimeError("Redis client not connected")
        
        return await self.client.rpush(key, *values)
    
    async def lrange(self, key: str, start: int, end: int) -> list:
        """Get list range"""
        if not self.client:
            raise RuntimeError("Redis client not connected")
        
        return await self.client.lrange(key, start, end)
    
    # Pub/Sub operations
    async def publish(self, channel: str, message: str) -> int:
        """
        Publish message to channel.
        
        Args:
            channel: Channel name
            message: Message to publish
        
        Returns:
            Number of subscribers that received the message
        """
        if not self.client:
            raise RuntimeError("Redis client not connected")
        
        return await self.client.publish(channel, message)
    
    async def subscribe(self, *channels: str):
        """
        Subscribe to channels.
        
        Args:
            *channels: Channel names
        
        Returns:
            PubSub instance
        
        Example:
            ```python
            pubsub = await client.subscribe("events")
            
            async for message in pubsub.listen():
                print(message)
            ```
        """
        if not self.client:
            raise RuntimeError("Redis client not connected")
        
        pubsub = self.client.pubsub()
        await pubsub.subscribe(*channels)
        return pubsub
    
    # Pattern matching
    async def keys(self, pattern: str) -> list:
        """
        Find keys matching pattern.
        
        Args:
            pattern: Pattern with wildcards (* and ?)
        
        Returns:
            List of matching keys
        """
        if not self.client:
            raise RuntimeError("Redis client not connected")
        
        return await self.client.keys(pattern)
    
    async def scan(self, cursor: int = 0, match: Optional[str] = None, count: int = 10):
        """
        Iterate over keys (more efficient than keys()).
        
        Args:
            cursor: Cursor position
            match: Pattern to match
            count: Number of keys per iteration
        
        Returns:
            (new_cursor, keys) tuple
        """
        if not self.client:
            raise RuntimeError("Redis client not connected")
        
        return await self.client.scan(cursor, match=match, count=count)
    
    # Utility
    async def flushdb(self) -> bool:
        """
        Delete all keys in current database.
        
        **WARNING**: This deletes ALL data!
        
        Returns:
            True if successful
        """
        if not self.client:
            raise RuntimeError("Redis client not connected")
        
        return await self.client.flushdb()
    
    async def info(self, section: Optional[str] = None) -> dict:
        """
        Get Redis server info.
        
        Args:
            section: Info section (memory, stats, etc.)
        
        Returns:
            Server info dict
        """
        if not self.client:
            raise RuntimeError("Redis client not connected")
        
        return await self.client.info(section)
    
    @property
    def is_connected(self) -> bool:
        """Check if client is connected"""
        return self._connected


# Singleton instance
_redis_client: Optional[RedisClient] = None


async def get_redis_client() -> RedisClient:
    """
    Get singleton Redis client instance.
    
    Automatically connects on first use.
    
    Example:
        ```python
        from src.state_management import get_redis_client
        
        client = await get_redis_client()
        await client.set("key", "value")
        ```
    """
    global _redis_client
    
    if _redis_client is None:
        _redis_client = RedisClient()
        await _redis_client.connect()
    
    return _redis_client


async def close_redis_client() -> None:
    """Close singleton Redis client"""
    global _redis_client
    
    if _redis_client:
        await _redis_client.close()
        _redis_client = None
