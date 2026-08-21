"""通用 Schema"""
from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ORMModel(BaseModel):
    """支持从 ORM 模型转换的基类"""
    model_config = {"from_attributes": True}


class PaginationParams(BaseModel):
    """分页参数"""
    page: int = 1
    page_size: int = 20
