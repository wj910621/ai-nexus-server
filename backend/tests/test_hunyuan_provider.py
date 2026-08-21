"""Tests for HunyuanProvider (local diffusers)."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.engines.base import GenerationResult


@pytest.fixture
def hunyuan_provider():
    from app.engines.video.hunyuan import HunyuanProvider
    p = HunyuanProvider(model_id="tencent/HunyuanVideo")
    p._initialized = True
    return p


def test_import_with_mocked_diffusers():
    import sys
    original = sys.modules.get("diffusers")
    sys.modules["diffusers"] = MagicMock()  # type: ignore
    try:
        import importlib
        import app.engines.video.hunyuan as hy_mod
        importlib.reload(hy_mod)
    finally:
        if original is not None:
            sys.modules["diffusers"] = original
        else:
            del sys.modules["diffusers"]


@pytest.mark.asyncio
async def test_text2video_success(hunyuan_provider):
    fake_pipe = MagicMock()
    fake_output = MagicMock()
    fake_video = MagicMock()
    fake_output.frames = [[fake_video]]
    fake_pipe.__call__ = MagicMock(return_value=fake_output)
    hunyuan_provider._pipe = fake_pipe

    with patch("os.makedirs"):
        with patch("builtins.open", new=MagicMock()):
            with patch("os.path.getsize", return_value=2048):
                result = await hunyuan_provider.text2video(
                    prompt="a dog", duration=2, output_path="/tmp/test.mp4",
                )
    assert result.success is True
    assert result.metadata["provider"] == "hunyuan"


@pytest.mark.asyncio
async def test_text2video_not_initialized():
    from app.engines.video.hunyuan import HunyuanProvider
    p = HunyuanProvider(model_id="test")
    result = await p.text2video(prompt="test")
    assert result.success is False


@pytest.mark.asyncio
async def test_lazy_loading():
    from app.engines.video.hunyuan import HunyuanProvider
    p = HunyuanProvider(model_id="test-model")
    assert p._pipe is None
    assert p._initialized is False


@pytest.mark.asyncio
async def test_health_check(hunyuan_provider):
    with patch.object(hunyuan_provider, "text2video", new=AsyncMock(return_value=GenerationResult(
        success=True, data=b"fake-mp4", content_type="video/mp4", metadata={},
    ))):
        result = await hunyuan_provider.health_check()
    assert result is True
