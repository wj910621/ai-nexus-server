"""角色模型"""
from sqlalchemy import JSON, Column, ForeignKey, Integer, String, Text
from sqlalchemy import Uuid as UUID

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin


class Character(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """角色实体"""
    __tablename__ = "characters"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)

    # 外观特征
    style = Column(String(50), default="anime")
    gender = Column(String(20))
    age = Column(String(50))
    hair_color = Column(String(50))
    eye_color = Column(String(50))
    skin_tone = Column(String(50))
    body_type = Column(String(50))

    # LoRA 模型
    lora_model_path = Column(String(500))
    lora_training_status = Column(String(20), default="none")  # none/training/ready/failed

    # 图像
    main_image_url = Column(String(500))
    reference_images = Column(JSON, default=list)

    # 元数据
    tags = Column(JSON, default=list)
    usage_count = Column(Integer, default=0)
