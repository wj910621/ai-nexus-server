"""项目模型"""
from sqlalchemy import JSON, Boolean, Column, ForeignKey, Integer, String, Text
from sqlalchemy import Uuid as UUID

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin


class Project(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """项目实体"""
    __tablename__ = "projects"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    genre = Column(String(50))  # romance/action/mystery/comedy/drama

    status = Column(String(20), default="active")  # active/archived/deleted

    config = Column(JSON, default=lambda: {
        "resolution": "1920x1080",
        "fps": 24,
        "style": "anime",
    })

    # 统计
    character_count = Column(Integer, default=0)
    scene_count = Column(Integer, default=0)
    frame_count = Column(Integer, default=0)

    # 协作
    is_shared = Column(Boolean, default=False)
    collaborators = Column(JSON, default=list)
