"""Provider 注册表 - 按引擎类型分组

P1: 多 Provider 抽象层核心

所有 Provider 在模块导入时通过 @register 装饰器或 register() 方法自动注册。
ProviderRouter 通过此注册表查找可用的 Provider。
"""
from typing import Type

from app.engines.base import BaseEngine


class ProviderRegistry:
    """Provider 注册表 - 按引擎类型分组

    支持的引擎类型: image / video / llm / tts
    """

    _registry: dict[str, dict[str, Type[BaseEngine]]] = {
        "image": {},
        "video": {},
        "llm": {},
        "tts": {},
    }

    @classmethod
    def register(
        cls,
        engine_type: str,
        provider_name: str,
        provider_class: Type[BaseEngine],
    ) -> None:
        """注册 Provider

        Args:
            engine_type: 引擎类型（image/video/llm/tts）
            provider_name: Provider 名（如 "seedream"、"flux"）
            provider_class: Provider 类

        Raises:
            ValueError: 未知引擎类型
        """
        if engine_type not in cls._registry:
            raise ValueError(f"未知引擎类型: {engine_type}")
        cls._registry[engine_type][provider_name] = provider_class

    @classmethod
    def get(
        cls,
        engine_type: str,
        provider_name: str,
    ) -> Type[BaseEngine]:
        """获取 Provider 类

        Raises:
            KeyError: 未注册的 Provider
        """
        providers = cls._registry.get(engine_type, {})
        if provider_name not in providers:
            raise KeyError(f"未注册的 Provider: {engine_type}/{provider_name}")
        return providers[provider_name]

    @classmethod
    def list_providers(cls, engine_type: str) -> list[str]:
        """列出某引擎类型的所有 Provider 名"""
        return list(cls._registry.get(engine_type, {}).keys())

    @classmethod
    def list_all(cls) -> dict[str, list[str]]:
        """列出所有注册的 Provider（按引擎类型分组）"""
        return {
            engine_type: list(providers.keys())
            for engine_type, providers in cls._registry.items()
        }


# 模块级单例 - 供 Provider 模块调用 provider_registry.register()
provider_registry = ProviderRegistry
