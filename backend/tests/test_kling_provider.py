"""Tests for KlingProvider (Kuaishou API)."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from app.engines.video.kling import KlingProvider
from app.engines.base import GenerationResult


@pytest.fixture
def provider():
    p = KlingProvider(
        api_key="test-kling-key",
        api_secret="test-kling-secret",
        api_base="https://api.kuaishou.com/kling",
    )
    p._client = AsyncMock(spec=httpx.AsyncClient)
    p._initialized = True
    return p


@pytest.mark.asyncio
async def test_text2video_success(provider):
    submit_resp = MagicMock()
    submit_resp.status_code = 200
    submit_resp.json.return_value = {"data": {"task_id": "k-task-1", "task_status": "submitted"}}
    provider._client.post.return_value = submit_resp

    pending_resp = MagicMock()
    pending_resp.status_code = 200
    pending_resp.json.return_value = {"data": {"task_id": "k-task-1", "task_status": "processing"}}

    done_resp = MagicMock()
    done_resp.status_code = 200
    done_resp.json.return_value = {
        "data": {
            "task_id": "k-task-1",
            "task_status": "succeed",
            "task_result": {"videos": [{"url": "https://cdn.example.com/kling.mp4"}]},
        }
    }

    with patch("asyncio.sleep", new=AsyncMock()):
        with patch("app.engines.video.kling.download_video", new=AsyncMock(return_value=b"fake-mp4-bytes")):
            provider._client.get = AsyncMock(side_effect=[pending_resp, done_resp])
            result = await provider.text2video(prompt="a dog running", duration=5)

    assert result.success is True
    assert result.content_type == "video/mp4"
    assert result.metadata["provider"] == "kling"
    assert result.metadata["task_id"] == "k-task-1"


@pytest.mark.asyncio
async def test_text2video_submit_failure(provider):
    error_resp = MagicMock()
    error_resp.status_code = 403
    error_resp.text = "Forbidden"
    error_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "403 Forbidden", request=MagicMock(), response=error_resp
    )
    provider._client.post.return_value = error_resp

    result = await provider.text2video(prompt="test")
    assert result.success is False
    assert "403" in result.error


@pytest.mark.asyncio
async def test_text2video_timeout(provider):
    submit_resp = MagicMock()
    submit_resp.status_code = 200
    submit_resp.json.return_value = {"data": {"task_id": "k-timeout", "task_status": "submitted"}}
    provider._client.post.return_value = submit_resp

    pending_resp = MagicMock()
    pending_resp.status_code = 200
    pending_resp.json.return_value = {"data": {"task_status": "processing"}}
    provider._client.get = AsyncMock(return_value=pending_resp)

    with patch("asyncio.sleep", new=AsyncMock()):
        result = await provider.text2video(prompt="test", max_poll_seconds=1)

    assert result.success is False
    assert "超时" in result.error or "timeout" in result.error.lower()


@pytest.mark.asyncio
async def test_text2video_task_failed(provider):
    submit_resp = MagicMock()
    submit_resp.status_code = 200
    submit_resp.json.return_value = {"data": {"task_id": "k-fail", "task_status": "submitted"}}
    provider._client.post.return_value = submit_resp

    fail_resp = MagicMock()
    fail_resp.status_code = 200
    fail_resp.json.return_value = {"data": {"task_status": "failed", "task_status_msg": "内容违规"}}
    provider._client.get = AsyncMock(return_value=fail_resp)

    with patch("asyncio.sleep", new=AsyncMock()):
        result = await provider.text2video(prompt="banned")

    assert result.success is False
    assert "内容违规" in result.error


@pytest.mark.asyncio
async def test_health_check(provider):
    with patch.object(provider, "text2video", new=AsyncMock(return_value=GenerationResult(
        success=True, data=b"fake-mp4", content_type="video/mp4", metadata={},
    ))):
        result = await provider.health_check()
    assert result is True
