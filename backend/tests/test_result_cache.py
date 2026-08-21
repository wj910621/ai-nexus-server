"""Tests for Task 9: Result Cache + Request Dedup."""
import asyncio
import json
import pytest
from datetime import datetime, timedelta

from app.models.result_cache import ResultCacheEntry
from app.services.result_cache_service import ResultCacheService, result_cache_service
from app.core.request_dedup import RequestDeduplicator, request_deduplicator


def test_build_cache_key_is_deterministic():
    """Same params → same key."""
    params = {"prompt": "cat", "width": 512, "height": 512}
    k1 = ResultCacheEntry.build_cache_key("image", params)
    k2 = ResultCacheEntry.build_cache_key("image", params)
    assert k1 == k2
    assert len(k1) == 64  # SHA256 hex


def test_build_cache_key_order_independent():
    """Different param order → same key."""
    k1 = ResultCacheEntry.build_cache_key("image", {"a": 1, "b": 2})
    k2 = ResultCacheEntry.build_cache_key("image", {"b": 2, "a": 1})
    assert k1 == k2


def test_build_cache_key_differs_by_engine():
    """Different engine_type → different key."""
    k1 = ResultCacheEntry.build_cache_key("image", {"prompt": "cat"})
    k2 = ResultCacheEntry.build_cache_key("llm", {"prompt": "cat"})
    assert k1 != k2


def test_build_cache_key_differs_by_user():
    """Different user_id → different key (per-user isolation)."""
    k1 = ResultCacheEntry.build_cache_key("image", {"prompt": "cat"}, user_id="1")
    k2 = ResultCacheEntry.build_cache_key("image", {"prompt": "cat"}, user_id="2")
    assert k1 != k2


@pytest.mark.asyncio
async def test_cache_miss_returns_none(db_session):
    """Cache miss returns None."""
    result = await result_cache_service.get(
        engine_type="image",
        params={"prompt": "nonexistent"},
        user_id="1",
    )
    assert result is None


@pytest.mark.asyncio
async def test_cache_set_then_get_returns_value(db_session):
    """Set then get returns the cached value."""
    await result_cache_service.set(
        engine_type="image",
        params={"prompt": "cat"},
        result={"url": "https://example.com/cat.png"},
        user_id="1",
    )
    result = await result_cache_service.get(
        engine_type="image",
        params={"prompt": "cat"},
        user_id="1",
    )
    assert result == {"url": "https://example.com/cat.png"}


@pytest.mark.asyncio
async def test_cache_hit_increments_hit_count(db_session):
    """Each hit increments hit_count."""
    await result_cache_service.set(
        engine_type="image", params={"p": "x"}, result={"r": 1}, user_id="1"
    )
    await result_cache_service.get("image", {"p": "x"}, user_id="1")
    await result_cache_service.get("image", {"p": "x"}, user_id="1")
    # Third get should report hit_count=2 internally; verify via DB
    from sqlalchemy import select
    from app.core.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        entry = (await db.execute(
            select(ResultCacheEntry).where(
                ResultCacheEntry.cache_key == ResultCacheEntry.build_cache_key(
                    "image", {"p": "x"}, user_id="1"
                )
            )
        )).scalar_one()
        assert entry.hit_count == 2


@pytest.mark.asyncio
async def test_cache_expires_after_ttl(db_session):
    """Cache entry expires after TTL."""
    await result_cache_service.set(
        engine_type="llm",
        params={"prompt": "hi"},
        result={"text": "hello"},
        user_id="1",
        ttl_seconds=0,  # Immediately expired
    )
    # Even with ttl=0, set happens-before get, but expires_at <= now → miss
    import time
    time.sleep(0.05)
    result = await result_cache_service.get("llm", {"prompt": "hi"}, user_id="1")
    assert result is None


@pytest.mark.asyncio
async def test_cache_set_upsert_updates_existing(db_session):
    """Re-setting same key updates payload instead of duplicate insert."""
    await result_cache_service.set(
        engine_type="image", params={"p": "x"}, result={"v": 1}, user_id="1"
    )
    await result_cache_service.set(
        engine_type="image", params={"p": "x"}, result={"v": 2}, user_id="1"
    )
    result = await result_cache_service.get("image", {"p": "x"}, user_id="1")
    assert result == {"v": 2}  # Updated value


@pytest.mark.asyncio
async def test_invalidate_user_removes_only_their_cache(db_session):
    """invalidate_user only removes entries for that user."""
    await result_cache_service.set("image", {"p": "a"}, result={"r": 1}, user_id="1")
    await result_cache_service.set("image", {"p": "a"}, result={"r": 2}, user_id="2")
    deleted = await result_cache_service.invalidate_user("1")
    assert deleted >= 1
    assert await result_cache_service.get("image", {"p": "a"}, user_id="1") is None
    assert await result_cache_service.get("image", {"p": "a"}, user_id="2") == {"r": 2}


@pytest.mark.asyncio
async def test_cleanup_expired_removes_old_entries(db_session):
    """cleanup_expired removes expired entries."""
    await result_cache_service.set(
        "llm", {"p": "x"}, result={"r": 1}, user_id="1", ttl_seconds=0
    )
    import time
    time.sleep(0.05)
    deleted = await result_cache_service.cleanup_expired()
    assert deleted >= 1


# ---------- RequestDeduplicator tests ----------

@pytest.mark.asyncio
async def test_dedup_merges_concurrent_identical_calls():
    """Two concurrent identical calls → only one underlying execution."""
    call_count = 0

    async def slow_func(x: int) -> int:
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.05)
        return x * 2

    dedup = RequestDeduplicator()
    # Launch 3 concurrent identical calls
    results = await asyncio.gather(
        dedup.deduplicate(slow_func, 5),
        dedup.deduplicate(slow_func, 5),
        dedup.deduplicate(slow_func, 5),
    )
    assert results == [10, 10, 10]
    assert call_count == 1  # Only one actual execution


@pytest.mark.asyncio
async def test_dedup_different_args_runs_separately():
    """Different args → separate executions."""
    call_count = 0

    async def func(x: int) -> int:
        nonlocal call_count
        call_count += 1
        return x

    dedup = RequestDeduplicator()
    r1, r2 = await asyncio.gather(
        dedup.deduplicate(func, 1),
        dedup.deduplicate(func, 2),
    )
    assert r1 == 1 and r2 == 2
    assert call_count == 2


@pytest.mark.asyncio
async def test_dedup_propagates_exception_to_all_waiters():
    """If the underlying call raises, all waiters get the exception."""
    async def failing_func():
        raise ValueError("upstream failure")

    dedup = RequestDeduplicator()
    results = await asyncio.gather(
        dedup.deduplicate(failing_func),
        dedup.deduplicate(failing_func),
        return_exceptions=True,
    )
    assert all(isinstance(r, ValueError) for r in results)
