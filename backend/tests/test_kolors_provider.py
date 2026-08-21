"""Tests for KolorsProvider (Kuaishou API)."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from app.engines.base import GenerationResult
from app.engines.image.kolors import KolorsProvider


@pytest.fixture
def provider():
    p = KolorsProvider(
        api_key="test-kolors-key",
        api_secret="test-kolors-secret",
        api_base="https://api.kuaishou.com/kolors",
    )
    p._client = AsyncMock(spec=httpx.AsyncClient)
    p._initialized = True
    return p


@pytest.mark.asyncio
async def test_text2img_success(provider):
    submit_resp = MagicMock()
    submit_resp.status_code = 200
    submit_resp.json.return_value = {"data": {"task_id": "kolors-1"}}
    provider._client.post.return_value = submit_resp

    pending_resp = MagicMock()
    pending_resp.status_code = 200
    pending_resp.json.return_value = {"data": {"task_status": "processing"}}

    done_resp = MagicMock()
    done_resp.status_code = 200
    done_resp.json.return_value = {
        "data": {
            "task_status": "succeed",
            "task_result": {"images": [{"url": "https://cdn.example.com/kolors.png"}]},
        }
    }

    with patch("asyncio.sleep", new=AsyncMock()):
        with patch("app.engines.image.kolors.download_image", new=AsyncMock(return_value=b"fake-png-bytes")):
            provider._client.get = AsyncMock(side_effect=[pending_resp, done_resp])
            result = await provider.text2img(prompt="一只狗", width=1024, height=1024)

    assert result.success is True
    assert isinstance(result.data, bytes)
    assert result.content_type == "image/png"
    assert result.metadata["provider"] == "kolors"


@pytest.mark.asyncio
async def test_text2img_submit_failure(provider):
    error_resp = MagicMock()
    error_resp.status_code = 401
    error_resp.text = "Unauthorized"
    error_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "401", request=MagicMock(), response=error_resp
    )
    provider._client.post.return_value = error_resp

    result = await provider.text2img(prompt="test")
    assert result.success is False
    assert "401" in result.error


@pytest.mark.asyncio
async def test_text2img_timeout(provider):
    submit_resp = MagicMock()
    submit_resp.status_code = 200
    submit_resp.json.return_value = {"data": {"task_id": "kolors-timeout"}}
    provider._client.post.return_value = submit_resp

    pending_resp = MagicMock()
    pending_resp.status_code = 200
    pending_resp.json.return_value = {"data": {"task_status": "processing"}}
    provider._client.get = AsyncMock(return_value=pending_resp)

    with patch("asyncio.sleep", new=AsyncMock()):
        result = await provider.text2img(prompt="test", max_poll_seconds=1)
    assert result.success is False
    assert "超时" in result.error or "timeout" in result.error.lower()


@pytest.mark.asyncio
async def test_text2img_task_failed(provider):
    submit_resp = MagicMock()
    submit_resp.status_code = 200
    submit_resp.json.return_value = {"data": {"task_id": "kolors-fail"}}
    provider._client.post.return_value = submit_resp

    fail_resp = MagicMock()
    fail_resp.status_code = 200
    fail_resp.json.return_value = {"data": {"task_status": "failed", "task_status_msg": "内容违规"}}
    provider._client.get = AsyncMock(return_value=fail_resp)

    with patch("asyncio.sleep", new=AsyncMock()):
        result = await provider.text2img(prompt="banned")
    assert result.success is False
    assert "内容违规" in result.error


@pytest.mark.asyncio
async def test_health_check(provider):
    with patch.object(provider, "text2img", new=AsyncMock(return_value=GenerationResult(
        success=True, data=b"fake-png", content_type="image/png", metadata={},
    ))):
        result = await provider.health_check()
    assert result is True
