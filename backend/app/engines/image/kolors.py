"""Kolors 图像生成 Provider (Kuaishou API)

Task 15 (Phase 8 P1) — Spec Section 8.6

快手可图 Kolors API：
- 提交任务 → 轮询 → 下载图片
- JWT 鉴权（与 Kling 共用 _generate_jwt 模式）
- 支持文生图
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
from app.engines.base import GenerationResult, ImageGenProvider

logger = logging.getLogger(__name__)


async def download_image(url: str, client: httpx.AsyncClient) -> bytes:
    resp = await client.get(url)
    resp.raise_for_status()
    return resp.content


class KolorsProvider(ImageGenProvider):
    """Kolors 可图图像 Provider (Kuaishou API)"""

    name = "kolors"
    display_name = "可图 Kolors (快手)"
    capability = "text2img"
    is_local = False
    supported_models = ["kolors-v1", "kolors-v1-pro"]

    DEFAULT_MODEL = "kolors-v1"
    SUBMIT_PATH = "/v1/images/text2image"
    QUERY_PATH = "/v1/images/query"

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        api_base: Optional[str] = None,
        timeout: int = 60,
    ) -> None:
        self.api_key = api_key or settings.kolors_api_key
        self.api_secret = api_secret or settings.kolors_api_secret
        self.api_base = api_base or settings.kolors_api_base
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        self._initialized = False

    async def initialize(self) -> None:
        if not self.api_key:
            return
        self._client = httpx.AsyncClient(timeout=self.timeout)
        self._initialized = True

    def _generate_jwt(self) -> str:
        """生成快手 JWT token"""
        header = {"alg": "HS256", "typ": "JWT"}
        now = int(time.time())
        payload = {"iss": self.api_key, "exp": now + 1800, "nbf": now - 5, "iat": now}
        h_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).rstrip(b"=").decode()
        p_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
        signing_input = f"{h_b64}.{p_b64}".encode()
        sig = hmac.new(self.api_secret.encode(), signing_input, hashlib.sha256).digest()
        s_b64 = base64.urlsafe_b64encode(sig).rstrip(b"=").decode()
        return f"{h_b64}.{p_b64}.{s_b64}"

    async def text2img(
        self,
        prompt: str,
        negative_prompt: str = "",
        width: int = 1024,
        height: int = 1024,
        seed: Optional[int] = None,
        model: str = DEFAULT_MODEL,
        max_poll_seconds: int = 120,
        poll_interval: float = 2.0,
        **kwargs,
    ) -> GenerationResult:
        if not self.api_key:
            return GenerationResult(
                success=False, data=b"", content_type="image/png",
                metadata={}, error="Kolors API key 未配置",
            )
        if not self._initialized:
            await self.initialize()

        submit_body = {
            "model_name": model,
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "width": width,
            "height": height,
            "seed": seed or 0,
        }
        submit_body.update(kwargs)

        try:
            submit_url = f"{self.api_base}{self.SUBMIT_PATH}"
            headers = {
                "Authorization": f"Bearer {self._generate_jwt()}",
                "Content-Type": "application/json",
            }
            resp = await self._client.post(submit_url, json=submit_body, headers=headers)
            resp.raise_for_status()
            task_id = resp.json().get("data", {}).get("task_id")
            if not task_id:
                return GenerationResult(
                    success=False, data=b"", content_type="image/png",
                    metadata={}, error=f"Kolors 未返回 task_id: {resp.text[:200]}",
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
                    images = q_data.get("task_result", {}).get("images", [])
                    if not images:
                        return GenerationResult(
                            success=False, data=b"", content_type="image/png",
                            metadata={"task_id": task_id}, error="任务完成但无图片",
                        )
                    image_bytes = await download_image(images[0].get("url"), self._client)
                    return GenerationResult(
                        success=True, data=image_bytes, content_type="image/png",
                        metadata={
                            "provider": self.name,
                            "model": model,
                            "task_id": task_id,
                        },
                    )
                if status == "failed":
                    err = q_data.get("task_status_msg", "Unknown error")
                    return GenerationResult(
                        success=False, data=b"", content_type="image/png",
                        metadata={"task_id": task_id}, error=err,
                    )
                await asyncio.sleep(poll_interval)

            return GenerationResult(
                success=False, data=b"", content_type="image/png",
                metadata={"task_id": task_id},
                error=f"任务超时（{max_poll_seconds}s）",
            )
        except httpx.HTTPStatusError as exc:
            return GenerationResult(
                success=False, data=b"", content_type="image/png",
                metadata={}, error=f"HTTP {exc.response.status_code}: {exc.response.text[:200]}",
            )
        except Exception as exc:
            return GenerationResult(
                success=False, data=b"", content_type="image/png",
                metadata={}, error=f"{type(exc).__name__}: {exc}",
            )

    async def health_check(self) -> bool:
        try:
            if not self._client:
                await self.initialize()
            result = await self.text2img(prompt="hi", width=256, height=256, max_poll_seconds=30)
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
    provider_registry.register("image", "kolors", KolorsProvider)
except Exception:
    pass
