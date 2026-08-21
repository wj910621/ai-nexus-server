"""本地 TTS - Piper (CPU, fast neural TTS)

Task 15: Local AI Inference (Desktop)

使用 Piper neural TTS (VITS-based) 实现 ≤1s/MB 的语音合成。
支持多语言/多音色。

piper_tts 是可选依赖（仅桌面构建安装）。
"""
import io
import logging
import wave
from typing import Optional

from app.core.storage import storage
from app.engines.base import GenerationResult, TTSProvider
from app.engines.model_manager import model_manager

logger = logging.getLogger(__name__)


class LocalTTSProvider(TTSProvider):
    """本地 TTS Provider

    使用 Piper neural TTS (VITS-based) 实现 ≤1s/MB 的语音合成。
    支持多语言/多音色。
    """

    name = "local-tts"
    display_name = "Local TTS (Piper)"

    # 静态音色注册表
    AVAILABLE_VOICES = [
        {"name": "en_US-lessac-medium", "display_name": "English (US) - Lessac", "language": "en-US"},
        {"name": "en_GB-alan-medium", "display_name": "English (UK) - Alan", "language": "en-GB"},
        {"name": "zh_CN-huayan-medium", "display_name": "中文 - 华燕", "language": "zh-CN"},
    ]

    def __init__(self, model_name: str = "piper-en-lessac") -> None:
        self.model_name = model_name
        self._voice = None
        self._initialized = False

    async def initialize(self) -> None:
        self._initialized = True

    def _ensure_loaded(self) -> None:
        if self._voice is not None:
            return
        from piper.voice import PiperVoice

        model_path = model_manager.get_model_path(self.model_name)
        if model_path is None:
            raise RuntimeError(f"Model {self.model_name} not downloaded")

        self._voice = PiperVoice.load(model_path)

    async def synthesize(
        self,
        text: str,
        voice: str = "default",
        rate: int = 0,
        pitch: int = 0,
        **kwargs,
    ) -> GenerationResult:
        """Synthesize speech via Piper.

        Args:
            text: 待合成文本
            voice: 音色名称（参考 AVAILABLE_VOICES）
            rate: 语速百分比（Piper 不支持，仅作兼容参数）
            pitch: 音调百分比（Piper 不支持，仅作兼容参数）
        """
        try:
            self._ensure_loaded()
        except Exception as exc:
            return GenerationResult(
                success=False,
                data=b"",
                content_type="",
                metadata={"provider": self.name},
                error=f"{type(exc).__name__}: {exc}",
            )

        # Synthesize to WAV in memory
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wav_file:
            self._voice.synthesize_wav(text, wav_file)

        audio_bytes = buf.getvalue()
        # Save to storage
        url_path = storage.save(audio_bytes, extension="wav", subdir="audio")

        # Estimate duration: 32KB/s is approximate for 16kHz 16-bit mono WAV
        duration = len(audio_bytes) / 32000

        return GenerationResult(
            success=True,
            data=url_path,
            content_type="audio/wav",
            metadata={
                "provider": self.name,
                "voice": voice,
                "text_length": len(text),
                "model": self.model_name,
                "is_local": True,
                "duration": duration,
                "size_bytes": len(audio_bytes),
            },
        )

    async def list_voices(self, language: Optional[str] = None) -> list[dict]:
        """List available Piper voices (from registry)."""
        voices = list(self.AVAILABLE_VOICES)
        if language:
            voices = [v for v in voices if v["language"].startswith(language)]
        return voices

    async def health_check(self) -> bool:
        """Healthy when piper is importable."""
        try:
            from piper.voice import PiperVoice  # noqa: F401
            return True
        except ImportError:
            return False

    def get_info(self) -> dict:
        info = super().get_info()
        info["model"] = self.model_name
        info["is_local"] = True
        info["available_voices"] = self.AVAILABLE_VOICES
        info["default_voice"] = "en_US-lessac-medium"
        return info
