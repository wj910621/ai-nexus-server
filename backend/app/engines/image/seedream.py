"""Seedream 图像生成 Provider (Volcano API)

Task 8 (Phase 8 P1) — Spec Section 8.1

火山引擎即梦 Seedream API：
- 提交异步任务 → 轮询状态 → 下载图片
- 使用 V4 签名（api_key + api_secret）
- 支持文生图 / 图生图
- 失败重试与超时由 ProviderFailover 兜底
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
from app.engines.base import GenerationResult, ImageGenProvider

logger = logging.getLogger(__name__)


async def download_image(url: str, client: httpx.AsyncClient) -> bytes:
    """下载图片 bytes"""
    resp = await client.get(url)
    resp.raise_for_status()
    return resp.content


class SeedreamProvider(ImageGenProvider):
    """Seedream 即梦图像 Provider (Volcano API)"""

    name = "seedream"
    display_name = "即梦 Seedream (火山引擎)"
    capability = "text2img,img2img"
    is_local = False
    supported_models = ["seedream-3.0", "seedream-2.0"]

    DEFAULT_MODEL = "seedream-3.0"
    SUBMIT_PATH = "/v1/visual/text2image"
    QUERY_PATH = "/v1/visual/query_task"

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        api_base: Optional[str] = None,
        timeout: int = 60,
    ) -> None:
        self.api_key = api_key or settings.volcano_api_key
        self.api_secret = api_secret or settings.volcano_api_secret
        self.api_base = api_base or settings.volcano_api_base
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        self._initialized = False

    async def initialize(self) -> None:
        """初始化 HTTP 客户端"""
        if not self.api_key:
            return
        self._client = httpx.AsyncClient(timeout=self.timeout)
        self._initialized = True

    def _sign_request(self, method: str, path: str, body: str) -> dict:
        """生成 Volcano V4 签名 headers

        简化版签名：HMAC-SHA256(api_secret, method + path + body + timestamp)
        """
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
        """文生图 - 异步任务轮询"""
        if not self.api_key:
            return GenerationResult(
                success=False, data=b"", content_type="image/png",
                metadata={}, error="Volcano API key 未配置",
            )
        if not self._initialized:
            await self.initialize()

        submit_body = {
            "req_key": model,
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "width": width,
            "height": height,
            "seed": seed or 0,
            "return_url": True,
        }
        submit_body.update(kwargs)
        body_str = json.dumps(submit_body)

        try:
            # 1. 提交任务
            submit_url = f"{self.api_base}{self.SUBMIT_PATH}"
            headers = self._sign_request("POST", self.SUBMIT_PATH, body_str)
            resp = await self._client.post(submit_url, content=body_str, headers=headers)
            resp.raise_for_status()
            task_id = resp.json().get("data", {}).get("task_id")
            if not task_id:
                return GenerationResult(
                    success=False, data=b"", content_type="image/png",
                    metadata={}, error=f"Volcano 未返回 task_id: {resp.text[:200]}",
                )

            # 2. 轮询任务状态
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
                    image_urls = data.get("image_urls", [])
                    if not image_urls:
                        return GenerationResult(
                            success=False, data=b"", content_type="image/png",
                            metadata={"task_id": task_id},
                            error="任务完成但无图片 URL",
                        )
                    image_bytes = await download_image(image_urls[0], self._client)
                    return GenerationResult(
                        success=True, data=image_bytes, content_type="image/png",
                        metadata={
                            "provider": self.name,
                            "model": model,
                            "task_id": task_id,
                            "image_url": image_urls[0],
                        },
                    )
                if status == "failed":
                    err = data.get("error_msg", "Unknown error")
                    return GenerationResult(
                        success=False, data=b"", content_type="image/png",
                        metadata={"task_id": task_id},
                        error=err,
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
        """健康检查 - 最小生成请求"""
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
    provider_registry.register("image", "seedream", SeedreamProvider)
except Exception:
    pass
