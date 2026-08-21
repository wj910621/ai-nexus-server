"""音频模型 (VoiceProfile + AudioTrack)"""
from sqlalchemy import Column, Float, ForeignKey, Integer, String
from sqlalchemy import Uuid as UUID

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin


class VoiceProfile(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """音色配置"""
    __tablename__ = "voice_profiles"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    character_id = Column(UUID(as_uuid=True), ForeignKey("characters.id"), nullable=True)

    name = Column(String(100), nullable=False)
    engine = Column(String(50), default="edge_tts")  # edge_tts/vits/volcano
    voice_id = Column(String(100))
    language = Column(String(10), default="zh-CN")

    rate = Column(Integer, default=0)  # -100 到 100
    pitch = Column(Integer, default=0)
    volume = Column(Integer, default=100)

    gender = Column(String(20))
    age_group = Column(String(20))
    tone = Column(String(50))


class AudioTrack(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """音频轨道"""
    __tablename__ = "audio_tracks"

    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True)
    track_type = Column(String(50), nullable=False)  # voice/bgm/sfx/ambient
    name = Column(String(200))

    audio_url = Column(String(500))
    duration = Column(Float)

    start_time = Column(Float, default=0)
    end_time = Column(Float)

    frame_id = Column(UUID(as_uuid=True), ForeignKey("storyboard_frames.id"), nullable=True)
    dialogue_id = Column(UUID(as_uuid=True), ForeignKey("dialogues.id"), nullable=True)
    voice_profile_id = Column(UUID(as_uuid=True), ForeignKey("voice_profiles.id"), nullable=True)

    volume = Column(Float, default=1.0)
    fade_in = Column(Float, default=0)
    fade_out = Column(Float, default=0)
