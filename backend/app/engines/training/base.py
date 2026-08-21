"""TrainingEngine 抽象基类 + 训练参数/结果数据类

Phase 8 P3: LoRA 训练 UI
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Awaitable, Callable

PRESET_STEPS = {
    "quick": 500,
    "standard": 1000,
    "high_quality": 2000,
}


@dataclass
class TrainingParams:
    """统一训练参数 schema"""
    base_model: str = "stabilityai/sdxl-base-1.0"
    resolution: int = 1024
    rank: int = 32
    learning_rate: float = 1e-4
    batch_size: int = 1
    max_train_steps: int = 1000
    gradient_accumulation: int = 4
    lr_scheduler: str = "cosine"
    seed: int = 42
    trigger_word: str = ""
    preset: str = "standard"

    @classmethod
    def from_preset(cls, preset: str, trigger_word: str = "") -> "TrainingParams":
        """根据预设档位创建参数"""
        steps = PRESET_STEPS.get(preset, 1000)
        return cls(max_train_steps=steps, trigger_word=trigger_word, preset=preset)


@dataclass
class TrainingResult:
    """训练结果"""
    adapter_path: str
    metrics: dict = field(default_factory=dict)


class TrainingEngine(ABC):
    """训练引擎抽象基类

    子类必须实现 train() 和 check_available()。
    """

    @abstractmethod
    async def train(
        self,
        dataset_path: str,
        output_dir: str,
        params: TrainingParams,
        progress_callback: Callable[[int, str], Awaitable[None]],
    ) -> TrainingResult:
        """执行训练，返回产物路径与指标

        Args:
            dataset_path: 数据集目录路径（含图片+caption）
            output_dir: 输出目录（保存 adapter.safetensors）
            params: 训练参数
            progress_callback: 进度回调 (progress: 0-100, message: str)
        """
        ...

    @abstractmethod
    def check_available(self) -> tuple[bool, str]:
        """检查引擎是否可用

        Returns:
            (is_available, reason) — reason 在不可用时给出原因
        """
        ...
