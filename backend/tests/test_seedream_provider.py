"""Tests for SeedreamProvider (Volcano API)."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from app.engines.image.seedream import SeedreamProvider
from app.engines.base import GenerationResult


@pytest.fixture
def provider():
    """SeedreamProvider 实例（使用 mock httpx）"""
    p = SeedreamProvider(
        api_key="test-volcano-key",
        api_secret="test-volcano-secret",
        api_base="https://visual.volcengineapi.com",
    )
    p._client = AsyncMock(spec=httpx.AsyncClient)
    p._initialized = True
    return p


@pytest.mark.asyncio
async def test_text2img_success(provider):
    """文生图成功返回 PNG bytes"""
    # Volcano API 返回 task_id，需轮询
    submit_response = MagicMock()
    submit_response.status_code = 200
    submit_response.json.return_value = {"data": {"task_id": "task-123"}}
    provider._client.post.return_value = submit_response

    # 轮询：第一次 pending，第二次完成
    query_response_pending = MagicMock()
    query_response_pending.status_code = 200
    query_response_pending.json.return_value = {"data": {"status": "running"}}

    query_response_done = MagicMock()
    query_response_done.status_code = 200
    query_response_done.json.return_value = {
        "data": {
            "status": "done",
            "image_urls": ["https://cdn.example.com/result.png"],
        }
    }

    # mock 轮询 + 下载图片
    with patch("asyncio.sleep", new=AsyncMock()):
        with patch("app.engines.image.seedream.download_image", new=AsyncMock(return_value=b"\x89PNG\r\n\x1a\n-fake-png-bytes")):
            provider._client.get = AsyncMock(
                side_effect=[query_response_pending, query_response_done]
            )
            result = await provider.text2img(prompt="一只猫", width=1024, height=1024)

    assert result.success is True
    assert isinstance(result.data, bytes)
    assert result.content_type == "image/png"
    assert result.metadata["provider"] == "seedream"
    assert result.metadata["task_id"] == "task-123"


@pytest.mark.asyncio
async def test_text2img_submit_failure(provider):
    """提交任务失败返回错误"""
    error_resp = MagicMock()
    error_resp.status_code = 400
    error_resp.text = "Invalid API key"
    error_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "400 Bad Request", request=MagicMock(), response=error_resp
    )
    provider._client.post.return_value = error_resp

    result = await provider.text2img(prompt="test")
    assert result.success is False
    assert "400" in result.error


@pytest.mark.asyncio
async def test_text2img_task_timeout(provider):
    """任务轮询超时返回错误"""
    submit_response = MagicMock()
    submit_response.status_code = 200
    submit_response.json.return_value = {"data": {"task_id": "task-timeout"}}
    provider._client.post.return_value = submit_response

    # 一直返回 running
    pending_resp = MagicMock()
    pending_resp.status_code = 200
    pending_resp.json.return_value = {"data": {"status": "running"}}
    provider._client.get = AsyncMock(return_value=pending_resp)

    with patch("asyncio.sleep", new=AsyncMock()):
        result = await provider.text2img(prompt="test", max_poll_seconds=2)

    assert result.success is False
    assert "超时" in result.error or "timeout" in result.error.lower()


@pytest.mark.asyncio
async def test_text2img_task_failed(provider):
    """任务状态为 failed 返回错误"""
    submit_response = MagicMock()
    submit_response.status_code = 200
    submit_response.json.return_value = {"data": {"task_id": "task-failed"}}
    provider._client.post.return_value = submit_response

    failed_resp = MagicMock()
    failed_resp.status_code = 200
    failed_resp.json.return_value = {
        "data": {"status": "failed", "error_msg": "Content moderation rejected"}
    }
    provider._client.get = AsyncMock(return_value=failed_resp)

    with patch("asyncio.sleep", new=AsyncMock()):
        result = await provider.text2img(prompt="banned content")

    assert result.success is False
    assert "Content moderation" in result.error


@pytest.mark.asyncio
async def test_health_check(provider):
    """健康检查（mock 最小请求）"""
    with patch.object(provider, "text2img", new=AsyncMock(return_value=GenerationResult(
        success=True, data=b"fake", content_type="image/png", metadata={},
    ))):
        result = await provider.health_check()
    assert result is True
