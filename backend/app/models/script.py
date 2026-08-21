"""剧本模型 (Script + Scene + Dialogue)"""
from sqlalchemy import Column, Float, ForeignKey, Integer, String, Text
from sqlalchemy import Uuid as UUID

from app.models.base import Base, TimestampMixin, UUIDMixin


class Script(Base, UUIDMixin, TimestampMixin):
    """剧本实体"""
    __tablename__ = "scripts"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text)

    structure = Column(String(50), default="three_act")
    genre = Column(String(50))
    outline = Column(Text)

    total_scenes = Column(Integer, default=0)
    total_duration = Column(Integer, default=0)
    status = Column(String(20), default="draft")  # draft/published/archived


class Scene(Base, UUIDMixin, TimestampMixin):
    """剧本场景实体"""
    __tablename__ = "script_scenes"

    script_id = Column(UUID(as_uuid=True), ForeignKey("scripts.id"), nullable=False, index=True)
    scene_number = Column(Integer, nullable=False)
    title = Column(String(200))
    location = Column(String(200))
    time_of_day = Column(String(50))
    description = Column(Text)
    mood = Column(String(50))
    intensity = Column(Integer, default=5)
    order_index = Column(Integer, default=0)


class Dialogue(Base, UUIDMixin, TimestampMixin):
    """对话实体"""
    __tablename__ = "dialogues"

    scene_id = Column(UUID(as_uuid=True), ForeignKey("script_scenes.id"), nullable=False, index=True)
    character_id = Column(UUID(as_uuid=True), ForeignKey("characters.id"), nullable=True)
    character_name = Column(String(100))

    content = Column(Text, nullable=False)
    emotion = Column(String(50))  # happy/sad/angry/surprised/neutral
    action = Column(Text)

    bubble_type = Column(String(50), default="normal")
    bubble_position = Column(String(50), default="right")
    duration = Column(Float, default=2.0)
    order_index = Column(Integer, default=0)
