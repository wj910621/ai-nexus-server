"""渲染 Schema"""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel

from app.schemas.common import ORMModel


class RenderTaskCreate(BaseModel):
    project_id: str
    script_id: str
    name: Optional[str] = None
    config: Optional[dict] = None


class RenderTaskResponse(ORMModel):
    id: str
    user_id: str
    project_id: str
    script_id: str
    name: Optional[str] = None
    status: str
    progress: int
    config: Optional[Any] = None
    output_url: Optional[str] = None
    output_size: Optional[int] = None
    duration: Optional[float] = None
    frame_count: Optional[int] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    credits_cost: int
    created_at: datetime
