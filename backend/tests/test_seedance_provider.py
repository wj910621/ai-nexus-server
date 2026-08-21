"""Tests for SeedanceProvider (Volcano API)."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from app.engines.video.seedance import SeedanceProvider
from app.engines.base import GenerationResult


@pytest.fixture
def provider():
    p = SeedanceProvider(
        api_key="test-volcano-key",
        api_secret="test-volcano-secret",
        api_base="https://visual.volcengineapi.com",
    )
    p._client = AsyncMock(spec=httpx.AsyncClient)
    p._initialized = True
    return p


@pytest.mark.asyncio
async def test_text2video_success(provider):
    """文生视频成功返回 mp4 bytes"""
    submit_resp = MagicMock()
    submit_resp.status_code = 200
    submit_resp.json.return_value = {"data": {"task_id": "v-task-1"}}
    provider._client.post.return_value = submit_resp

    pending_resp = MagicMock()
    pending_resp.status_code = 200
    pending_resp.json.return_value = {"data": {"status": "running", "progress": 30}}

    done_resp = MagicMock()
    done_resp.status_code = 200
    done_resp.json.return_value = {
        "data": {"status": "done", "video_url": "https://cdn.example.com/result.mp4"}
    }

    with patch("asyncio.sleep", new=AsyncMock()):
        with patch("app.engines.video.seedance.download_video", new=AsyncMock(return_value=b"\x00\x00\x00\x20ftypmp42-fake-mp4")):
            provider._client.get = AsyncMock(side_effect=[pending_resp, done_resp])
            result = await provider.text2video(prompt="一只猫在跑", duration=5)

    assert result.success is True
    assert isinstance(result.data, bytes)
    assert result.content_type == "video/mp4"
    assert result.metadata["provider"] == "seedance"
    assert result.metadata["task_id"] == "v-task-1"


@pytest.mark.asyncio
async def test_text2video_submit_failure(provider):
    """提交任务失败"""
    error_resp = MagicMock()
    error_resp.status_code = 401
    error_resp.text = "Unauthorized"
    error_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "401 Unauthorized", request=MagicMock(), response=error_resp
    )
    provider._client.post.return_value = error_resp

    result = await provider.text2video(prompt="test")
    assert result.success is False
    assert "401" in result.error


@pytest.mark.asyncio
async def test_text2video_timeout(provider):
    """轮询超时"""
    submit_resp = MagicMock()
    submit_resp.status_code = 200
    submit_resp.json.return_value = {"data": {"task_id": "v-timeout"}}
    provider._client.post.return_value = submit_resp

    pending_resp = MagicMock()
    pending_resp.status_code = 200
    pending_resp.json.return_value = {"data": {"status": "running", "progress": 50}}
    provider._client.get = AsyncMock(return_value=pending_resp)

    with patch("asyncio.sleep", new=AsyncMock()):
        result = await provider.text2video(prompt="test", max_poll_seconds=1)

    assert result.success is False
    assert "超时" in result.error or "timeout" in result.error.lower()


@pytest.mark.asyncio
async def test_text2video_task_failed(provider):
    """任务失败"""
    submit_resp = MagicMock()
    submit_resp.status_code = 200
    submit_resp.json.return_value = {"data": {"task_id": "v-fail"}}
    provider._client.post.return_value = submit_resp

    fail_resp = MagicMock()
    fail_resp.status_code = 200
    fail_resp.json.return_value = {"data": {"status": "failed", "error_msg": "视频生成失败"}}
    provider._client.get = AsyncMock(return_value=fail_resp)

    with patch("asyncio.sleep", new=AsyncMock()):
        result = await provider.text2video(prompt="test")

    assert result.success is False
    assert "视频生成失败" in result.error


@pytest.mark.asyncio
async def test_health_check(provider):
    with patch.object(provider, "text2video", new=AsyncMock(return_value=GenerationResult(
        success=True, data=b"fake-mp4", content_type="video/mp4", metadata={},
    ))):
        result = await provider.health_check()
    assert result is True
