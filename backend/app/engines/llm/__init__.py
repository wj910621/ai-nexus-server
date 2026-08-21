"""LLM 大语言模型引擎"""
from app.engines.llm.base import GenerationResult, LLMProvider
from app.engines.llm.deepseek import DeepSeekProvider


def get_default_provider() -> LLMProvider:
    """获取默认 LLM Provider（零成本默认策略：DeepSeek 需用户 API Key，但便宜）"""
    from app.core.config import settings
    if settings.jarvis_gateway_enabled:
        from app.engines.llm.jarvis_gateway import JarvisGatewayProvider
        return JarvisGatewayProvider()
    return DeepSeekProvider()


__all__ = ["LLMProvider", "GenerationResult", "DeepSeekProvider", "get_default_provider"]
