"""Seedance 视频生成 Provider (Volcano API)

Task 9 (Phase 8 P1) — Spec Section 8.2

火山引擎即梦 Seedance API：
- 提交异步任务 → 轮询状态（含进度）→ 下载 mp4
- 支持 WebSocket 进度推送（本任务先用 HTTP 轮询，WebSocket 在 P2）
- 与 Seedream 共用 V4 签名
"""
import asyncio
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
    """下载视频 bytes"""
    resp = await client.get(url)
    resp.raise_for_status()
    return resp.content


class SeedanceProvider(BaseEngine):
    """Seedance 即梦视频 Provider (Volcano API)"""

    name = "seedance"
    display_name = "即梦 Seedance (火山引擎视频)"
    capability = "text2video"
    is_local = False
    supported_models = ["seedance-1.0", "seedance-1.0-pro"]

    DEFAULT_MODEL = "seedance-1.0"
    SUBMIT_PATH = "/v1/visual/text2video"
    QUERY_PATH = "/v1/visual/query_video_task"

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        api_base: Optional[str] = None,
        timeout: int = 120,
    ) -> None:
        self.api_key = api_key or settings.volcano_api_key
        self.api_secret = api_secret or settings.volcano_api_secret
        self.api_base = api_base or settings.volcano_api_base
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        self._initialized = False

    async def initialize(self) -> None:
        if not self.api_key:
            return
        self._client = httpx.AsyncClient(timeout=self.timeout)
        self._initialized = True

    def _sign_request(self, method: str, path: str, body: str) -> dict:
        """生成 Volcano V4 签名 headers"""
        ts = str(int(time.time()))
        string_to_sign = f"{method}\n{path}\n{body}\n{ts}"
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

    async def text2video(
        self,
        prompt: str,
        duration: int = 5,
        fps: int = 24,
        resolution: str = "720p",
        seed: Optional[int] = None,
        model: str = DEFAULT_MODEL,
        max_poll_seconds: int = 300,
        poll_interval: float = 5.0,
        **kwargs,
    ) -> GenerationResult:
        """文生视频 - 异步任务轮询"""
        if not self.api_key:
            return GenerationResult(
                success=False, data=b"", content_type="video/mp4",
                metadata={}, error="Volcano API key 未配置",
            )
        if not self._initialized:
            await self.initialize()

        submit_body = {
            "req_key": model,
            "prompt": prompt,
            "duration": duration,
            "fps": fps,
            "resolution": resolution,
            "seed": seed or 0,
            "return_url": True,
        }
        submit_body.update(kwargs)
        body_str = json.dumps(submit_body)

        try:
            submit_url = f"{self.api_base}{self.SUBMIT_PATH}"
            headers = self._sign_request("POST", self.SUBMIT_PATH, body_str)
            resp = await self._client.post(submit_url, content=body_str, headers=headers)
            resp.raise_for_status()
            task_id = resp.json().get("data", {}).get("task_id")
            if not task_id:
                return GenerationResult(
                    success=False, data=b"", content_type="video/mp4",
                    metadata={}, error=f"Volcano 未返回 task_id: {resp.text[:200]}",
                )

            query_url = f"{self.api_base}{self.QUERY_PATH}"
            deadline = time.time() + max_poll_seconds
            while time.time() < deadline:
                q_headers = self._sign_request("GET", self.QUERY_PATH, "")
                q_resp = await self._client.get(
                    query_url, params={"task_id": task_id}, headers=q_headers
                )
                q_resp.raise_for_status()
                data = q_resp.json().get("data", {})
                status = data.get("status")
                if status == "done":
                    video_url = data.get("video_url")
                    if not video_url:
                        return GenerationResult(
                            success=False, data=b"", content_type="video/mp4",
                            metadata={"task_id": task_id},
                            error="任务完成但无视频 URL",
                        )
                    video_bytes = await download_video(video_url, self._client)
                    return GenerationResult(
                        success=True, data=video_bytes, content_type="video/mp4",
                        metadata={
                            "provider": self.name,
                            "model": model,
                            "task_id": task_id,
                            "video_url": video_url,
                            "progress": 100,
                        },
                    )
                if status == "failed":
                    err = data.get("error_msg", "Unknown error")
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
    provider_registry.register("video", "seedance", SeedanceProvider)
except Exception:
    pass
