"""
Caching strategy for expensive operations.

Features:
- Paper metadata caching (arXiv results)
- Problem extraction caching
- Persona selection caching
- Code template caching
- Cache invalidation strategies
- TTL-based expiration
"""

import json
import hashlib
import pickle
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Optional, TypeVar, Generic, Callable
from functools import wraps
import sqlite3

from src.utils.logger import get_logger

logger = get_logger("cache")


class CacheStrategy(Enum):
    """Cache invalidation strategies."""
    TTL = "ttl"  # Time-based expiration
    LRU = "lru"  # Least recently used
    MANUAL = "manual"  # Manual invalidation


@dataclass
class CacheEntry:
    """
    A single cache entry.

    Attributes:
        key: Cache key
        value: Cached value
        timestamp: Creation timestamp
        ttl: Time to live in seconds (None = no expiration)
        hits: Number of cache hits
        size_bytes: Approximate size in bytes
    """
    key: str
    value: Any
    timestamp: float
    ttl: Optional[float] = None
    hits: int = 0
    size_bytes: int = 0

    def is_expired(self) -> bool:
        """Check if entry has expired."""
        if self.ttl is None:
            return False
        return time.time() - self.timestamp > self.ttl

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary (for JSON serialization)."""
        return {
            "key": self.key,
            "value": self.value if not isinstance(self.value, (bytes, object)) else str(self.value),
            "timestamp": self.timestamp,
            "ttl": self.ttl,
            "hits": self.hits,
            "size_bytes": self.size_bytes,
        }


class BaseCache(ABC):
    """Base class for cache implementations."""

    def __init__(self, name: str, default_ttl: Optional[float] = None):
        """
        Initialize cache.

        Args:
            name: Cache name (for logging)
            default_ttl: Default TTL in seconds
        """
        self.name = name
        self.default_ttl = default_ttl
        self._hits = 0
        self._misses = 0

    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        pass

    @abstractmethod
    def set(self, key: str, value: Any, ttl: Optional[float] = None):
        """Set value in cache."""
        pass

    @abstractmethod
    def delete(self, key: str) -> bool:
        """Delete entry from cache."""
        pass

    @abstractmethod
    def clear(self):
        """Clear all cache entries."""
        pass

    @abstractmethod
    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        pass

    def get_hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self._hits + self._misses
        if total == 0:
            return 0.0
        return self._hits / total

    def _generate_key(self, *args, **kwargs) -> str:
        """Generate cache key from arguments."""
        key_parts = [str(arg) for arg in args]
        key_parts.extend([f"{k}={v}" for k, v in sorted(kwargs.items())])
        key_string = ":".join(key_parts)
        return hashlib.sha256(key_string.encode()).hexdigest()[:32]


class InMemoryCache(BaseCache):
    """
    In-memory cache with LRU eviction.

    Fast but limited by memory. Suitable for small datasets.
    """

    def __init__(
        self,
        name: str,
        default_ttl: Optional[float] = None,
        max_size: int = 1000,
        max_memory_mb: int = 100,
    ):
        """
        Initialize in-memory cache.

        Args:
            name: Cache name
            default_ttl: Default TTL in seconds
            max_size: Maximum number of entries
            max_memory_mb: Maximum memory usage in MB
        """
        super().__init__(name, default_ttl)
        self.max_size = max_size
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        self._cache: dict[str, CacheEntry] = {}
        self._access_order: list[str] = []  # For LRU

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        entry = self._cache.get(key)

        if entry is None:
            self._misses += 1
            return None

        if entry.is_expired():
            self.delete(key)
            self._misses += 1
            return None

        # Update access order for LRU
        if key in self._access_order:
            self._access_order.remove(key)
        self._access_order.append(key)

        entry.hits += 1
        self._hits += 1
        return entry.value

    def set(self, key: str, value: Any, ttl: Optional[float] = None):
        """Set value in cache."""
        # Check if we need to evict
        self._ensure_capacity()

        # Calculate size
        try:
            size = len(json.dumps(value)) if not isinstance(value, (bytes, object)) else 0
        except (TypeError, OverflowError):
            size = 0

        entry = CacheEntry(
            key=key,
            value=value,
            timestamp=time.time(),
            ttl=ttl or self.default_ttl,
            size_bytes=size,
        )

        self._cache[key] = entry
        if key not in self._access_order:
            self._access_order.append(key)

    def delete(self, key: str) -> bool:
        """Delete entry from cache."""
        if key in self._cache:
            del self._cache[key]
            if key in self._access_order:
                self._access_order.remove(key)
            return True
        return False

    def clear(self):
        """Clear all cache entries."""
        self._cache.clear()
        self._access_order.clear()
        self._hits = 0
        self._misses = 0

    def _ensure_capacity(self):
        """Ensure cache doesn't exceed capacity limits."""
        # Check size limit
        while len(self._cache) >= self.max_size:
            self._evict_lru()

        # Check memory limit
        total_memory = sum(e.size_bytes for e in self._cache.values())
        while total_memory > self.max_memory_bytes and self._cache:
            total_memory -= self._evict_lru()

    def _evict_lru(self) -> int:
        """Evict least recently used entry. Returns freed bytes."""
        if not self._access_order:
            return 0

        lru_key = self._access_order.pop(0)
        entry = self._cache.pop(lru_key)
        logger.debug(f"[{self.name}] Evicted LRU entry: {lru_key}")
        return entry.size_bytes

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        total_size = sum(e.size_bytes for e in self._cache.values())
        return {
            "name": self.name,
            "type": "in_memory",
            "entries": len(self._cache),
            "max_entries": self.max_size,
            "memory_bytes": total_size,
            "max_memory_bytes": self.max_memory_bytes,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self.get_hit_rate(),
        }


