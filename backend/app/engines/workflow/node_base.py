# backend/app/engines/workflow/node_base.py
"""节点抽象基类与定义"""
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class NodeCategory(str, Enum):
    """节点分类"""
    INPUT = "input"
    GENERATION = "generation"
    PROCESSING = "processing"
    COMPOSITE = "composite"
    OUTPUT = "output"
    UTILITY = "utility"


class NodeStatus(str, Enum):
    """节点执行状态"""
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class PortDefinition(BaseModel):
    """端口定义"""
    name: str
    type: str  # image/text/audio/video/any/image_array
    required: bool = True
    default: Any = None
    description: str = ""


class ParameterDefinition(BaseModel):
    """参数定义"""
    name: str
    type: str  # int/float/text/bool/select
    default: Any = None
    min: Optional[float] = None
    max: Optional[float] = None
    options: Optional[list[str]] = None
    description: str = ""


class NodeDefinition(BaseModel):
    """节点定义"""
    type: str
    name: str
    category: NodeCategory
    description: str = ""
    icon: str = ""
    inputs: list[PortDefinition] = Field(default_factory=list)
    outputs: list[PortDefinition] = Field(default_factory=list)
    parameters: list[ParameterDefinition] = Field(default_factory=list)
    is_async: bool = True
    estimated_time: float = 1.0


class BaseNode(ABC):
    """节点基类"""

    def __init__(self, node_id: str, params: Optional[dict] = None):
        self.id = node_id
        self.params = params or {}
        self.status = NodeStatus.IDLE
        self.result: Optional[dict] = None
        self.error: Optional[str] = None
        self.started_at: Optional[float] = None
        self.completed_at: Optional[float] = None

    @abstractmethod
    async def execute(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """执行节点逻辑

        Args:
            inputs: 输入数据 {port_name: value}

        Returns:
            输出数据 {port_name: value}
        """
        ...

    @classmethod
    @abstractmethod
    def get_definition(cls) -> NodeDefinition:
        """获取节点定义"""
        ...

    def get_info(self) -> dict:
        """获取节点运行信息"""
        return {
            "id": self.id,
            "status": self.status.value if isinstance(self.status, NodeStatus) else self.status,
            "has_result": self.result is not None,
            "error": self.error,
        }

    def get_elapsed(self) -> Optional[float]:
        """获取执行耗时（秒）"""
        if self.started_at and self.completed_at:
            return round(self.completed_at - self.started_at, 3)
        return None
