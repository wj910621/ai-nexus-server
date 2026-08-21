"""Kling 视频生成 Provider (Kuaishou API)

Task 10 (Phase 8 P1) — Spec Section 8.3

快手可灵 Kling API：
- 提交任务 → 轮询状态 → 下载视频
- JWT 鉴权（api_key + api_secret 签名）
- 状态枚举：submitted / processing / succeed / failed
"""
import asyncio
import base64
import hashlib
import hmac
import json
import logging
import time
from typing import Optional

import httpx

from app.core.config import settings
from app.engines.base import BaseEngine, GenerationResult

logger = logging.getLogger(__name__)


async def download_video(url: str, client: httpx.AsyncClient) -> bytes:
    resp = await client.get(url)
    resp.raise_for_status()
    return resp.content


class KlingProvider(BaseEngine):
    """Kling 可灵视频 Provider (Kuaishou API)"""

    name = "kling"
    display_name = "可灵 Kling (快手)"
    capability = "text2video"
    is_local = False
    supported_models = ["kling-v1", "kling-v1-pro"]

    DEFAULT_MODEL = "kling-v1"
    SUBMIT_PATH = "/v1/videos/text2video"
    QUERY_PATH = "/v1/videos/query"

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        api_base: Optional[str] = None,
        timeout: int = 120,
    ) -> None:
        self.api_key = api_key or settings.kling_api_key
        self.api_secret = api_secret or settings.kling_api_secret
        self.api_base = api_base or settings.kling_api_base
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        self._initialized = False

    async def initialize(self) -> None:
        if not self.api_key:
            return
        self._client = httpx.AsyncClient(timeout=self.timeout)
        self._initialized = True

    def _generate_jwt(self) -> str:
        """生成快手 JWT token（HS256 签名）"""
        header = {"alg": "HS256", "typ": "JWT"}
        now = int(time.time())
        payload = {
            "iss": self.api_key,
            "exp": now + 1800,
            "nbf": now - 5,
            "iat": now,
        }
        header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).rstrip(b"=").decode()
        payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
        signing_input = f"{header_b64}.{payload_b64}".encode()
        signature = hmac.new(self.api_secret.encode(), signing_input, hashlib.sha256).digest()
        sig_b64 = base64.urlsafe_b64encode(signature).rstrip(b"=").decode()
        return f"{header_b64}.{payload_b64}.{sig_b64}"

    async def text2video(
        self,
        prompt: str,
        duration: int = 5,
        fps: int = 24,
        resolution: str = "720p",
        model: str = DEFAULT_MODEL,
        max_poll_seconds: int = 300,
        poll_interval: float = 5.0,
        **kwargs,
    ) -> GenerationResult:
        """文生视频"""
        if not self.api_key:
            return GenerationResult(
                success=False, data=b"", content_type="video/mp4",
                metadata={}, error="Kling API key 未配置",
            )
        if not self._initialized:
            await self.initialize()

        submit_body = {
            "model_name": model,
            "prompt": prompt,
            "duration": duration,
            "fps": fps,
            "resolution": resolution,
        }
        submit_body.update(kwargs)

        try:
            submit_url = f"{self.api_base}{self.SUBMIT_PATH}"
            jwt_token = self._generate_jwt()
            headers = {
                "Authorization": f"Bearer {jwt_token}",
                "Content-Type": "application/json",
            }
            resp = await self._client.post(submit_url, json=submit_body, headers=headers)
            resp.raise_for_status()
            data = resp.json().get("data", {})
            task_id = data.get("task_id")
            if not task_id:
                return GenerationResult(
                    success=False, data=b"", content_type="video/mp4",
                    metadata={}, error=f"Kling 未返回 task_id: {resp.text[:200]}",
                )

            query_url = f"{self.api_base}{self.QUERY_PATH}"
            deadline = time.time() + max_poll_seconds
            while time.time() < deadline:
                q_resp = await self._client.get(
                    query_url,
                    params={"task_id": task_id},
                    headers={"Authorization": f"Bearer {self._generate_jwt()}"},
                )
                q_resp.raise_for_status()
                q_data = q_resp.json().get("data", {})
                status = q_data.get("task_status")
                if status == "succeed":
                    videos = q_data.get("task_result", {}).get("videos", [])
                    if not videos:
                        return GenerationResult(
                            success=False, data=b"", content_type="video/mp4",
                            metadata={"task_id": task_id}, error="任务完成但无视频",
                        )
                    video_url = videos[0].get("url")
                    video_bytes = await download_video(video_url, self._client)
                    return GenerationResult(
                        success=True, data=video_bytes, content_type="video/mp4",
                        metadata={
                            "provider": self.name,
                            "model": model,
                            "task_id": task_id,
                            "video_url": video_url,
                        },
                    )
                if status == "failed":
                    err = q_data.get("task_status_msg", "Unknown error")
                    return GenerationResult(
                        success=False, data=b"", content_type="video/mp4",
                        metadata={"task_id": task_id}, error=err,
                    )
                await asyncio.sleep(poll_interval)

            return GenerationResult(
                success=False, data=b"", content_type="video/mp4",
                metadata={"task_id": task_id},
                error=f"任务超时（{max_poll_seconds}s）",
            )
        except httpx.HTTPStatusError as exc:
            return GenerationResult(
                success=False, data=b"", content_type="video/mp4",
                metadata={}, error=f"HTTP {exc.response.status_code}: {exc.response.text[:200]}",
            )
        except Exception as exc:
            return GenerationResult(
                success=False, data=b"", content_type="video/mp4",
                metadata={}, error=f"{type(exc).__name__}: {exc}",
            )

    async def health_check(self) -> bool:
        try:
            if not self._client:
                await self.initialize()
            result = await self.text2video(prompt="hi", duration=2, max_poll_seconds=60)
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
    provider_registry.register("video", "kling", KlingProvider)
except Exception:
    pass
