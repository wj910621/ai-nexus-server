"""工作流模型 (Workflow + WorkflowExecution)"""
from sqlalchemy import JSON, Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy import Uuid as UUID

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin


class Workflow(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """工作流定义"""
    __tablename__ = "workflows"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=True)

    name = Column(String(200), nullable=False)
    description = Column(Text)

    # 工作流数据
    nodes = Column(JSON, nullable=False, default=list)
    edges = Column(JSON, nullable=False, default=list)

    # 元数据
    category = Column(String(50), default="custom")
    is_template = Column(Boolean, default=False)
    is_public = Column(Boolean, default=False)

    # 版本
    version = Column(Integer, default=1)
    parent_version_id = Column(UUID(as_uuid=True), nullable=True)


class WorkflowExecution(Base, UUIDMixin, TimestampMixin):
    """工作流执行记录"""
    __tablename__ = "workflow_executions"

    # Nullable for ad-hoc executions submitted with inline nodes/edges.
    workflow_id = Column(UUID(as_uuid=True), ForeignKey("workflows.id"), nullable=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    status = Column(String(20), default="running")  # running/completed/failed/cancelled
    inputs = Column(JSON)
    results = Column(JSON)
    errors = Column(JSON)

    started_at = Column(DateTime)
    completed_at = Column(DateTime, nullable=True)
    duration = Column(Float, nullable=True)

    node_executions = Column(JSON, default=list)
