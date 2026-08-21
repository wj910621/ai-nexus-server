"""TaskService — DB-backed state machine + asyncio task runner.

State transitions:
    pending → running → succeeded
                      → failed
              → cancelled (only from pending or running)
"""
import asyncio
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Optional

from loguru import logger
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.background_task import BackgroundTask

TaskHandler = Callable[[BackgroundTask], Awaitable[Any]]


class TaskService:
    """Manages background tasks: submit, run, track state, query."""

    def __init__(self):
        self._handlers: dict[str, TaskHandler] = {}
        self._asyncio_tasks: dict[str, asyncio.Task] = {}
        self._semaphore = asyncio.Semaphore(settings.max_concurrent_tasks)

    def register_handler(self, task_type: str, handler: TaskHandler) -> None:
        """Register a handler for a task type."""
        self._handlers[task_type] = handler

    async def submit(
        self,
        db: AsyncSession,
        user_id: str,
        task_type: str,
        payload: dict,
    ) -> BackgroundTask:
        """Submit a new task. Persists to DB and starts asyncio task."""
        task = BackgroundTask(
            user_id=str(user_id),
            task_type=task_type,
            payload=payload,
            status="pending",
            progress=0,
        )
        db.add(task)
        await db.commit()
        await db.refresh(task)
        logger.info(f"Task submitted: {task.id} (type={task_type}, user={user_id})")

        # Start asyncio task if handler registered
        if task_type in self._handlers:
            asyncio_task = asyncio.create_task(self._run_task(task.id, task_type))
            self._asyncio_tasks[task.id] = asyncio_task
        else:
            logger.warning(
                f"No handler for task type '{task_type}'; task stays pending"
            )

        return task

    async def _run_task(self, task_id: str, task_type: str) -> None:
        """Run task handler with semaphore + state updates."""
        async with self._semaphore:
            # Use a fresh session for handler execution
            from app.core.database import AsyncSessionLocal
            async with AsyncSessionLocal() as db:
                try:
                    # Mark running
                    await self.mark_running(db, task_id)

                    # Fetch fresh task for handler
                    task = await self.get(db, task_id)
                    if task is None:
                        logger.error(f"Task {task_id} disappeared before execution")
                        return

                    handler = self._handlers[task_type]
                    result = await handler(task)

                    # Mark succeeded
                    await self.mark_succeeded(db, task_id, result=result)
                    logger.info(f"Task succeeded: {task_id}")

                except asyncio.CancelledError:
                    await self.mark_cancelled(db, task_id)
                    logger.info(f"Task cancelled: {task_id}")
                except Exception as e:
                    await self.mark_failed(db, task_id, error=str(e))
                    logger.error(f"Task failed: {task_id} — {e}", exc_info=True)
                finally:
                    self._asyncio_tasks.pop(task_id, None)

    async def get(self, db: AsyncSession, task_id: str) -> Optional[BackgroundTask]:
        """Get task by ID.

        Uses ``populate_existing=True`` to bypass the identity map so that
        state changes committed by background tasks (in a different session)
        are visible to the caller.
        """
        result = await db.execute(
            select(BackgroundTask)
            .where(BackgroundTask.id == task_id)
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def list_by_user(
        self,
        db: AsyncSession,
        user_id: str,
        page: int = 1,
        page_size: int = 10,
        status: Optional[str] = None,
    ) -> list[BackgroundTask]:
        """List tasks for a user with pagination."""
        query = select(BackgroundTask).where(BackgroundTask.user_id == str(user_id))
        if status:
            query = query.where(BackgroundTask.status == status)
        query = query.order_by(BackgroundTask.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await db.execute(query)
        return list(result.scalars().all())

    async def count_by_user(
        self, db: AsyncSession, user_id: str, status: Optional[str] = None
    ) -> int:
        """Count tasks for a user."""
        query = select(func.count(BackgroundTask.id)).where(
            BackgroundTask.user_id == str(user_id)
        )
        if status:
            query = query.where(BackgroundTask.status == status)
        result = await db.execute(query)
        return result.scalar_one()

    async def mark_running(self, db: AsyncSession, task_id: str) -> Optional[BackgroundTask]:
        """Mark task as running."""
        await db.execute(
            update(BackgroundTask)
            .where(BackgroundTask.id == task_id)
            .values(status="running", started_at=datetime.now(timezone.utc))
        )
        await db.commit()
        return await self.get(db, task_id)

    async def mark_succeeded(
        self, db: AsyncSession, task_id: str, result: Any
    ) -> Optional[BackgroundTask]:
        """Mark task as succeeded with result."""
        await db.execute(
            update(BackgroundTask)
            .where(BackgroundTask.id == task_id)
            .values(
                status="succeeded",
                result=result,
                progress=100,
                completed_at=datetime.now(timezone.utc),
            )
        )
        await db.commit()
        return await self.get(db, task_id)

    async def mark_failed(
        self, db: AsyncSession, task_id: str, error: str
    ) -> Optional[BackgroundTask]:
        """Mark task as failed with error."""
        await db.execute(
            update(BackgroundTask)
            .where(BackgroundTask.id == task_id)
            .values(status="failed", error=error, completed_at=datetime.now(timezone.utc))
        )
        await db.commit()
        return await self.get(db, task_id)

    async def mark_cancelled(self, db: AsyncSession, task_id: str) -> Optional[BackgroundTask]:
        """Mark task as cancelled."""
        await db.execute(
            update(BackgroundTask)
            .where(BackgroundTask.id == task_id)
            .values(status="cancelled", completed_at=datetime.now(timezone.utc))
        )
        await db.commit()

        # Cancel asyncio task if running
        asyncio_task = self._asyncio_tasks.pop(task_id, None)
        if asyncio_task and not asyncio_task.done():
            asyncio_task.cancel()

        return await self.get(db, task_id)

    async def cancel(self, db: AsyncSession, task_id: str) -> Optional[BackgroundTask]:
        """User-initiated cancel."""
        return await self.mark_cancelled(db, task_id)

    async def update_progress(
        self, db: AsyncSession, task_id: str, progress: int, message: str = ""
    ) -> None:
        """Update progress (0-100). Used by handlers via WebSocket events."""
        progress = max(0, min(100, progress))
        await db.execute(
            update(BackgroundTask)
            .where(BackgroundTask.id == task_id)
            .values(progress=progress)
        )
        await db.commit()

        # Push progress to WebSocket subscribers (Task 10)
        try:
            from app.core.ws_manager import ws_manager
            task = await self.get(db, task_id)
            if task is not None:
                await ws_manager.publish(
                    f"task:{task_id}",
                    {
                        "type": "progress",
                        "task_id": task_id,
                        "progress": progress,
                        "message": message,
                        "status": task.status,
                    },
                )
                await ws_manager.publish_to_user(
                    task.user_id,
                    {
                        "type": "task_progress",
                        "task_id": task_id,
                        "progress": progress,
                    },
                )
        except Exception as exc:
            logger.warning(f"WS publish failed for task {task_id}: {exc}")

    async def recover_interrupted(self, db: AsyncSession) -> int:
        """On startup, mark running tasks as failed (interrupted).

        Called from lifespan on boot. Returns count of recovered tasks.
        """
        result = await db.execute(
            select(BackgroundTask).where(
                BackgroundTask.status.in_(["pending", "running"])
            )
        )
        tasks = list(result.scalars().all())
        count = 0
        for task in tasks:
            await self.mark_failed(
                db, task.id, error="interrupted by server restart"
            )
            count += 1
        if count > 0:
            logger.warning(f"Recovered {count} interrupted tasks (marked as failed)")
        return count


# Module-level singleton
task_service = TaskService()


async def get_task_service() -> TaskService:
    """FastAPI dependency."""
    return task_service
