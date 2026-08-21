"""Cache service — unified abstraction over in-memory TTLCache and Redis.

Both cloud (Redis primary) and desktop (in-memory) deployments use this single
interface. Desktop mode auto-falls back to in-memory when Redis is unavailable.
"""
import asyncio
import fnmatch
import json
import time
from typing import Any, Awaitable, Callable, Optional

from cachetools import TTLCache
from loguru import logger

from app.core.config import settings

# Make redis importable at module level so tests can patch `app.core.cache.redis`.
# Gracefully degrade when redis is not installed (desktop mode).
try:
    import redis.asyncio as redis  # noqa: F401
except ImportError:  # pragma: no cover - desktop fallback
    redis = None  # type: ignore[assignment]


class CacheService:
    """Unified cache with pluggable backend.

    Backends:
    - "memory": cachetools.TTLCache (in-process, desktop + cloud fallback)
    - "redis": redis.asyncio (cloud primary, distributed)

    Memory backend stores ``(value, expiration_monotonic)`` tuples to support
    per-entry TTL (TTLCache's global TTL is only used as a safety net for
    eviction).
    """

    def __init__(self, backend: str = "memory", redis_client=None):
        self.backend = backend
        self._redis = redis_client
        if backend == "memory":
            self._memory: TTLCache = TTLCache(
                maxsize=settings.cache_max_size_memory,
                ttl=settings.cache_ttl_default,
            )
            self._lock = asyncio.Lock()
        elif backend == "redis" and redis_client is None:
            raise ValueError("redis_client required when backend='redis'")

    def _full_key(self, key: str) -> str:
        return f"{settings.cache_key_prefix}{key}"

    async def get(self, key: str) -> Any:
        """Get value by key. Returns None on miss."""
        full_key = self._full_key(key)
        try:
            if self.backend == "memory":
                async with self._lock:
                    entry = self._memory.get(full_key)
                    if entry is None:
                        return None
                    value, expiration = entry
                    if time.monotonic() >= expiration:
                        # Per-entry TTL expired
                        self._memory.pop(full_key, None)
                        return None
                    return value
            else:  # redis
                raw = await self._redis.get(full_key)
                if raw is None:
                    return None
                return json.loads(raw)
        except Exception as e:
            logger.warning(f"Cache get failed for '{key}': {e}")
            return None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value with TTL (seconds). Uses default TTL if None."""
        full_key = self._full_key(key)
        ttl = ttl if ttl is not None else settings.cache_ttl_default
        try:
            if self.backend == "memory":
                async with self._lock:
                    # Track per-entry expiration manually (TTLCache global TTL
                    # is only a backstop for eviction).
                    expiration = time.monotonic() + max(ttl, 0)
                    self._memory[full_key] = (value, expiration)
            else:  # redis
                await self._redis.setex(full_key, ttl, json.dumps(value))
        except Exception as e:
            logger.warning(f"Cache set failed for '{key}': {e}")

    async def delete(self, key: str) -> bool:
        """Delete key. Returns True if existed, False otherwise."""
        full_key = self._full_key(key)
        try:
            if self.backend == "memory":
                async with self._lock:
                    existed = full_key in self._memory
                    self._memory.pop(full_key, None)
                    return existed
            else:
                deleted = await self._redis.delete(full_key)
                return deleted > 0
        except Exception as e:
            logger.warning(f"Cache delete failed for '{key}': {e}")
            return False

    async def clear(self) -> None:
        """Clear all keys."""
        try:
            if self.backend == "memory":
                async with self._lock:
                    self._memory.clear()
            else:
                # Only clear keys with our prefix
                async for key in self._redis.scan_iter(
                    match=f"{settings.cache_key_prefix}*", count=100
                ):
                    await self._redis.delete(key)
        except Exception as e:
            logger.warning(f"Cache clear failed: {e}")

    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        full_key = self._full_key(key)
        try:
            if self.backend == "memory":
                async with self._lock:
                    entry = self._memory.get(full_key)
                    if entry is None:
                        return False
                    _, expiration = entry
                    if time.monotonic() >= expiration:
                        self._memory.pop(full_key, None)
                        return False
                    return True
            else:
                return bool(await self._redis.exists(full_key))
        except Exception as e:
            logger.warning(f"Cache exists failed for '{key}': {e}")
            return False

    async def get_or_set(
        self,
        key: str,
        compute: Callable[[], Awaitable[Any]],
        ttl: Optional[int] = None,
    ) -> Any:
        """Get value; if missing, compute and store."""
        cached = await self.get(key)
        if cached is not None:
            return cached
        value = await compute()
        await self.set(key, value, ttl=ttl)
        return value

    async def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate all keys matching glob pattern (e.g., 'user:1:*').

        Returns count of deleted keys.
        """
        full_pattern = self._full_key(pattern)
        count = 0
        try:
            if self.backend == "memory":
                async with self._lock:
                    keys_to_delete = [
                        k for k in list(self._memory.keys())
                        if fnmatch.fnmatch(k, full_pattern)
                    ]
                    for k in keys_to_delete:
                        self._memory.pop(k, None)
                        count += 1
            else:
                async for key in self._redis.scan_iter(
                    match=full_pattern, count=100
                ):
                    await self._redis.delete(key)
                    count += 1
        except Exception as e:
            logger.warning(f"Cache invalidate_pattern failed for '{pattern}': {e}")
        return count


_cache_service: Optional[CacheService] = None


async def get_cache_service() -> CacheService:
    """Get or initialize the global CacheService singleton.

    Backend selection:
    1. If cache_redis_url == "memory" → force in-memory
    2. Else try Redis (from cache_redis_url or redis_url); if reachable, use Redis
    3. Else fall back to in-memory
    """
    global _cache_service
    if _cache_service is not None:
        return _cache_service

    if not settings.cache_enabled:
        _cache_service = CacheService(backend="memory")
        return _cache_service

    redis_url = settings.cache_redis_url or settings.redis_url
    if redis_url == "memory" or redis_url == "":
        _cache_service = CacheService(backend="memory")
        logger.info("CacheService: in-memory backend (explicitly configured)")
        return _cache_service

    # Try Redis (uses module-level `redis` so tests can patch
    # `app.core.cache.redis.from_url`)
    try:
        if redis is None:
            raise ImportError("redis package not installed")
        client = redis.from_url(redis_url, decode_responses=True)
        await client.ping()
        _cache_service = CacheService(backend="redis", redis_client=client)
        logger.info(f"CacheService: Redis backend at {redis_url}")
        return _cache_service
    except Exception as e:
        if settings.is_production:
            raise RuntimeError("Production Redis cache is unavailable") from e
        logger.warning(
            f"CacheService: Redis unavailable ({e}), falling back to in-memory"
        )
        _cache_service = CacheService(backend="memory")
        return _cache_service


async def close_cache_service() -> None:
    """Close cache service (called on app shutdown)."""
    global _cache_service
    if _cache_service is not None and _cache_service.backend == "redis":
        await _cache_service._redis.aclose()
    _cache_service = None


def reset_cache_service() -> None:
    """Reset the singleton (for tests only)."""
    global _cache_service
    _cache_service = None
