"""Tests for EngineConcurrencyManager."""
import pytest
import asyncio
from unittest.mock import AsyncMock, patch

from app.core.engine_concurrency import EngineConcurrencyManager


@pytest.fixture
def manager():
    return EngineConcurrencyManager(
        limits={"image": 2, "llm": 3, "tts": 1, "video": 1, "character": 1}
    )


@pytest.mark.asyncio
async def test_acquire_slot_success(manager):
    """Acquiring a slot when available succeeds."""
    async with manager.acquire("image") as slot:
        assert slot.engine_type == "image"
        assert manager.active_count("image") == 1


@pytest.mark.asyncio
async def test_release_after_context(manager):
    """Slot is released after context exits."""
    async with manager.acquire("image"):
        pass
    assert manager.active_count("image") == 0


@pytest.mark.asyncio
async def test_concurrent_acquires_within_limit(manager):
    """Multiple acquires up to limit succeed."""
    async with manager.acquire("image"):
        async with manager.acquire("image"):
            assert manager.active_count("image") == 2


@pytest.mark.asyncio
async def test_acquire_blocks_when_limit_reached(manager):
    """Acquire blocks when limit reached, then succeeds after release."""
    acquired_second = asyncio.Event()

    async def hold_then_release():
        async with manager.acquire("tts"):
            # Hold for a bit
            await asyncio.sleep(0.1)

    async def wait_and_acquire():
        # This should block until first releases
        async with manager.acquire("tts"):
            acquired_second.set()

    await asyncio.gather(hold_then_release(), wait_and_acquire())
    assert acquired_second.is_set()


@pytest.mark.asyncio
async def test_acquire_timeout_raises_timeout_error(manager):
    """Acquire with timeout raises TimeoutError when slot unavailable."""
    async with manager.acquire("tts"):
        with pytest.raises(TimeoutError):
            async with manager.acquire("tts", timeout=0.05):
                pass


@pytest.mark.asyncio
async def test_unknown_engine_type_raises(manager):
    """Unknown engine type raises ValueError."""
    with pytest.raises(ValueError, match="unknown_engine"):
        async with manager.acquire("unknown_engine"):
            pass


@pytest.mark.asyncio
async def test_get_limits_returns_config(manager):
    """get_limits returns configured limits."""
    limits = manager.get_limits()
    assert limits == {"image": 2, "llm": 3, "tts": 1, "video": 1, "character": 1}


@pytest.mark.asyncio
async def test_update_limits_dynamically(manager):
    """Update limits at runtime."""
    manager.update_limits({"image": 5})
    assert manager.get_limits()["image"] == 5
