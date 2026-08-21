"""HealthCheckRegistry — pluggable health checks for /ready endpoint.

/health (liveness): always 200, no dependency checks
/ready (readiness): runs all registered checks, 200 if all healthy, 503 otherwise
"""
import asyncio
from typing import Awaitable, Callable

from loguru import logger

HealthCheck = Callable[[], Awaitable[dict]]


class HealthCheckRegistry:
    """Registry of named async health checks."""

    def __init__(self):
        self._checks: dict[str, HealthCheck] = {}

    def register(self, name: str, check: HealthCheck) -> None:
        """Register a health check by name."""
        self._checks[name] = check

    def unregister(self, name: str) -> None:
        """Remove a health check."""
        self._checks.pop(name, None)

    def list_checks(self) -> list[str]:
        """List registered check names."""
        return list(self._checks.keys())

    async def run_all(self) -> dict[str, dict]:
        """Run all checks concurrently. Returns {name: {status, detail}}."""
        results: dict[str, dict] = {}
        tasks = {
            name: asyncio.create_task(self._run_one(name, check))
            for name, check in self._checks.items()
        }
        for name, task in tasks.items():
            results[name] = await task
        return results

    async def _run_one(self, name: str, check: HealthCheck) -> dict:
        """Run a single check with error handling."""
        try:
            result = await check()
            # Normalize: ensure status field exists
            if "status" not in result:
                result["status"] = "healthy"
            return result
        except Exception as e:
            logger.warning(f"Health check '{name}' failed: {e}")
            return {"status": "unhealthy", "detail": str(e)}


# Module-level singleton
health_registry = HealthCheckRegistry()


async def check_db() -> dict:
    """Check database connectivity."""
    from sqlalchemy import text

    from app.core.database import engine
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "healthy", "detail": "database reachable"}
    except Exception as e:
        return {"status": "unhealthy", "detail": str(e)}


async def check_redis() -> dict:
    """Check Redis connectivity (skipped if not configured)."""
    from app.core.config import settings
    redis_url = settings.cache_redis_url or settings.redis_url
    if not redis_url or redis_url == "memory":
        return {"status": "skipped", "detail": "Redis not configured (desktop mode)"}
    try:
        import redis.asyncio as redis
        client = redis.from_url(redis_url, decode_responses=True)
        await client.ping()
        await client.aclose()
        return {"status": "healthy", "detail": "redis reachable"}
    except Exception as e:
        return {"status": "unhealthy", "detail": str(e)}


async def check_engines() -> dict:
    """Check AI engine availability (info-only, not blocking)."""
    from app.engines.manager import engine_manager
    errors = engine_manager.get_init_errors()
    if not errors:
        return {"status": "healthy", "detail": f"{len(engine_manager._engines)} engines initialized"}
    return {
        "status": "degraded",
        "detail": f"errors: {errors}; available: {list(engine_manager._engines.keys())}",
    }


# Register default checks
health_registry.register("db", check_db)
health_registry.register("redis", check_redis)
health_registry.register("engines", check_engines)
