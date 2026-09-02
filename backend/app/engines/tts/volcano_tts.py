"""Volcano TTS 语音合成 Provider (Volcano API)

Task 18 (Phase 8 P1) — Spec Section 8.6

火山引擎语音合成：
- POST /api/v1/tts 返回 base64 音频
- 支持 MP3/WAV/PCM 格式
- 多种音色（zh_female_qingxin 等）
"""
import base64
import hashlib
import hmac
import logging
import time
from typing import Optional

import httpx

from app.core.config import settings
from app.engines.base import GenerationResult, TTSProvider

logger = logging.getLogger(__name__)


class VolcanoTTSProvider(TTSProvider):
    """火山引擎 TTS Provider"""

    name = "volcano_tts"
    display_name = "火山引擎 TTS"
    capability = "tts"
    is_local = False
    supported_models = ["volcano-tts-1"]

    DEFAULT_VOICE = "zh_female_qingxin"
    TTS_PATH = "/tts"

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        api_base: Optional[str] = None,
        timeout: int = 30,
    ) -> None:
        self.api_key = api_key or settings.volcano_tts_api_key
        self.api_secret = api_secret or settings.volcano_tts_api_secret
        self.api_base = api_base or settings.volcano_tts_api_base
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        self._initialized = False

    async def initialize(self) -> None:
        if not self.api_key:
            return
        self._client = httpx.AsyncClient(timeout=self.timeout)
        self._initialized = True

    def _sign_request(self, body: str) -> dict:
        ts = str(int(time.time()))
        string_to_sign = f"{body}\n{ts}"
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return {
            "Authorization": f"Volc-Sign {self.api_key}:{signature}",
            "Volc-Date": ts,
            "Content-Type": "application/json",
        }

    async def synthesize(
        self,
        text: str,
        voice: str = DEFAULT_VOICE,
        rate: int = 0,
        pitch: int = 0,
        speed_ratio: float = 1.0,
        volume_ratio: float = 1.0,
        audio_format: str = "mp3",
        **kwargs,
    ) -> GenerationResult:
        """文本转语音"""
        if not self.api_key:
            return GenerationResult(
                success=False, data=b"", content_type="audio/mp3",
                metadata={}, error="Volcano TTS API key 未配置",
            )
        if not self._initialized:
            await self.initialize()

        import json as _json
        payload = {
            "app": {
                "appid": self.api_key,
                "token": getattr(settings, "volcano_tts_app_token", "") or "",
                "cluster": "volcano_tts",
            },
            "user": {"uid": "comicstudio"},
            "audio": {
                "voice_type": voice,
                "encoding": audio_format,
                "speed_ratio": speed_ratio,
                "volume_ratio": volume_ratio,
                "pitch_ratio": pitch,
            },
            "request": {
                "reqid": f"req-{int(time.time()*1000)}",
                "text": text,
                "text_type": "plain",
                "operation": "query",
            },
        }
        payload.update(kwargs)
        body_str = _json.dumps(payload, ensure_ascii=False)

        try:
            url = f"{self.api_base}{self.TTS_PATH}"
            headers = self._sign_request(body_str)
            resp = await self._client.post(url, content=body_str.encode("utf-8"), headers=headers)
            resp.raise_for_status()
            data = resp.json()
            code = data.get("code")
            if code != 3000:
                err = data.get("message", f"Unknown error code: {code}")
                return GenerationResult(
                    success=False, data=b"", content_type="audio/mp3",
                    metadata={}, error=err,
                )

            audio_b64 = data.get("data", {}).get("audio", "")
            if not audio_b64:
                return GenerationResult(
                    success=False, data=b"", content_type="audio/mp3",
                    metadata={}, error="TTS 返回空音频",
                )

            audio_bytes = base64.b64decode(audio_b64)
            return GenerationResult(
                success=True, data=audio_bytes, content_type=f"audio/{audio_format}",
                metadata={
                    "provider": self.name,
                    "voice": voice,
                    "audio_format": audio_format,
                    "duration_seconds": kwargs.get("duration", 0),
                },
            )
        except httpx.HTTPStatusError as exc:
            return GenerationResult(
                success=False, data=b"", content_type="audio/mp3",
                metadata={}, error=f"HTTP {exc.response.status_code}: {exc.response.text[:200]}",
            )
        except Exception as exc:
            return GenerationResult(
                success=False, data=b"", content_type="audio/mp3",
                metadata={}, error=f"{type(exc).__name__}: {exc}",
            )

    async def health_check(self) -> bool:
        try:
            if not self._client:
                await self.initialize()
            result = await self.synthesize(text="hi")
            return result.success
        except Exception:
            return False

    def get_info(self) -> dict:
        info = super().get_info()
        info["api_base"] = self.api_base
        info["api_key_configured"] = bool(self.api_key)
        return info


# 模块级注册 - 导入时自动触发
try:
    from app.engines.registry import provider_registry
    provider_registry.register("tts", "volcano_tts", VolcanoTTSProvider)
except Exception:
    pass
