"""训练数据集模型 - TrainingDataset + DatasetItem

Phase 8 P3: LoRA 训练 UI
"""
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin, utc_now


def _generate_dataset_id() -> str:
    import uuid
    return f"ds_{uuid.uuid4().hex[:14]}"


def _generate_item_id() -> str:
    import uuid
    return f"di_{uuid.uuid4().hex[:14]}"


class TrainingDataset(Base, TimestampMixin):
    """训练数据集实体"""
    __tablename__ = "training_datasets"

    id = Column(String(36), primary_key=True, default=_generate_dataset_id)
    character_id = Column(String(36), ForeignKey("characters.id"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    status = Column(String(20), default="drafting", nullable=False)
    # drafting / captioning / ready / training / used

    image_count = Column(Integer, default=0, nullable=False)
    caption_mode = Column(String(20), default="auto", nullable=False)
    # auto / manual

    trigger_word = Column(String(50), default="", nullable=False)

    items = relationship(
        "DatasetItem",
        back_populates="dataset",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class DatasetItem(Base):
    """数据集条目（单张图片 + caption）"""
    __tablename__ = "dataset_items"

    id = Column(String(36), primary_key=True, default=_generate_item_id)
    dataset_id = Column(String(36), ForeignKey("training_datasets.id"), nullable=False, index=True)
    image_path = Column(String(500), nullable=False)
    caption = Column(Text, default="", nullable=False)
    caption_source = Column(String(20), default="manual", nullable=False)
    # auto / manual / imported

    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)

    created_at = Column(DateTime, default=utc_now, nullable=False)

    dataset = relationship("TrainingDataset", back_populates="items")
