"""Rate limiting module.

Uses fastapi-limiter with Redis backend in production. In desktop mode
(no Redis available), rate limiting is gracefully disabled.

Per-plan limits:
- free:       10 req/min  (sustained), 30 req/min burst
- pro:        60 req/min  (sustained), 120 req/min burst
- enterprise: 300 req/min (sustained), 600 req/min burst
"""
import functools
import os
import time
from typing import Any, Callable

from fastapi import HTTPException, status
from loguru import logger

# Per-plan rate limits: (times, seconds) = N requests per S seconds
PLAN_RATE_LIMITS: dict[str, tuple[int, int]] = {
    "free": (30, 60),        # 30 per minute
    "pro": (120, 60),        # 120 per minute
    "enterprise": (600, 60), # 600 per minute
}

DEFAULT_RATE_LIMIT = PLAN_RATE_LIMITS["free"]


_redis_client = None
_limiter_initialized = False


def is_rate_limiting_enabled() -> bool:
    """Check if rate limiting should be active.

    Disabled when:
    - CS_DESKTOP_MODE=1 (no Redis in desktop mode)
    - rate_limit_redis_url == "none"
    - Redis URL is empty
    """
    if os.environ.get("CS_DESKTOP_MODE", "").lower() in ("1", "true", "yes"):
        return False
    from app.core.config import settings
    if not settings.rate_limit_enabled:
        return False
    redis_url = settings.rate_limit_redis_url or settings.redis_url
    if not redis_url or redis_url == "none":
        return False
    return True


def get_limiter():
    """Return the initialized Redis client or a desktop no-op sentinel."""
    if not is_rate_limiting_enabled():
        return _DummyLimiter()
    return _redis_client


async def init_limiter(app):
    """Connect and verify the Redis limiter during application startup."""
    global _limiter_initialized, _redis_client
    if _limiter_initialized:
        return
    if not is_rate_limiting_enabled():
        logger.info("Rate limiting disabled (desktop mode or no Redis)")
        _limiter_initialized = True
        return
    try:
        import redis.asyncio as aioredis

        from app.core.config import settings
        redis_url = settings.rate_limit_redis_url or settings.redis_url
        _redis_client = aioredis.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
        await _redis_client.ping()
        _limiter_initialized = True
        logger.info("Distributed rate limiter connected")
    except Exception as e:
        _redis_client = None
        from app.core.config import settings
        if settings.app_env.lower() == "production":
            raise RuntimeError("Production rate limiter Redis is unavailable") from e
        logger.warning(f"Rate limiter init failed in non-production mode: {e}")
        _limiter_initialized = True


class _DummyLimiter:
    """No-op limiter used when rate limiting is disabled."""
    pass


def rate_limit(times: int = 30, seconds: int = 60):
    """Decorator to apply rate limiting to an endpoint.

    A3: 实际调用 fastapi_limiter.limiter.limit(...)。
    当 rate limiting 被禁用（桌面模式或 Redis 不可用）时为 no-op。

    Usage:
        @router.get("/expensive")
        @rate_limit(times=5, seconds=60)
        async def expensive_endpoint(request: Request):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            if not is_rate_limiting_enabled():
                return await func(*args, **kwargs)
            request = kwargs.get("request")
            if request is None:
                for arg in args:
                    if hasattr(arg, "client") and hasattr(arg, "headers"):
                        request = arg
                        break
            if request is None:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Rate-limited endpoint is missing Request context",
                )

            from app.core.config import settings
            try:
                redis = _redis_client
                if redis is None:
                    raise RuntimeError("Rate limiter is not initialized")
                bucket = int(time.time()) // seconds
                client_ip = get_client_ip(request)
                key = f"rate:{func.__module__}:{func.__name__}:{client_ip}:{bucket}"
                async with redis.pipeline(transaction=True) as pipeline:
                    pipeline.incr(key)
                    pipeline.expire(key, seconds + 1)
                    count, _ = await pipeline.execute()
                if int(count) > times:
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail="Too many requests",
                        headers={"Retry-After": str(seconds)},
                    )
            except HTTPException:
                raise
            except Exception as exc:
                if settings.app_env.lower() == "production":
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="Rate limiting service unavailable",
                    ) from exc
                logger.warning(f"Rate limiter bypassed outside production: {exc}")
                return await func(*args, **kwargs)
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def get_client_ip(request) -> str:
    """Extract client IP from request, respecting X-Forwarded-For."""
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        # Take first IP in chain
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def get_rate_limit_for_plan(plan: str) -> tuple[int, int]:
    """Get (times, seconds) rate limit for a plan."""
    return PLAN_RATE_LIMITS.get(plan, DEFAULT_RATE_LIMIT)
