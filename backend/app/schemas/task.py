"""Pydantic schemas for task API."""
from typing import Optional

from pydantic import BaseModel, Field


class TaskResponse(BaseModel):
    """Single task response."""
    id: str
    user_id: int
    task_type: str
    status: str
    progress: int = 0
    payload: dict = Field(default_factory=dict)
    result: Optional[dict] = None
    error: Optional[str] = None
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    model_config = {"from_attributes": True}


class TaskListResponse(BaseModel):
    """Paginated list of tasks."""
    items: list[TaskResponse]
    total: int
    page: int
    page_size: int


class TaskCreateRequest(BaseModel):
    """Submit a new task."""
    task_type: str = Field(..., description="Type: video_compose | batch_image_gen | character_generate")
    payload: dict = Field(default_factory=dict)


class TaskSubmitResponse(BaseModel):
    """Response when task is submitted (202 Accepted)."""
    task_id: str
    status: str = "pending"
    message: str = "Task submitted"
