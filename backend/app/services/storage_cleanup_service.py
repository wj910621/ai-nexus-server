"""Best-effort retry worker for transactional storage deletion outbox entries."""
import asyncio

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.storage import storage
from app.models.storage_cleanup import PendingStorageDeletion


async def retry_pending_storage_deletions(
    db: AsyncSession, limit: int = 100
) -> tuple[int, int]:
    """Retry pending deletions, returning ``(deleted, failed)``."""
    result = await db.execute(
        select(PendingStorageDeletion)
        .order_by(PendingStorageDeletion.created_at.asc())
        .limit(limit)
    )
    entries = list(result.scalars().all())
    deleted = 0
    failed = 0
    for entry in entries:
        try:
            storage.delete(entry.path)
            await db.delete(entry)
            deleted += 1
        except (OSError, ValueError) as exc:
            entry.attempts += 1
            entry.last_error = str(exc)[:2000]
            failed += 1
            logger.warning(
                "Storage cleanup retry failed for {} (attempt {}): {}",
                entry.path,
                entry.attempts,
                exc,
            )
    await db.commit()
    return deleted, failed


async def storage_cleanup_loop(interval_seconds: int) -> None:
    """Periodically drain the outbox until the task is cancelled."""
    from app.core.database import AsyncSessionLocal

    while True:
        await asyncio.sleep(interval_seconds)
        try:
            async with AsyncSessionLocal() as db:
                deleted, failed = await retry_pending_storage_deletions(db)
                if deleted or failed:
                    logger.info(
                        "Storage cleanup pass: deleted={}, failed={}", deleted, failed
                    )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("Storage cleanup pass failed: {}", exc)
