"""Tests for CacheService — in-memory + Redis dual mode."""
import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from app.core.cache import CacheService, get_cache_service, reset_cache_service


@pytest.fixture(autouse=True)
def _reset_cache_singleton():
    """Reset the global CacheService singleton between tests for isolation."""
    reset_cache_service()
    yield
    reset_cache_service()


@pytest.fixture
def memory_cache():
    """In-memory cache (no Redis)."""
    return CacheService(backend="memory")


@pytest.mark.asyncio
async def test_memory_cache_set_get(memory_cache):
    """Set then get returns value within TTL."""
    await memory_cache.set("key1", "value1", ttl=60)
    result = await memory_cache.get("key1")
    assert result == "value1"


@pytest.mark.asyncio
async def test_memory_cache_miss(memory_cache):
    """Get on missing key returns None."""
    result = await memory_cache.get("nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_memory_cache_ttl_expiry(memory_cache):
    """Value expires after TTL."""
    await memory_cache.set("key1", "value1", ttl=0)  # Immediate expiry
    await asyncio.sleep(0.01)
    result = await memory_cache.get("key1")
    assert result is None


@pytest.mark.asyncio
async def test_memory_cache_delete(memory_cache):
    """Delete removes the key."""
    await memory_cache.set("key1", "value1", ttl=60)
    deleted = await memory_cache.delete("key1")
    assert deleted is True
    assert await memory_cache.get("key1") is None


@pytest.mark.asyncio
async def test_memory_cache_clear(memory_cache):
    """Clear removes all keys."""
    await memory_cache.set("k1", "v1", ttl=60)
    await memory_cache.set("k2", "v2", ttl=60)
    await memory_cache.clear()
    assert await memory_cache.get("k1") is None
    assert await memory_cache.get("k2") is None


@pytest.mark.asyncio
async def test_memory_cache_exists(memory_cache):
    """Exists returns True for set keys."""
    await memory_cache.set("key1", "value1", ttl=60)
    assert await memory_cache.exists("key1") is True
    assert await memory_cache.exists("missing") is False


@pytest.mark.asyncio
async def test_cache_service_factory_memory(monkeypatch):
    """Factory returns memory backend when cache_redis_url='memory'."""
    monkeypatch.setattr("app.core.cache.settings.cache_redis_url", "memory")
    svc = await get_cache_service()
    assert svc.backend == "memory"


@pytest.mark.asyncio
async def test_cache_service_factory_redis_unavailable(monkeypatch):
    """Factory falls back to memory if Redis unreachable."""
    monkeypatch.setattr("app.core.cache.settings.cache_redis_url", "")
    monkeypatch.setattr("app.core.cache.settings.redis_url", "redis://invalid:6379/0")
    svc = await get_cache_service()
    # Should fall back to memory since Redis is unreachable
    assert svc.backend == "memory"


@pytest.mark.asyncio
async def test_cache_service_redis_unavailable_fails_closed_in_production(monkeypatch):
    """Production must not silently split cache state across pod memory."""
    monkeypatch.setattr("app.core.cache.settings.app_env", "production")
    monkeypatch.setattr("app.core.cache.settings.cache_redis_url", "")
    monkeypatch.setattr("app.core.cache.settings.redis_url", "redis://invalid:6379/0")
    with pytest.raises(RuntimeError, match="Production Redis cache is unavailable"):
        await get_cache_service()


@pytest.mark.asyncio
async def test_cache_service_redis_mode(monkeypatch):
    """Factory uses Redis when available."""
    fake_redis = AsyncMock()
    fake_redis.ping = AsyncMock(return_value=True)

    with patch("app.core.cache.redis.from_url", return_value=fake_redis):
        monkeypatch.setattr("app.core.cache.settings.cache_redis_url", "")
        monkeypatch.setattr("app.core.cache.settings.redis_url", "redis://localhost:6379/0")
        svc = await get_cache_service()
        assert svc.backend == "redis"


@pytest.mark.asyncio
async def test_cache_get_or_set(memory_cache):
    """get_or_set fetches existing or computes and stores."""
    call_count = 0

    async def compute():
        nonlocal call_count
        call_count += 1
        return f"computed_{call_count}"

    # First call: cache miss, computes
    result1 = await memory_cache.get_or_set("key1", compute, ttl=60)
    assert result1 == "computed_1"
    assert call_count == 1

    # Second call: cache hit, doesn't compute
    result2 = await memory_cache.get_or_set("key1", compute, ttl=60)
    assert result2 == "computed_1"
    assert call_count == 1  # compute not called again


@pytest.mark.asyncio
async def test_cache_invalidate_pattern(memory_cache):
    """Invalidate removes keys matching prefix."""
    await memory_cache.set("user:1:balance", "100", ttl=60)
    await memory_cache.set("user:1:plan", "pro", ttl=60)
    await memory_cache.set("user:2:balance", "200", ttl=60)
    count = await memory_cache.invalidate_pattern("user:1:*")
    assert count == 2
    assert await memory_cache.get("user:1:balance") is None
    assert await memory_cache.get("user:2:balance") == "200"


@pytest.mark.asyncio
async def test_cache_serialize_dict(memory_cache):
    """Cache serializes dict values correctly."""
    data = {"user_id": 1, "balance": 100, "plan": "pro"}
    await memory_cache.set("user:1", data, ttl=60)
    result = await memory_cache.get("user:1")
    assert result == data
