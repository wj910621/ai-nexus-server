"""Doubao LLM Provider (Volcano Ark API)

Task 14 (Phase 8 P1) — Spec Section 8.6

火山引擎豆包：
- OpenAI 兼容 API（/api/v3/chat/completions）
- 模型：doubao-pro-32k, doubao-pro-128k, doubao-lite-32k
- 支持流式响应
"""
import json
import logging
import time
from typing import Optional

import httpx

from app.core.config import settings
from app.engines.base import GenerationResult, LLMProvider

logger = logging.getLogger(__name__)


class DoubaoProvider(LLMProvider):
    """Doubao 豆包 LLM Provider (Volcano Ark API)"""

    name = "doubao"
    display_name = "豆包 Doubao (火山 Ark)"
    capability = "chat"
    is_local = False
    supported_models = ["doubao-pro-32k", "doubao-pro-128k", "doubao-lite-32k"]

    DEFAULT_MODEL = "doubao-pro-32k"

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        timeout: int = 60,
    ) -> None:
        self.api_key = api_key or settings.doubao_api_key
        self.api_base = api_base or settings.doubao_api_base
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        self._initialized = False

    async def initialize(self) -> None:
        if not self.api_key:
            return
        self._client = httpx.AsyncClient(timeout=self.timeout)
        self._initialized = True

    async def chat(
        self,
        messages: list[dict],
        model: str = DEFAULT_MODEL,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        stream: bool = False,
        **kwargs,
    ) -> GenerationResult:
        if not self.api_key:
            return GenerationResult(
                success=False, data="", content_type="text/plain",
                metadata={}, error="Doubao API key 未配置",
            )
        if not self._initialized:
            await self.initialize()

        start = time.time()
        url = f"{self.api_base}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }
        payload.update(kwargs)

        try:
            if stream:
                full_text = ""
                async with self._client.stream("POST", url, json=payload, headers=headers) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line or not line.startswith("data: "):
                            continue
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue
                        choices = chunk.get("choices", [])
                        if choices:
                            delta = choices[0].get("delta", {})
                            if "content" in delta:
                                full_text += delta["content"]
                return GenerationResult(
                    success=True, data=full_text, content_type="text/plain",
                    metadata={
                        "provider": self.name,
                        "model": model,
                        "elapsed_seconds": round(time.time() - start, 2),
                    },
                )
            else:
                resp = await self._client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                choices = data.get("choices", [])
                content = choices[0].get("message", {}).get("content", "") if choices else ""
                usage = data.get("usage", {})
                return GenerationResult(
                    success=True, data=content, content_type="text/plain",
                    metadata={
                        "provider": self.name,
                        "model": model,
                        "prompt_tokens": usage.get("prompt_tokens", 0),
                        "completion_tokens": usage.get("completion_tokens", 0),
                        "total_tokens": usage.get("total_tokens", 0),
                        "elapsed_seconds": round(time.time() - start, 2),
                    },
                )
        except httpx.HTTPStatusError as exc:
            return GenerationResult(
                success=False, data="", content_type="text/plain",
                metadata={}, error=f"HTTP {exc.response.status_code}: {exc.response.text[:200]}",
            )
        except Exception as exc:
            return GenerationResult(
                success=False, data="", content_type="text/plain",
                metadata={}, error=f"{type(exc).__name__}: {exc}",
            )

    async def health_check(self) -> bool:
        try:
            if not self._client:
                await self.initialize()
            result = await self.chat(
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=1,
            )
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
    provider_registry.register("llm", "doubao", DoubaoProvider)
except Exception:
    pass
