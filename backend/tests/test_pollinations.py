"""测试 Pollinations Provider（使用 mock，不依赖真实网络）"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.engines.image.pollinations import PollinationsProvider
from app.engines.base import GenerationResult


@pytest.fixture
def provider():
    """Provider 实例"""
    return PollinationsProvider()


def test_provider_init(provider):
    """测试初始化"""
    assert provider.name == "pollinations"
    assert provider.display_name == "Pollinations.ai (免费)"
    assert provider._initialized is False
    assert provider.client is None


def test_provider_available_models(provider):
    """测试可用模型列表"""
    assert "flux" in provider.AVAILABLE_MODELS
    assert "turbo" in provider.AVAILABLE_MODELS


@pytest.mark.asyncio
async def test_provider_initialize(provider):
    """测试初始化"""
    await provider.initialize()
    assert provider._initialized is True
    assert provider.client is not None
    await provider.client.aclose()


@pytest.mark.asyncio
async def test_text2img_success(provider):
    """测试文生图成功（mock 网络）"""
    fake_image = b"fake-png-bytes"

    # mock httpx 客户端
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = fake_image
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    provider.client = mock_client
    provider._initialized = True

    result = await provider.text2img(
        prompt="a cute cat",
        width=512,
        height=512,
        model="flux",
    )

    assert result.success is True
    assert result.content_type == "image/png"
    assert result.metadata["provider"] == "pollinations"
    assert result.metadata["model"] == "flux"
    assert "/uploads/images/" in result.data
    assert result.error is None

    # 验证调用了正确的 URL
    mock_client.get.assert_called_once()
    call_args = mock_client.get.call_args
    assert "image.pollinations.ai" in call_args[0][0]
    assert "cute%20cat" in call_args[0][0] or "cute%20cat" in str(call_args)


@pytest.mark.asyncio
async def test_text2img_with_negative_prompt(provider):
    """测试带负面提示词的文生图"""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = b"fake"
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    provider.client = mock_client

    result = await provider.text2img(
        prompt="beautiful landscape",
        negative_prompt="blurry, low quality",
    )

    assert result.success is True
    call_url = mock_client.get.call_args[0][0]
    assert "blurry" in call_url or "low%20quality" in call_url


@pytest.mark.asyncio
async def test_text2img_http_error(provider):
    """测试 HTTP 错误"""
    import httpx

    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"
    mock_response.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError("500", request=MagicMock(), response=mock_response)
    )

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    provider.client = mock_client

    result = await provider.text2img(prompt="test")

    assert result.success is False
    assert "500" in result.error


@pytest.mark.asyncio
async def test_health_check(provider):
    """测试健康检查"""
    mock_response = MagicMock()
    mock_response.status_code = 200

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    provider.client = mock_client

    healthy = await provider.health_check()
    assert healthy is True


def test_get_info(provider):
    """测试获取引擎信息"""
    info = provider.get_info()
    assert info["name"] == "pollinations"
    assert "available_models" in info
    assert info["default_model"] == "flux"
