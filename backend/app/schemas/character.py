"""角色 Schema"""
from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class CharacterBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    style: str = "anime"
    gender: Optional[str] = None
    age: Optional[str] = None
    hair_color: Optional[str] = None
    eye_color: Optional[str] = None
    skin_tone: Optional[str] = None
    body_type: Optional[str] = None
    tags: List[str] = []


class CharacterCreate(CharacterBase):
    project_id: Optional[str] = None
    reference_images: List[str] = []


class CharacterUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    style: Optional[str] = None
    gender: Optional[str] = None
    age: Optional[str] = None
    hair_color: Optional[str] = None
    eye_color: Optional[str] = None
    skin_tone: Optional[str] = None
    body_type: Optional[str] = None
    main_image_url: Optional[str] = None
    reference_images: Optional[List[str]] = None
    tags: Optional[List[str]] = None


class CharacterResponse(ORMModel):
    id: str
    user_id: str
    project_id: Optional[str] = None
    name: str
    description: Optional[str] = None
    style: str
    gender: Optional[str] = None
    age: Optional[str] = None
    hair_color: Optional[str] = None
    eye_color: Optional[str] = None
    skin_tone: Optional[str] = None
    body_type: Optional[str] = None
    lora_model_path: Optional[str] = None
    lora_training_status: str
    main_image_url: Optional[str] = None
    reference_images: Optional[Any] = None
    tags: Optional[Any] = None
    usage_count: int
    created_at: datetime
