"""剧本 Schema"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class ScriptBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    structure: str = "three_act"
    genre: Optional[str] = None
    outline: Optional[str] = None


class ScriptCreate(ScriptBase):
    project_id: str


class ScriptUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    structure: Optional[str] = None
    genre: Optional[str] = None
    outline: Optional[str] = None
    status: Optional[str] = None


class ScriptResponse(ORMModel):
    id: str
    user_id: str
    project_id: str
    title: str
    description: Optional[str] = None
    structure: str
    genre: Optional[str] = None
    outline: Optional[str] = None
    total_scenes: int
    total_duration: int
    status: str
    created_at: datetime
    updated_at: datetime


class SceneBase(BaseModel):
    title: Optional[str] = None
    location: Optional[str] = None
    time_of_day: Optional[str] = None
    description: Optional[str] = None
    mood: Optional[str] = None
    intensity: int = 5


class SceneCreate(SceneBase):
    script_id: str
    scene_number: int


class SceneResponse(ORMModel):
    id: str
    script_id: str
    scene_number: int
    title: Optional[str] = None
    location: Optional[str] = None
    time_of_day: Optional[str] = None
    description: Optional[str] = None
    mood: Optional[str] = None
    intensity: int
    order_index: int


class DialogueBase(BaseModel):
    character_name: Optional[str] = None
    content: str
    emotion: Optional[str] = None
    action: Optional[str] = None
    bubble_type: str = "normal"
    bubble_position: str = "right"
    duration: float = 2.0


class DialogueCreate(DialogueBase):
    scene_id: str
    character_id: Optional[str] = None


class DialogueResponse(ORMModel):
    id: str
    scene_id: str
    character_id: Optional[str] = None
    character_name: Optional[str] = None
    content: str
    emotion: Optional[str] = None
    action: Optional[str] = None
    bubble_type: str
    bubble_position: str
    duration: float
    order_index: int
