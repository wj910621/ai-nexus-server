"""GLM-4 LLM Provider (ZhipuAI API)

Task 13 (Phase 8 P1) — Spec Section 8.6

智谱 AI GLM-4：
- OpenAI 兼容 API（/v1/chat/completions）
- 模型：glm-4, glm-4-air, glm-4-flash, glm-4-long
- 支持流式响应（SSE）
"""
import json
import logging
import time
from typing import Optional

import httpx

from app.core.config import settings
from app.engines.base import GenerationResult, LLMProvider

logger = logging.getLogger(__name__)


class GLMProvider(LLMProvider):
    """GLM-4 LLM Provider (ZhipuAI API)"""

    name = "glm"
    display_name = "智谱 GLM-4 (OpenAI 兼容)"
    capability = "chat"
    is_local = False
    supported_models = ["glm-4", "glm-4-air", "glm-4-flash", "glm-4-long"]

    DEFAULT_MODEL = "glm-4"

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        timeout: int = 60,
    ) -> None:
        self.api_key = api_key or settings.glm_api_key
        self.api_base = api_base or settings.glm_api_base
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
        """对话生成（OpenAI 兼容）"""
        if not self.api_key:
            return GenerationResult(
                success=False, data="", content_type="text/plain",
                metadata={}, error="GLM API key 未配置",
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
                finish_reason = None
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
                            if choices[0].get("finish_reason"):
                                finish_reason = choices[0]["finish_reason"]

                return GenerationResult(
                    success=True, data=full_text, content_type="text/plain",
                    metadata={
                        "provider": self.name,
                        "model": model,
                        "finish_reason": finish_reason,
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
    provider_registry.register("llm", "glm", GLMProvider)
except Exception:
    pass
