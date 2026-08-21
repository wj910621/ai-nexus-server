"""训练引擎包 - P3 LoRA 训练

提供 TrainingEngine 抽象基类 + Local/Replicate 实现 + TrainingEngineProvider 路由。
"""
from app.engines.training.base import TrainingEngine, TrainingParams, TrainingResult
from app.engines.training.local import LocalTrainingEngine
from app.engines.training.replicate import ReplicateTrainingEngine


class TrainingEngineProvider:
    """训练引擎路由选择"""

    @staticmethod
    def select(location: str) -> TrainingEngine:
        """按 location 选择引擎"""
        if location == "local":
            return LocalTrainingEngine()
        elif location == "replicate":
            return ReplicateTrainingEngine()
        raise ValueError(f"Unknown training location: {location}")

    @staticmethod
    def auto_select() -> tuple[str, TrainingEngine]:
        """自动选择：优先本地（VRAM≥8GB），否则云端"""
        local = LocalTrainingEngine()
        ok, _ = local.check_available()
        if ok:
            return "local", local
        return "replicate", ReplicateTrainingEngine()


__all__ = [
    "TrainingEngine",
    "TrainingParams",
    "TrainingResult",
    "LocalTrainingEngine",
    "ReplicateTrainingEngine",
    "TrainingEngineProvider",
]
