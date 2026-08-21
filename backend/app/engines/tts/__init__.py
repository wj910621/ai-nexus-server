"""TTS 语音合成引擎"""
from app.engines.tts.base import GenerationResult, TTSProvider
from app.engines.tts.edge_tts import EdgeTTSProvider


def get_default_provider() -> TTSProvider:
    """获取默认 TTS 语音合成 Provider（零成本默认策略：Edge TTS 免费）"""
    return EdgeTTSProvider()


__all__ = ["TTSProvider", "GenerationResult", "EdgeTTSProvider", "get_default_provider"]
