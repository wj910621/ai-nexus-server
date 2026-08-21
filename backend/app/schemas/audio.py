"""音频 Schema"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class VoiceProfileBase(BaseModel):
    name: str = Field(..., max_length=100)
    engine: str = "edge_tts"
    voice_id: Optional[str] = None
    language: str = "zh-CN"
    rate: int = 0
    pitch: int = 0
    volume: int = 100
    gender: Optional[str] = None
    age_group: Optional[str] = None
    tone: Optional[str] = None


class VoiceProfileCreate(VoiceProfileBase):
    character_id: Optional[str] = None


class VoiceProfileResponse(ORMModel):
    id: str
    user_id: str
    character_id: Optional[str] = None
    name: str
    engine: str
    voice_id: Optional[str] = None
    language: str
    rate: int
    pitch: int
    volume: int
    gender: Optional[str] = None
    age_group: Optional[str] = None
    tone: Optional[str] = None
    created_at: datetime


class AudioTrackBase(BaseModel):
    track_type: str  # voice/bgm/sfx/ambient
    name: Optional[str] = None
    audio_url: Optional[str] = None
    duration: Optional[float] = None
    start_time: float = 0
    end_time: Optional[float] = None
    volume: float = 1.0
    fade_in: float = 0
    fade_out: float = 0


class AudioTrackCreate(AudioTrackBase):
    project_id: str
    frame_id: Optional[str] = None
    dialogue_id: Optional[str] = None
    voice_profile_id: Optional[str] = None


class AudioTrackResponse(ORMModel):
    id: str
    project_id: str
    track_type: str
    name: Optional[str] = None
    audio_url: Optional[str] = None
    duration: Optional[float] = None
    start_time: float
    end_time: Optional[float] = None
    frame_id: Optional[str] = None
    dialogue_id: Optional[str] = None
    voice_profile_id: Optional[str] = None
    volume: float
    fade_in: float
    fade_out: float
    created_at: datetime
