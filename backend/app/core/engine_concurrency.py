"""EngineConcurrencyManager — per-engine-type asyncio.Semaphore.

Prevents:
- API bans (Pollinations 50 req/min)
- Resource exhaustion (too many concurrent FFmpeg processes)
- VRAM/RAM overload in desktop local inference
"""
import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Optional

from loguru import logger

from app.core.config import settings

DEFAULT_LIMITS = {
    "image": settings.engine_max_concurrent_image,
    "llm": settings.engine_max_concurrent_llm,
    "tts": settings.engine_max_concurrent_tts,
    "video": settings.engine_max_concurrent_video,
    "character": settings.engine_max_concurrent_character,
}


@dataclass
class EngineSlot:
    """Acquired engine slot (informational; release is handled by acquire's context)."""
    engine_type: str
    _manager: "EngineConcurrencyManager"


class EngineConcurrencyManager:
    """Manages per-engine-type asyncio.Semaphore.

    Usage:
        async with engine_concurrency.acquire("image", timeout=30) as slot:
            result = await image_engine.text2img(...)
    """

    def __init__(self, limits: Optional[dict[str, int]] = None):
        self._limits = dict(limits) if limits else dict(DEFAULT_LIMITS)
        self._semaphores: dict[str, asyncio.Semaphore] = {
            engine_type: asyncio.Semaphore(limit)
            for engine_type, limit in self._limits.items()
        }
        self._active_counts: dict[str, int] = {k: 0 for k in self._limits}

    @asynccontextmanager
    async def acquire(self, engine_type: str, timeout: Optional[float] = None):
        """Acquire a slot for the engine type.

        Args:
            engine_type: One of image/llm/tts/video/character
            timeout: Seconds to wait; None = use settings.engine_acquire_timeout_seconds;
                     raises TimeoutError if not acquired

        Raises:
            ValueError: Unknown engine type
            TimeoutError: Slot not acquired within timeout
        """
        if engine_type not in self._semaphores:
            raise ValueError(
                f"Unknown engine type: '{engine_type}'. "
                f"Valid: {list(self._semaphores.keys())}"
            )

        if timeout is None:
            timeout = settings.engine_acquire_timeout_seconds

        semaphore = self._semaphores[engine_type]
        try:
            await asyncio.wait_for(semaphore.acquire(), timeout=timeout)
        except asyncio.TimeoutError:
            raise TimeoutError(
                f"Could not acquire '{engine_type}' slot within {timeout}s "
                f"(active={self._active_counts[engine_type]}, "
                f"limit={self._limits[engine_type]})"
            )

        self._active_counts[engine_type] += 1
        try:
            yield EngineSlot(engine_type=engine_type, _manager=self)
        finally:
            self._release(engine_type)

    def _release(self, engine_type: str) -> None:
        """Release a slot (called by EngineSlot.__aexit__)."""
        self._active_counts[engine_type] -= 1
        self._semaphores[engine_type].release()

    def active_count(self, engine_type: str) -> int:
        """Return current active count for engine type."""
        return self._active_counts.get(engine_type, 0)

    def get_limits(self) -> dict[str, int]:
        """Return current limits."""
        return dict(self._limits)

    def update_limits(self, new_limits: dict[str, int]) -> None:
        """Update limits at runtime (creates new semaphores).

        Warning: existing acquired slots are not affected; new semaphore
        starts fresh.
        """
        for engine_type, limit in new_limits.items():
            if engine_type in self._limits:
                self._limits[engine_type] = limit
                self._semaphores[engine_type] = asyncio.Semaphore(limit)
                logger.info(f"Updated '{engine_type}' concurrency limit to {limit}")

    def get_status(self) -> dict:
        """Return status for monitoring."""
        return {
            engine_type: {
                "limit": self._limits[engine_type],
                "active": self._active_counts[engine_type],
                "available": self._limits[engine_type] - self._active_counts[engine_type],
            }
            for engine_type in self._limits
        }


# Module-level singleton
engine_concurrency = EngineConcurrencyManager()
