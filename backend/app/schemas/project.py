"""项目 Schema"""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class ProjectBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    genre: Optional[str] = None
    config: Optional[dict] = None


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    genre: Optional[str] = None
    status: Optional[str] = None
    config: Optional[dict] = None


class ProjectResponse(ORMModel):
    id: str
    user_id: str
    name: str
    description: Optional[str] = None
    genre: Optional[str] = None
    status: str
    config: Optional[Any] = None
    character_count: int
    scene_count: int
    frame_count: int
    is_shared: bool
    collaborators: Optional[Any] = None
    created_at: datetime
    updated_at: datetime
