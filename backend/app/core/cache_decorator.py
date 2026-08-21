"""@cached decorator for service methods.

Usage:
    @cached(ttl=30, key=lambda self, user_id: f"user:{user_id}:balance")
    async def get_balance(self, user_id: int) -> dict:
        ...
"""
import functools
from typing import Callable, Optional

from app.core.cache import get_cache_service


def cached(
    ttl: Optional[int] = None,
    key: Optional[Callable] = None,
    invalidate_on: Optional[Callable] = None,
):
    """Decorator: cache method result.

    Args:
        ttl: Cache TTL in seconds (None = use default)
        key: Function (self, *args, **kwargs) → cache key string
        invalidate_on: Function (self, result, *args, **kwargs) → list of
            glob patterns to invalidate after write
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(self, *args, **kwargs):
            cache = await get_cache_service()

            # Compute cache key
            if key is not None:
                cache_key = key(self, *args, **kwargs)
            else:
                # Default: function name + args
                cache_key = f"{func.__name__}:{args}:{sorted(kwargs.items())}"

            # Try cache
            cached_value = await cache.get(cache_key)
            if cached_value is not None:
                return cached_value

            # Compute and store
            result = await func(self, *args, **kwargs)

            # Store in cache
            await cache.set(cache_key, result, ttl=ttl)

            # Invalidate related keys if specified
            if invalidate_on is not None:
                patterns = invalidate_on(self, result, *args, **kwargs)
                for pattern in patterns:
                    await cache.invalidate_pattern(pattern)

            return result
        return wrapper
    return decorator
