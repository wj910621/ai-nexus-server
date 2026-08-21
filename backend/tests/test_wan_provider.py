"""Tests for WanProvider (local diffusers)."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.engines.base import GenerationResult


@pytest.fixture
def wan_provider():
    from app.engines.video.wan import WanProvider
    p = WanProvider(model_id="Wan-AI/Wan2.1-T2V-1.3B")
    p._initialized = True
    return p


def test_import_with_mocked_diffusers():
    import sys
    original = sys.modules.get("diffusers")
    sys.modules["diffusers"] = MagicMock()  # type: ignore
    try:
        import importlib
        import app.engines.video.wan as wan_mod
        importlib.reload(wan_mod)
    finally:
        if original is not None:
            sys.modules["diffusers"] = original
        else:
            del sys.modules["diffusers"]


@pytest.mark.asyncio
async def test_text2video_success(wan_provider):
    fake_pipe = MagicMock()
    fake_output = MagicMock()
    fake_video = MagicMock()
    fake_video.save = MagicMock(side_effect=lambda path, **kw: None)
    fake_output.frames = [[fake_video]]
    fake_pipe.__call__ = MagicMock(return_value=fake_output)
    wan_provider._pipe = fake_pipe

    import os
    with patch("os.makedirs"):
        with patch("builtins.open", new=MagicMock()):
            with patch("os.path.getsize", return_value=1024):
                result = await wan_provider.text2video(
                    prompt="a cat running", duration=2, output_path="/tmp/test.mp4",
                )

    assert result.success is True
    assert result.content_type == "video/mp4"
    assert result.metadata["provider"] == "wan"


@pytest.mark.asyncio
async def test_text2video_not_initialized():
    from app.engines.video.wan import WanProvider
    p = WanProvider(model_id="test")
    result = await p.text2video(prompt="test")
    assert result.success is False
    assert "未初始化" in result.error or "not initialized" in result.error.lower()


@pytest.mark.asyncio
async def test_lazy_loading():
    """懒加载 - 初始化时才加载模型"""
    from app.engines.video.wan import WanProvider
    p = WanProvider(model_id="test-model")
    assert p._pipe is None
    assert p._initialized is False


@pytest.mark.asyncio
async def test_health_check(wan_provider):
    with patch.object(wan_provider, "text2video", new=AsyncMock(return_value=GenerationResult(
        success=True, data=b"fake-mp4", content_type="video/mp4", metadata={},
    ))):
        result = await wan_provider.health_check()
    assert result is True
