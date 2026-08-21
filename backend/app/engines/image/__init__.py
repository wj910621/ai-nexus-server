"""图像生成引擎"""
from app.engines.image.base import GenerationResult, ImageGenProvider
from app.engines.image.pollinations import PollinationsProvider


def get_default_provider() -> ImageGenProvider:
    """获取默认图像生成 Provider"""
    return PollinationsProvider()


__all__ = ["ImageGenProvider", "GenerationResult", "PollinationsProvider", "get_default_provider"]
