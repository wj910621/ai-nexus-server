"""训练数据集 Schema"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class DatasetCreate(BaseModel):
    """创建数据集"""
    character_id: str = Field(..., description="关联角色 ID")
    name: str = Field(..., min_length=1, max_length=100)
    caption_mode: str = Field("auto", pattern="^(auto|manual)$")
    trigger_word: str = Field("", max_length=50)


class CaptionUpdate(BaseModel):
    """更新单张图片 caption"""
    caption: str = Field(..., min_length=0, max_length=2000)


class DatasetItemResponse(ORMModel):
    """数据集条目响应"""
    id: str
    dataset_id: str
    image_path: str
    caption: str
    caption_source: str
    width: Optional[int] = None
    height: Optional[int] = None
    created_at: datetime


class DatasetResponse(ORMModel):
    """数据集响应（含条目列表）"""
    id: str
    character_id: str
    user_id: str
    name: str
    status: str
    image_count: int
    caption_mode: str
    trigger_word: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    items: List[DatasetItemResponse] = []
