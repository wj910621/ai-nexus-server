"""Audit log schemas."""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel

from app.schemas.common import ORMModel


class AuditLogResponse(ORMModel):
    """An audit log entry."""
    id: UUID
    actor_id: Optional[UUID] = None
    action: str
    resource_type: Optional[str] = None
    resource_id: Optional[UUID] = None
    metadata: Optional[dict] = None
    created_at: datetime


class AuditLogListResponse(BaseModel):
    """Paginated audit log list."""
    items: list[AuditLogResponse]
    total: int
    page: int = 1
    page_size: int = 50
