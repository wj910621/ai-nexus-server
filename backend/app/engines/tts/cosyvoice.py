"""CosyVoice 本地语音合成 Provider

Task 19 (Phase 8 P1) — Spec Section 8.7

FunAudioLLM CosyVoice：
- 阿里通义实验室推出的开源 TTS 模型
- 支持多语言/多音色/零样本克隆
- 模型常驻显存
- torch 是可选依赖
"""
import logging
from io import BytesIO
from typing import Optional

from app.engines.base import GenerationResult, TTSProvider

logger = logging.getLogger(__name__)

# torch / torchaudio 是可选依赖
try:
    import torch
    import torchaudio
    _TORCH_AVAILABLE = True
except ImportError:
    torch = None  # type: ignore
    torchaudio = None  # type: ignore
    _TORCH_AVAILABLE = False


class CosyVoiceProvider(TTSProvider):
    """CosyVoice 本地 TTS Provider"""

    name = "cosyvoice"
    display_name = "CosyVoice (本地)"
    capability = "tts"
    is_local = True
    supported_models = ["FunAudioLLM/CosyVoice-300M", "FunAudioLLM/CosyVoice2-0.5B"]

    DEFAULT_MODEL = "FunAudioLLM/CosyVoice-300M"

    def __init__(
        self,
        model_id: str = DEFAULT_MODEL,
        device: Optional[str] = None,
    ) -> None:
        self.model_id = model_id
        # P2: 通过 DeviceManager 获取设备（NVIDIA cuda:0 / AMD cuda:0 / Intel xpu:0 / cpu）
        from app.core.device_manager import DeviceManager
        dm = DeviceManager.get_instance()
        self.device = device or dm.get_device_string("tts")
        self.dtype = dm.get_torch_dtype("tts")
        self._model = None
        self._initialized = False

    async def initialize(self) -> None:
        """加载 CosyVoice 模型"""
        if not _TORCH_AVAILABLE:
            logger.warning("torch 未安装，CosyVoiceProvider 不可用")
            return

        # CosyVoice 模型加载（通过 transformers 或直接 from_pretrained）
        try:
            from cosyvoice.cli.cosyvoice import CosyVoice  # type: ignore
            self._model = CosyVoice(self.model_id)
            self._initialized = True
            logger.info(f"CosyVoice loaded: {self.model_id}")
        except ImportError:
            # 退回到 transformers 加载
            logger.warning("cosyvoice 包未安装，CosyVoiceProvider 不可用")

    async def synthesize(
        self,
        text: str,
        voice: str = "中文女",
        rate: int = 0,
        pitch: int = 0,
        speed_ratio: float = 1.0,
        **kwargs,
    ) -> GenerationResult:
        """文本转语音"""
        if not self._initialized or self._model is None:
            return GenerationResult(
                success=False, data=b"", content_type="audio/wav",
                metadata={}, error="CosyVoiceProvider 未初始化（模型未加载）",
            )

        try:
            # CosyVoice 推理
            audios = list(self._model.inference_sft(
                tts_text=text,
                prompt_text=kwargs.get("prompt_text", ""),
                prompt_audio=kwargs.get("prompt_audio", ""),
            ))

            if not audios:
                return GenerationResult(
                    success=False, data=b"", content_type="audio/wav",
                    metadata={}, error="CosyVoice 返回空音频",
                )

            # 转 WAV bytes
            buf = BytesIO()
            audio = audios[0]
            if hasattr(audio, "tobytes"):
                # tensor / numpy array；延迟导入便于测试 mock
                import torchaudio  # noqa: E402
                torchaudio.save(buf, audio, 22050, format="wav")
            wav_bytes = buf.getvalue()

            return GenerationResult(
                success=True, data=wav_bytes, content_type="audio/wav",
                metadata={
                    "provider": self.name,
                    "model": self.model_id,
                    "voice": voice,
                    "speed_ratio": speed_ratio,
                },
            )
        except Exception as exc:
            return GenerationResult(
                success=False, data=b"", content_type="audio/wav",
                metadata={}, error=f"{type(exc).__name__}: {exc}",
            )

    async def health_check(self) -> bool:
        try:
            if not self._initialized:
                await self.initialize()
            result = await self.synthesize(text="hi")
            return result.success
        except Exception:
            return False

    def get_info(self) -> dict:
        info = super().get_info()
        info["model_id"] = self.model_id
        info["torch_available"] = _TORCH_AVAILABLE
        return info


# 模块级注册 - 导入时自动触发
try:
    from app.engines.registry import provider_registry
    provider_registry.register("tts", "cosyvoice", CosyVoiceProvider)
except Exception:
    pass
