"""角色一致性引擎"""
from app.engines.character.base import CharacterConsistencyProvider, GenerationResult
from app.engines.character.soft_provider import SoftConsistencyProvider


def get_default_provider() -> CharacterConsistencyProvider:
    """获取默认角色一致性 Provider（零成本默认策略：软一致性，无需 GPU）"""
    return SoftConsistencyProvider()


__all__ = [
    "CharacterConsistencyProvider",
    "GenerationResult",
    "SoftConsistencyProvider",
    "get_default_provider",
]