class SQLiteCache(BaseCache):
    """
    Persistent cache using SQLite.

    Slower than in-memory but survives restarts.
    """

    def __init__(
        self,
        name: str,
        db_path: str = "./data/cache.db",
        default_ttl: Optional[float] = None,
    ):
        """
        Initialize SQLite cache.

        Args:
            name: Cache name (table name)
            db_path: Path to SQLite database
            default_ttl: Default TTL in seconds
        """
        super().__init__(name, default_ttl)
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initialize database table."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.name} (
                    key TEXT PRIMARY KEY,
                    value BLOB,
                    timestamp REAL,
                    ttl REAL,
                    hits INTEGER DEFAULT 0
                )
            """)
            conn.commit()

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    f"SELECT value, timestamp, ttl FROM {self.name} WHERE key = ?",
                    (key,)
                )
                row = cursor.fetchone()

                if row is None:
                    self._misses += 1
                    return None

                value_blob, timestamp, ttl = row

                # Check expiration
                if ttl is not None and time.time() - timestamp > ttl:
                    self.delete(key)
                    self._misses += 1
                    return None

                # Increment hits
                conn.execute(
                    f"UPDATE {self.name} SET hits = hits + 1 WHERE key = ?",
                    (key,)
                )
                conn.commit()

                self._hits += 1
                return pickle.loads(value_blob)

        except (sqlite3.Error, pickle.PickleError) as e:
            logger.error(f"[{self.name}] Cache get failed: {e}")
            self._misses += 1
            return None

    def set(self, key: str, value: Any, ttl: Optional[float] = None):
        """Set value in cache."""
        try:
            value_blob = pickle.dumps(value)
            timestamp = time.time()
            ttl_value = ttl or self.default_ttl

            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    f"""
                    INSERT OR REPLACE INTO {self.name} (key, value, timestamp, ttl)
                    VALUES (?, ?, ?, ?)
                    """,
                    (key, value_blob, timestamp, ttl_value)
                )
                conn.commit()

        except (sqlite3.Error, pickle.PickleError) as e:
            logger.error(f"[{self.name}] Cache set failed: {e}")

    def delete(self, key: str) -> bool:
        """Delete entry from cache."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    f"DELETE FROM {self.name} WHERE key = ?",
                    (key,)
                )
                conn.commit()
                return cursor.rowcount > 0
        except sqlite3.Error as e:
            logger.error(f"[{self.name}] Cache delete failed: {e}")
            return False

    def clear(self):
        """Clear all cache entries."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(f"DELETE FROM {self.name}")
                conn.commit()
                self._hits = 0
                self._misses = 0
        except sqlite3.Error as e:
            logger.error(f"[{self.name}] Cache clear failed: {e}")

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(f"SELECT COUNT(*) FROM {self.name}")
                count = cursor.fetchone()[0]

                cursor = conn.execute(f"SELECT SUM(hits) FROM {self.name}")
                total_hits = cursor.fetchone()[0] or 0

            return {
                "name": self.name,
                "type": "sqlite",
                "entries": count,
                "hits": total_hits + self._hits,
                "misses": self._misses,
                "hit_rate": self.get_hit_rate(),
            }
        except sqlite3.Error as e:
            logger.error(f"[{self.name}] Failed to get stats: {e}")
            return {
                "name": self.name,
                "type": "sqlite",
                "error": str(e),
            }


T = TypeVar("T")


def cached(
    cache: BaseCache,
    ttl: Optional[float] = None,
    key_fn: Optional[Callable] = None,
):
    """
    Decorator for caching function results.

    Args:
        cache: Cache instance to use
        ttl: Time to live for cached results
        key_fn: Optional function to generate cache key

    Example:
        @cached(paper_cache, ttl=3600)
        async def fetch_arxiv_paper(paper_id: str):
            ...
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            # Generate cache key
            if key_fn:
                key = key_fn(*args, **kwargs)
            else:
                key = cache._generate_key(func.__name__, *args, **kwargs)

            # Try to get from cache
            cached_value = cache.get(key)
            if cached_value is not None:
                logger.debug(f"[{cache.name}] Cache hit for {key}")
                return cached_value

            # Cache miss - call function
            logger.debug(f"[{cache.name}] Cache miss for {key}")
            result = await func(*args, **kwargs)

            # Store in cache
            cache.set(key, result, ttl=ttl)

            return result

        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> T:
            # Generate cache key
            if key_fn:
                key = key_fn(*args, **kwargs)
            else:
                key = cache._generate_key(func.__name__, *args, **kwargs)

            # Try to get from cache
            cached_value = cache.get(key)
            if cached_value is not None:
                logger.debug(f"[{cache.name}] Cache hit for {key}")
                return cached_value

            # Cache miss - call function
            logger.debug(f"[{cache.name}] Cache miss for {key}")
            result = func(*args, **kwargs)

            # Store in cache
            cache.set(key, result, ttl=ttl)

            return result

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


