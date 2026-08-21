"""统一 API 响应模型"""
import time
from typing import Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """统一 API 响应"""
    code: int = Field(default=0, description="业务状态码，0 表示成功")
    message: str = Field(default="success", description="提示信息")
    data: Optional[T] = None
    timestamp: int = Field(default_factory=lambda: int(time.time()))

    @classmethod
    def success(cls, data: T = None, message: str = "success") -> "ApiResponse[T]":
        return cls(code=0, message=message, data=data)

    @classmethod
    def error(cls, message: str, code: int = -1, data: T = None) -> "ApiResponse[T]":
        return cls(code=code, message=message, data=data)


class PaginatedData(BaseModel, Generic[T]):
    """分页数据"""
    items: List[T]
    total: int
    page: int = 1
    page_size: int = 20


class PaginatedResponse(BaseModel, Generic[T]):
    """分页响应"""
    code: int = 0
    message: str = "success"
    data: PaginatedData[T]
    timestamp: int = Field(default_factory=lambda: int(time.time()))
