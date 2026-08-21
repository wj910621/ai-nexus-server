"""Edge TTS 微软免费语音合成 Provider

文档：https://github.com/rany2/edge-tts
- 无需 API Key（调用微软 Edge 浏览器在线 TTS 接口）
- 支持中文/英文等多种语言声音
- 支持 rate/pitch/volume 调整
- 输出 MP3 格式
"""
import io
import time
from typing import Optional

from app.core.storage import storage
from app.engines.base import GenerationResult, TTSProvider

# 延迟导入 edge_tts（可选依赖）
try:
    import edge_tts
except ImportError:
    edge_tts = None


class EdgeTTSProvider(TTSProvider):
    """Edge TTS 微软免费语音合成"""

    name = "edge-tts"
    display_name = "Edge TTS (微软免费)"

    # 常用声音列表
    POPULAR_VOICES = {
        "zh-CN-XiaoxiaoNeural": "女声，活泼",
        "zh-CN-YunxiNeural": "男声，阳光",
        "zh-CN-YunyangNeural": "男声，专业",
        "zh-CN-XiaoyiNeural": "女声，温柔",
        "zh-CN-YunjianNeural": "男声，运动",
        "en-US-JennyNeural": "英文女声",
        "en-US-GuyNeural": "英文男声",
    }

    def __init__(self):
        self._initialized = False

    async def initialize(self) -> None:
        """初始化引擎（edge-tts 无需特殊初始化，仅标记状态）"""
        self._initialized = True

    @staticmethod
    def _format_percent(value: int) -> str:
        """将百分比 int 转为 edge-tts 格式：0 -> '+0%', 10 -> '+10%', -10 -> '-10%'"""
        if value >= 0:
            return f"+{value}%"
        return f"{value}%"

    @staticmethod
    def _format_pitch(value: int) -> str:
        """将音调 int 转为 edge-tts 格式：0 -> '+0Hz', 10 -> '+10Hz', -10 -> '-10Hz'"""
        if value >= 0:
            return f"+{value}Hz"
        return f"{value}Hz"

    async def synthesize(
        self,
        text: str,
        voice: str = "zh-CN-XiaoxiaoNeural",
        rate: int = 0,
        pitch: int = 0,
        volume: int = 0,
        output_format: str = "audio-24khz-48kbitrate-mono-mp3",
        **kwargs,
    ) -> GenerationResult:
        """
        文本转语音

        Args:
            text: 待合成文本
            voice: 声音名称（参考 POPULAR_VOICES）
            rate: 语速百分比（0 正常，正数加速，负数减速）
            pitch: 音调（0 正常，正数升调，负数降调）
            volume: 音量百分比（0 正常，正数放大，负数减小）
            output_format: 输出格式标识
        """
        if not self._initialized:
            await self.initialize()

        if edge_tts is None:
            return GenerationResult(
                success=False,
                data=b"",
                content_type="",
                metadata={},
                error="edge-tts 未安装，请执行 pip install edge-tts",
            )

        start_time = time.time()

        try:
            rate_str = self._format_percent(rate)
            pitch_str = self._format_pitch(pitch)
            volume_str = self._format_percent(volume)

            communicate = edge_tts.Communicate(
                text,
                voice,
                rate=rate_str,
                pitch=pitch_str,
                volume=volume_str,
            )

            # 异步流式收集音频字节到内存
            audio_buffer = io.BytesIO()
            async for chunk in communicate.stream():
                if chunk.get("type") == "audio":
                    audio_buffer.write(chunk["data"])

            audio_bytes = audio_buffer.getvalue()
            elapsed = time.time() - start_time

            # 保存到存储
            url_path = storage.save(audio_bytes, extension="mp3", subdir="audio")

            return GenerationResult(
                success=True,
                data=url_path,
                content_type="audio/mp3",
                metadata={
                    "provider": self.name,
                    "voice": voice,
                    "text_length": len(text),
                    "rate": rate,
                    "pitch": pitch,
                    "volume": volume,
                    "output_format": output_format,
                    "size_bytes": len(audio_bytes),
                    "elapsed_seconds": round(elapsed, 2),
                },
            )
        except Exception as e:
            return GenerationResult(
                success=False,
                data=b"",
                content_type="",
                metadata={},
                error=f"{type(e).__name__}: {str(e)}",
            )

    async def list_voices(self, language: Optional[str] = None) -> list[dict]:
        """
        获取可用声音列表

        Args:
            language: 语言前缀过滤（如 "zh" 返回所有中文声音）
        """
        if edge_tts is None:
            return []
        voices = await edge_tts.list_voices()
        if language:
            voices = [v for v in voices if v.get("Locale", "").startswith(language)]
        return voices

    async def health_check(self) -> bool:
        """健康检查 - edge_tts 可导入且已初始化"""
        if edge_tts is None:
            return False
        return self._initialized

    def get_info(self) -> dict:
        """获取引擎信息"""
        info = super().get_info()
        info["popular_voices"] = self.POPULAR_VOICES
        info["default_voice"] = "zh-CN-XiaoxiaoNeural"
        return info
