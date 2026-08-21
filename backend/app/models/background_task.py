"""BackgroundTask model — persistent state machine for async tasks."""
import uuid
from datetime import datetime, timezone
from typing import ClassVar, Optional

from sqlalchemy import JSON, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


def _generate_task_id() -> str:
    return f"task_{uuid.uuid4().hex[:16]}"


class BackgroundTask(Base):
    """Background task with DB-backed state machine.

    States: pending → running → succeeded | failed | cancelled
    """

    __tablename__ = "background_tasks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_generate_task_id)
    user_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    task_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # e.g., "video_compose", "batch_image_gen", "character_generate"

    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending", index=True
    )
    # pending | running | succeeded | failed | cancelled

    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    # Input parameters for the task

    result: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # Output on success (e.g., {"video_url": "..."})

    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Error message on failure

    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # 0-100

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # asyncio.Task reference (not persisted; in-memory only)
    _asyncio_task: ClassVar[Optional[object]] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "task_type": self.task_type,
            "status": self.status,
            "progress": self.progress,
            "payload": self.payload,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
