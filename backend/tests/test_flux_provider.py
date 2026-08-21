"""Tests for FluxProvider (local diffusers)."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.engines.base import GenerationResult


@pytest.fixture
def flux_provider():
    """FluxProvider 实例（diffusers 已 mock）"""
    from app.engines.image.flux import FluxProvider
    p = FluxProvider(model_id="black-forest-labs/FLUX.1-dev")
    p._initialized = True
    return p


def test_import_with_mocked_diffusers():
    """diffusers 未安装时仍可导入模块"""
    import sys
    # 模拟 diffusers 未安装
    original = sys.modules.get("diffusers")
    sys.modules["diffusers"] = MagicMock()  # type: ignore
    try:
        # 重新导入应不报错
        import importlib
        import app.engines.image.flux as flux_mod
        importlib.reload(flux_mod)
    finally:
        if original is not None:
            sys.modules["diffusers"] = original
        else:
            del sys.modules["diffusers"]


@pytest.mark.asyncio
async def test_text2img_success(flux_provider):
    """生成图像成功"""
    fake_pipe = MagicMock()
    fake_output = MagicMock()
    fake_image = MagicMock()
    fake_image.save = MagicMock()
    fake_output.images = [fake_image]
    fake_pipe.__call__ = MagicMock(return_value=fake_output)
    flux_provider._pipe = fake_pipe

    import io
    with patch("app.engines.image.flux.BytesIO", new=io.BytesIO):
        result = await flux_provider.text2img(prompt="a cat", width=1024, height=1024)

    assert result.success is True
    assert isinstance(result.data, bytes)
    assert result.content_type == "image/png"
    assert result.metadata["provider"] == "flux"
    assert result.metadata["model"] == "black-forest-labs/FLUX.1-dev"


@pytest.mark.asyncio
async def test_text2img_not_initialized():
    """未初始化（模型未加载）返回错误"""
    from app.engines.image.flux import FluxProvider
    p = FluxProvider(model_id="test-model")
    # _pipe 为 None
    result = await p.text2img(prompt="test")
    assert result.success is False
    assert "未初始化" in result.error or "not initialized" in result.error.lower()


@pytest.mark.asyncio
async def test_4bit_quantization_called(flux_provider):
    """4-bit 量化应在 initialize 中调用"""
    with patch("app.engines.image.flux._DIFFUSERS_AVAILABLE", True):
        with patch("app.engines.image.flux.BitsAndBytesConfig") as bnb_mock:
            with patch("app.engines.image.flux.FluxPipeline") as pipe_mock:
                pipe_mock.from_pretrained = MagicMock(return_value=MagicMock())
                flux_provider._initialized = False
                flux_provider._pipe = None
                await flux_provider.initialize()
                # 验证 from_pretrained 被调用且含 quantization_config
                pipe_mock.from_pretrained.assert_called_once()
                call_kwargs = pipe_mock.from_pretrained.call_args[1]
                assert "quantization_config" in call_kwargs


@pytest.mark.asyncio
async def test_health_check(flux_provider):
    """健康检查"""
    with patch.object(flux_provider, "text2img", new=AsyncMock(return_value=GenerationResult(
        success=True, data=b"fake-png", content_type="image/png", metadata={},
    ))):
        result = await flux_provider.health_check()
    assert result is True