# Specialized caches for common operations

class PaperMetadataCache(SQLiteCache):
    """Cache for arXiv paper metadata."""

    def __init__(self, db_path: str = "./data/cache.db"):
        super().__init__("paper_metadata", db_path, default_ttl=86400)  # 24 hours

    def get_paper(self, paper_id: str) -> Optional[dict[str, Any]]:
        """Get paper metadata by ID."""
        return self.get(paper_id)

    def set_paper(self, paper_id: str, metadata: dict[str, Any]):
        """Cache paper metadata."""
        self.set(paper_id, metadata)

    def invalidate_paper(self, paper_id: str):
        """Invalidate cached paper."""
        self.delete(paper_id)


class ProblemExtractionCache(SQLiteCache):
    """Cache for extracted problems from papers."""

    def __init__(self, db_path: str = "./data/cache.db"):
        super().__init__("problem_extraction", db_path, default_ttl=604800)  # 7 days

    def get_problem(self, paper_id: str) -> Optional[str]:
        """Get extracted problem statement."""
        return self.get(paper_id)

    def set_problem(self, paper_id: str, problem: str):
        """Cache extracted problem."""
        self.set(paper_id, problem)


class PersonaCache(SQLiteCache):
    """Cache for generated personas by domain."""

    def __init__(self, db_path: str = "./data/cache.db"):
        super().__init__("personas", db_path, default_ttl=2592000)  # 30 days

    def get_personas(self, domain: str) -> Optional[list[dict[str, Any]]]:
        """Get personas for domain."""
        return self.get(domain.lower())

    def set_personas(self, domain: str, personas: list[dict[str, Any]]):
        """Cache personas for domain."""
        self.set(domain.lower(), personas)


class CodeTemplateCache(SQLiteCache):
    """Cache for generated code templates."""

    def __init__(self, db_path: str = "./data/cache.db"):
        super().__init__("code_templates", db_path, default_ttl=2592000)  # 30 days

    def get_template(self, template_type: str, signature: str) -> Optional[str]:
        """Get code template."""
        key = f"{template_type}:{signature}"
        return self.get(key)

    def set_template(self, template_type: str, signature: str, code: str):
        """Cache code template."""
        key = f"{template_type}:{signature}"
        self.set(key, code)


# Global cache instances
_paper_cache: Optional[PaperMetadataCache] = None
_problem_cache: Optional[ProblemExtractionCache] = None
_persona_cache: Optional[PersonaCache] = None
_template_cache: Optional[CodeTemplateCache] = None


def get_paper_cache() -> PaperMetadataCache:
    """Get global paper metadata cache."""
    global _paper_cache
    if _paper_cache is None:
        _paper_cache = PaperMetadataCache()
    return _paper_cache


def get_problem_cache() -> ProblemExtractionCache:
    """Get global problem extraction cache."""
    global _problem_cache
    if _problem_cache is None:
        _problem_cache = ProblemExtractionCache()
    return _problem_cache


def get_persona_cache() -> PersonaCache:
    """Get global persona cache."""
    global _persona_cache
    if _persona_cache is None:
        _persona_cache = PersonaCache()
    return _persona_cache


def get_template_cache() -> CodeTemplateCache:
    """Get global code template cache."""
    global _template_cache
    if _template_cache is None:
        _template_cache = CodeTemplateCache()
    return _template_cache


def clear_all_caches():
    """Clear all global caches."""
    global _paper_cache, _problem_cache, _persona_cache, _template_cache

    if _paper_cache:
        _paper_cache.clear()
    if _problem_cache:
        _problem_cache.clear()
    if _persona_cache:
        _persona_cache.clear()
    if _template_cache:
        _template_cache.clear()


def get_all_cache_stats() -> dict[str, dict[str, Any]]:
    """Get statistics for all caches."""
    stats = {}

    if _paper_cache:
        stats["paper_metadata"] = _paper_cache.get_stats()
    if _problem_cache:
        stats["problem_extraction"] = _problem_cache.get_stats()
    if _persona_cache:
        stats["personas"] = _persona_cache.get_stats()
    if _template_cache:
        stats["code_templates"] = _template_cache.get_stats()

    return stats


def cleanup_expired_caches():
    """Clean up expired entries from all caches."""
    logger.info("Cleaning up expired cache entries...")

    # For SQLite caches, we'd need to implement periodic cleanup
    # For now, expired entries are removed on access

    stats = get_all_cache_stats()
    for cache_name, cache_stats in stats.items():
        logger.info(
            f"Cache '{cache_name}': {cache_stats.get('entries', 0)} entries, "
            f"hit rate: {cache_stats.get('hit_rate', 0):.1%}"
        )
