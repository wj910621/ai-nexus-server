"""DeepSeek LLM Provider (OpenAI 兼容)

文档：https://api-docs.deepseek.com
- 需要 API Key（用户自行申请，价格便宜）
- 完全兼容 OpenAI API 格式
- 可用模型：deepseek-chat (V3), deepseek-reasoner (R1)
- 支持流式响应 (SSE)
"""
import json
import time
from typing import AsyncGenerator, Optional

import httpx

from app.core.config import settings
from app.core.http_client import http_client_factory
from app.engines.base import GenerationResult, LLMProvider


class DeepSeekProvider(LLMProvider):
    """DeepSeek LLM Provider (OpenAI 兼容)"""

    name = "deepseek"
    display_name = "DeepSeek (OpenAI 兼容)"

    AVAILABLE_MODELS = ["deepseek-chat", "deepseek-reasoner"]
    DEFAULT_MODEL = "deepseek-chat"

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        timeout: int = 60,
    ):
        """
        初始化 DeepSeek Provider

        Args:
            api_key: DeepSeek API Key（默认从 settings.deepseek_api_key 读取）
            api_base: API 基础地址（默认从 settings.deepseek_api_base 读取）
            timeout: 请求超时时间（秒）
        """
        self.api_key = api_key if api_key is not None else settings.deepseek_api_key
        self.api_base = api_base if api_base is not None else settings.deepseek_api_base
        self.timeout = timeout
        self._initialized = False
        self.client: Optional[httpx.AsyncClient] = None
        self._cache = None  # 新增：SemanticCache 实例（可选）

    def set_cache(self, cache) -> None:
        """注入 SemanticCache 实例（可选，由 EngineManager 调用）"""
        self._cache = cache

    async def initialize(self) -> None:
        """初始化 HTTP 客户端 (Task 11: 共享 HTTP/2 client)

        验证 api_key 非空，建立 httpx.AsyncClient，标记 _initialized=True。
        若 api_key 为空，则不建立客户端（chat 方法会返回错误）。
        """
        if not self.api_key:
            # api_key 为空，不建立客户端，chat() 会返回 success=False
            return
        self.client = http_client_factory.get_client(
            self.api_base,
            timeout=self.timeout,
        )
        self._initialized = True

    async def chat(
        self,
        messages: list[dict],
        model: str = "deepseek-chat",
        temperature: float = 0.7,
        max_tokens: int = 2000,
        stream: bool = False,
        user_id: int = 0,
        **kwargs,
    ) -> GenerationResult:
        """对话生成（集成 SemanticCache）

        缓存策略：
        - streaming=True → 跳过缓存
        - max_tokens < 100 → 跳过缓存（短回复不值得缓存）
        - 其余情况 → lookup，未命中调 API 后 store

        Args:
            messages: OpenAI 格式消息列表
            model: 模型名称 (deepseek-chat, deepseek-reasoner)
            temperature: 温度参数
            max_tokens: 最大生成 token 数
            stream: 是否使用流式响应（SSE）
            user_id: 用户 ID（用于缓存隔离）
            **kwargs: 其他 OpenAI 兼容参数
        """
        if not self.api_key:
            return GenerationResult(
                success=False,
                data="",
                content_type="text/plain",
                metadata={},
                error="DeepSeek API key 未配置",
            )

        if not self._initialized:
            await self.initialize()

        # 缓存启用条件
        cache_enabled = (
            self._cache is not None
            and not stream
            and max_tokens >= settings.semantic_cache_min_max_tokens
            and settings.semantic_cache_enabled
        )

        # 计算 system_prompt_hash
        system_prompt_hash = ""
        for msg in messages:
            if msg.get("role") == "system":
                import hashlib
                system_prompt_hash = hashlib.sha256(
                    msg.get("content", "").encode("utf-8")
                ).hexdigest()[:16]
                break

        # 缓存查询
        if cache_enabled:
            user_query = ""
            for msg in reversed(messages):
                if msg.get("role") == "user":
                    user_query = msg.get("content", "")
                    break
            cached = await self._cache.lookup(
                user_id=user_id,
                query=user_query,
                system_prompt_hash=system_prompt_hash,
                model=model,
            )
            if cached is not None:
                cached.metadata["cached"] = True
                return cached

        start_time = time.time()

        url = f"{self.api_base}/v1/chat/completions"
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
                # 流式响应：逐行读取 SSE，拼接 content
                full_text = ""
                finish_reason = None
                usage = {}
                async with self.client.stream(
                    "POST", url, json=payload, headers=headers
                ) as resp:
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
                        if "usage" in chunk:
                            usage = chunk["usage"]

                elapsed = time.time() - start_time

                return GenerationResult(
                    success=True,
                    data=full_text,
                    content_type="text/plain",
                    metadata={
                        "provider": self.name,
                        "model": model,
                        "prompt_tokens": usage.get("prompt_tokens", 0),
                        "completion_tokens": usage.get("completion_tokens", 0),
                        "total_tokens": usage.get("total_tokens", 0),
                        "finish_reason": finish_reason,
                        "elapsed_seconds": round(elapsed, 2),
                        "model_used": model,
                    },
                )
            else:
                # 非流式响应
                resp = await self.client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()

                elapsed = time.time() - start_time

                choices = data.get("choices", [])
                message = choices[0].get("message", {}) if choices else {}
                content = message.get("content", "")
                finish_reason = (
                    choices[0].get("finish_reason") if choices else None
                )
                usage = data.get("usage", {})

                result = GenerationResult(
                    success=True,
                    data=content,
                    content_type="text/plain",
                    metadata={
                        "provider": self.name,
                        "model": model,
                        "prompt_tokens": usage.get("prompt_tokens", 0),
                        "completion_tokens": usage.get("completion_tokens", 0),
                        "total_tokens": usage.get("total_tokens", 0),
                        "finish_reason": finish_reason,
                        "elapsed_seconds": round(elapsed, 2),
                        "model_used": model,
                    },
                )

                # 缓存存储（仅在成功时）
                if cache_enabled and result.success:
                    user_query = ""
                    for msg in reversed(messages):
                        if msg.get("role") == "user":
                            user_query = msg.get("content", "")
                            break
                    try:
                        await self._cache.store(
                            user_id=user_id,
                            query=user_query,
                            response=content,
                            system_prompt_hash=system_prompt_hash,
                            model=model,
                        )
                    except Exception:
                        # 缓存存储失败不影响主流程
                        pass

                return result
        except httpx.HTTPStatusError as e:
            return GenerationResult(
                success=False,
                data="",
                content_type="text/plain",
                metadata={},
                error=f"HTTP {e.response.status_code}: {e.response.text[:200]}",
            )
        except Exception as e:
            return GenerationResult(
                success=False,
                data="",
                content_type="text/plain",
                metadata={},
                error=f"{type(e).__name__}: {str(e)}",
            )

    async def chat_stream(
        self,
        messages: list[dict],
        model: str = "deepseek-chat",
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """流式聊天 - 逐 token yield

        与 `chat()` 不同，本方法不做错误吞噬：上游连接异常会抛出，
        由调用方（SSE 端点）捕获并转为 SSE error 事件 + 退款。

        Args:
            messages: OpenAI 格式消息列表
            model: 模型名称
            temperature: 温度参数
            max_tokens: 最大生成 token 数
            **kwargs: 其他 OpenAI 兼容参数

        Yields:
            str: 每个增量 token (delta.content)
        """
        if not self.api_key:
            raise RuntimeError("DeepSeek API key 未配置")

        if not self._initialized:
            await self.initialize()

        url = f"{self.api_base}/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        payload.update(kwargs)

        # NOTE: 不在此捕获异常 — 让上层 SSE 包装器处理错误事件 + 退款
        async with self.client.stream(
            "POST", url, json=payload, headers=headers
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                    delta = chunk["choices"][0]["delta"].get("content", "")
                    if delta:
                        yield delta
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue

    async def health_check(self) -> bool:
        """健康检查 - 发送最小请求测试连接"""
        try:
            if not self.client:
                await self.initialize()
            result = await self.chat(
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=1,
            )
            return result.success
        except Exception:
            return False

    def get_info(self) -> dict:
        """获取引擎信息"""
        info = super().get_info()
        info["available_models"] = self.AVAILABLE_MODELS
        info["default_model"] = self.DEFAULT_MODEL
        info["api_base"] = self.api_base
        info["api_key_configured"] = bool(self.api_key)
        return info


# 商业化瘦身（2026-09-02）：默认 LLM 引擎补注册进 ProviderRegistry，
# 使 ProviderRouter / get_engine_routed 能路由到 deepseek（低价主力）。
from app.engines.registry import provider_registry  # noqa: E402

provider_registry.register("llm", "deepseek", DeepSeekProvider)
