"""Tests for GLMProvider (ZhipuAI API)."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from app.engines.base import GenerationResult
from app.engines.llm.glm import GLMProvider


@pytest.fixture
def provider():
    p = GLMProvider(
        api_key="test-glm-key",
        api_base="https://open.bigmodel.cn/api/paas/v4",
    )
    p._client = AsyncMock(spec=httpx.AsyncClient)
    p._initialized = True
    return p


@pytest.mark.asyncio
async def test_chat_success(provider):
    """对话成功"""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "choices": [{
            "message": {"content": "你好，我是 GLM-4"},
            "finish_reason": "stop",
        }],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
    }
    provider._client.post.return_value = resp

    result = await provider.chat(
        messages=[{"role": "user", "content": "你是谁"}],
        model="glm-4",
        max_tokens=100,
    )
    assert result.success is True
    assert result.data == "你好，我是 GLM-4"
    assert result.metadata["provider"] == "glm"
    assert result.metadata["model"] == "glm-4"
    assert result.metadata["total_tokens"] == 30


@pytest.mark.asyncio
async def test_chat_no_api_key():
    """未配置 API key 返回错误"""
    p = GLMProvider(api_key="", api_base="https://test")
    result = await p.chat(messages=[{"role": "user", "content": "hi"}])
    assert result.success is False
    assert "API key" in result.error or "api_key" in result.error.lower()


@pytest.mark.asyncio
async def test_chat_http_error(provider):
    """HTTP 错误"""
    error_resp = MagicMock()
    error_resp.status_code = 429
    error_resp.text = "Rate limit"
    error_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "429 Too Many Requests", request=MagicMock(), response=error_resp
    )
    provider._client.post.return_value = error_resp

    result = await provider.chat(messages=[{"role": "user", "content": "hi"}])
    assert result.success is False
    assert "429" in result.error


@pytest.mark.asyncio
async def test_chat_streaming(provider):
    """流式响应"""
    async def fake_aiter_lines():
        lines = [
            'data: {"choices":[{"delta":{"content":"你好"}}]}',
            'data: {"choices":[{"delta":{"content":"GLM"}}]}',
            'data: {"choices":[{"finish_reason":"stop"}]}',
            'data: [DONE]',
        ]
        for line in lines:
            yield line

    fake_stream_ctx = MagicMock()
    fake_stream_ctx.__aenter__ = AsyncMock(return_value=fake_stream_ctx)
    fake_stream_ctx.__aexit__ = AsyncMock(return_value=None)
    fake_stream_ctx.aiter_lines = fake_aiter_lines
    fake_stream_ctx.raise_for_status = MagicMock()

    provider._client.stream = MagicMock(return_value=fake_stream_ctx)

    result = await provider.chat(
        messages=[{"role": "user", "content": "hi"}],
        stream=True,
    )
    assert result.success is True
    assert "你好" in result.data
    assert "GLM" in result.data


@pytest.mark.asyncio
async def test_health_check(provider):
    with patch.object(provider, "chat", new=AsyncMock(return_value=GenerationResult(
        success=True, data="hi", content_type="text/plain", metadata={},
    ))):
        result = await provider.health_check()
    assert result is True
