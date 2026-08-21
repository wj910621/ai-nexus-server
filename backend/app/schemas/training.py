"""训练相关 Schema"""
from typing import Optional

from pydantic import BaseModel, Field


class TrainParamsAdvanced(BaseModel):
    """高级训练参数（可选）"""
    rank: int = Field(32, ge=1, le=128, description="LoRA rank")
    learning_rate: float = Field(1e-4, gt=0, lt=1, description="学习率")
    max_train_steps: int = Field(1000, ge=10, le=10000, description="最大训练步数")
    batch_size: int = Field(1, ge=1, le=8, description="批次大小")
    gradient_accumulation: int = Field(4, ge=1, le=16, description="梯度累积")


class TrainRequest(BaseModel):
    """提交训练任务请求"""
    dataset_id: str = Field(..., description="数据集 ID")
    location: str = Field(..., pattern="^(local|replicate)$", description="训练位置")
    trigger_word: str = Field(..., min_length=2, max_length=50, description="触发词")
    preset: str = Field(
        "standard", pattern="^(quick|standard|high_quality)$",
        description="预设档位",
    )
    advanced: Optional[TrainParamsAdvanced] = Field(None, description="高级参数")


class TrainResponse(BaseModel):
    """训练任务提交响应"""
    task_id: str
    character_id: str
    status: str


class TrainStatusResponse(BaseModel):
    """训练状态查询响应"""
    status: str
    progress: int = 0
    message: str = ""
    task_id: Optional[str] = None
