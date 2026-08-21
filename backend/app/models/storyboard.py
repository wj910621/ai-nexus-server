"""分镜模型"""
from sqlalchemy import JSON, Column, Float, ForeignKey, Integer, String, Text
from sqlalchemy import Uuid as UUID

from app.models.base import Base, TimestampMixin, UUIDMixin


class StoryboardFrame(Base, UUIDMixin, TimestampMixin):
    """分镜帧"""
    __tablename__ = "storyboard_frames"

    script_id = Column(UUID(as_uuid=True), ForeignKey("scripts.id"), nullable=False, index=True)
    scene_id = Column(UUID(as_uuid=True), ForeignKey("script_scenes.id"), nullable=True)
    frame_number = Column(Integer, nullable=False)

    # 镜头信息
    shot_type = Column(String(50))  # extreme_wide/wide/medium/close_up
    camera_angle = Column(String(50))  # eye_level/high_angle/low_angle
    composition = Column(String(50))  # rule_of_thirds/center/symmetry
    camera_movement = Column(String(50))  # static/pan/zoom/tracking

    # 内容
    description = Column(Text)
    prompt = Column(Text)
    negative_prompt = Column(Text)

    # 角色配置
    characters_in_frame = Column(JSON, default=list)

    # 时间
    duration = Column(Float, default=2.0)
    transition = Column(String(50), default="cut")
    transition_duration = Column(Float, default=0.5)

    # 生成结果
    generated_image_url = Column(String(500), nullable=True)
    generation_status = Column(String(20), default="pending")  # pending/generating/completed/failed
