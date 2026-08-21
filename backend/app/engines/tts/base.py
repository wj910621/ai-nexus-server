"""TTS 语音合成 Provider 抽象基类（已在 engines/base.py 定义，此处重导出）"""
from app.engines.base import GenerationResult, TTSProvider

__all__ = ["TTSProvider", "GenerationResult"]
