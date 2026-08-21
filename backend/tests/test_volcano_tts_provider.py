"""Tests for VolcanoTTSProvider (Volcano API)."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from app.engines.base import GenerationResult
from app.engines.tts.volcano_tts import VolcanoTTSProvider


@pytest.fixture
def provider():
    p = VolcanoTTSProvider(
        api_key="test-volcano-key",
        api_secret="test-volcano-secret",
        api_base="https://openspeech.bytedance.com/api/v1",
    )
    p._client = AsyncMock(spec=httpx.AsyncClient)
    p._initialized = True
    return p


@pytest.mark.asyncio
async def test_synthesize_success(provider):
    """合成成功返回 mp3 bytes"""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "code": 3000,
        "data": {"audio": "fake-base64-audio-data"},
    }
    provider._client.post.return_value = resp

    with patch("base64.b64decode", return_value=b"fake-mp3-bytes"):
        result = await provider.synthesize(
            text="你好世界",
            voice="zh_female_qingxin",
        )

    assert result.success is True
    assert isinstance(result.data, bytes)
    assert result.content_type == "audio/mp3"
    assert result.metadata["provider"] == "volcano_tts"


@pytest.mark.asyncio
async def test_synthesize_no_api_key():
    p = VolcanoTTSProvider(api_key="", api_secret="", api_base="https://test")
    result = await p.synthesize(text="hi")
    assert result.success is False
    assert "API key" in result.error or "api_key" in result.error.lower()


@pytest.mark.asyncio
async def test_synthesize_http_error(provider):
    error_resp = MagicMock()
    error_resp.status_code = 401
    error_resp.text = "Unauthorized"
    error_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "401", request=MagicMock(), response=error_resp
    )
    provider._client.post.return_value = error_resp

    result = await provider.synthesize(text="hi")
    assert result.success is False
    assert "401" in result.error


@pytest.mark.asyncio
async def test_synthesize_api_error_code(provider):
    """API 返回错误 code"""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"code": 3001, "message": "Invalid voice"}
    provider._client.post.return_value = resp

    result = await provider.synthesize(text="hi", voice="invalid")
    assert result.success is False
    assert "Invalid voice" in result.error


@pytest.mark.asyncio
async def test_health_check(provider):
    with patch.object(provider, "synthesize", new=AsyncMock(return_value=GenerationResult(
        success=True, data=b"fake-mp3", content_type="audio/mp3", metadata={},
    ))):
        result = await provider.health_check()
    assert result is True
