"""分镜 Schema"""
from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel

from app.schemas.common import ORMModel


class StoryboardFrameBase(BaseModel):
    shot_type: Optional[str] = None
    camera_angle: Optional[str] = None
    composition: Optional[str] = None
    camera_movement: Optional[str] = None
    description: Optional[str] = None
    prompt: Optional[str] = None
    negative_prompt: Optional[str] = None
    characters_in_frame: List[dict] = []
    duration: float = 2.0
    transition: str = "cut"
    transition_duration: float = 0.5


class StoryboardFrameCreate(StoryboardFrameBase):
    script_id: str
    scene_id: Optional[str] = None
    frame_number: int


class StoryboardFrameUpdate(BaseModel):
    shot_type: Optional[str] = None
    camera_angle: Optional[str] = None
    composition: Optional[str] = None
    camera_movement: Optional[str] = None
    description: Optional[str] = None
    prompt: Optional[str] = None
    negative_prompt: Optional[str] = None
    characters_in_frame: Optional[List[dict]] = None
    duration: Optional[float] = None
    transition: Optional[str] = None
    transition_duration: Optional[float] = None
    generated_image_url: Optional[str] = None
    generation_status: Optional[str] = None


class StoryboardFrameResponse(ORMModel):
    id: str
    script_id: str
    scene_id: Optional[str] = None
    frame_number: int
    shot_type: Optional[str] = None
    camera_angle: Optional[str] = None
    composition: Optional[str] = None
    camera_movement: Optional[str] = None
    description: Optional[str] = None
    prompt: Optional[str] = None
    negative_prompt: Optional[str] = None
    characters_in_frame: Optional[Any] = None
    duration: float
    transition: str
    transition_duration: float
    generated_image_url: Optional[str] = None
    generation_status: str
    created_at: datetime
