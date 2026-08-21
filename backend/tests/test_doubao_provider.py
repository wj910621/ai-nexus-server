"""Tests for DoubaoProvider (Volcano Ark API)."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from app.engines.base import GenerationResult
from app.engines.llm.doubao import DoubaoProvider


@pytest.fixture
def provider():
    p = DoubaoProvider(
        api_key="test-doubao-key",
        api_base="https://ark.cn-beijing.volces.com/api/v3",
    )
    p._client = AsyncMock(spec=httpx.AsyncClient)
    p._initialized = True
    return p


@pytest.mark.asyncio
async def test_chat_success(provider):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "choices": [{
            "message": {"content": "你好，我是豆包"},
            "finish_reason": "stop",
        }],
        "usage": {"prompt_tokens": 5, "completion_tokens": 10, "total_tokens": 15},
    }
    provider._client.post.return_value = resp

    result = await provider.chat(
        messages=[{"role": "user", "content": "你是谁"}],
        model="doubao-pro-32k",
    )
    assert result.success is True
    assert result.data == "你好，我是豆包"
    assert result.metadata["provider"] == "doubao"
    assert result.metadata["total_tokens"] == 15


@pytest.mark.asyncio
async def test_chat_no_api_key():
    p = DoubaoProvider(api_key="", api_base="https://test")
    result = await p.chat(messages=[{"role": "user", "content": "hi"}])
    assert result.success is False
    assert "API key" in result.error or "api_key" in result.error.lower()


@pytest.mark.asyncio
async def test_chat_http_error(provider):
    error_resp = MagicMock()
    error_resp.status_code = 401
    error_resp.text = "Unauthorized"
    error_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "401", request=MagicMock(), response=error_resp
    )
    provider._client.post.return_value = error_resp

    result = await provider.chat(messages=[{"role": "user", "content": "hi"}])
    assert result.success is False
    assert "401" in result.error


@pytest.mark.asyncio
async def test_chat_streaming(provider):
    async def fake_aiter_lines():
        yield 'data: {"choices":[{"delta":{"content":"豆"}}]}'
        yield 'data: {"choices":[{"delta":{"content":"包"}}]}'
        yield 'data: [DONE]'

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
    assert result.data == "豆包"


@pytest.mark.asyncio
async def test_health_check(provider):
    with patch.object(provider, "chat", new=AsyncMock(return_value=GenerationResult(
        success=True, data="hi", content_type="text/plain", metadata={},
    ))):
        result = await provider.health_check()
    assert result is True
