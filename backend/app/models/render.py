"""渲染任务模型"""
from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy import Uuid as UUID

from app.models.base import Base, TimestampMixin, UUIDMixin


class RenderTask(Base, UUIDMixin, TimestampMixin):
    """渲染任务"""
    __tablename__ = "render_tasks"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True)
    script_id = Column(UUID(as_uuid=True), ForeignKey("scripts.id"), nullable=False)

    name = Column(String(200))
    status = Column(String(20), default="pending")  # pending/processing/completed/failed/cancelled
    progress = Column(Integer, default=0)

    config = Column(JSON)
    output_url = Column(String(500), nullable=True)
    output_size = Column(Integer, nullable=True)
    duration = Column(Float, nullable=True)
    frame_count = Column(Integer, nullable=True)

    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    credits_cost = Column(Integer, default=0)
