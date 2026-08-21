"""测试角色一致性 Provider（使用 mock，不依赖真实网络）"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.engines.character.soft_provider import SoftConsistencyProvider
from app.engines.base import GenerationResult


def _make_mock_image_provider():
    """创建 mock 图像 Provider"""
    mock = AsyncMock()
    mock.name = "pollinations"
    mock.text2img = AsyncMock(
        return_value=GenerationResult(
            success=True,
            data="/uploads/images/test.png",
            content_type="image/png",
            metadata={"provider": "pollinations", "model": "flux", "seed": 42},
        )
    )
    mock.health_check = AsyncMock(return_value=True)
    return mock


def _make_mock_llm_provider():
    """创建 mock LLM Provider"""
    mock = AsyncMock()
    mock.name = "deepseek"
    mock.chat = AsyncMock(
        return_value=GenerationResult(
            success=True,
            data="enhanced prompt: a beautiful girl with long hair",
            content_type="text/plain",
            metadata={"total_tokens": 50},
        )
    )
    return mock


@pytest.fixture
def provider():
    """Provider 实例（带 mock providers）"""
    return SoftConsistencyProvider(
        image_provider=_make_mock_image_provider(),
        llm_provider=_make_mock_llm_provider(),
    )


def test_provider_init(provider):
    """测试初始化"""
    assert provider.name == "soft-consistency"
    assert provider.display_name == "软一致性 (LLM提示词增强 + Seed锁定)"
    assert provider._initialized is False
    assert provider.consistency_seed == 42


@pytest.mark.asyncio
async def test_provider_initialize():
    """测试 initialize - mock image_provider 和 llm_provider，验证 _initialized=True"""
    mock_image = _make_mock_image_provider()
    mock_llm = _make_mock_llm_provider()
    provider = SoftConsistencyProvider(
        image_provider=mock_image,
        llm_provider=mock_llm,
    )
    assert provider._initialized is False
    await provider.initialize()
    assert provider._initialized is True


@pytest.mark.asyncio
async def test_extract_features(provider):
    """测试 extract_features - 相同 bytes 返回相同特征向量，长度 64，值在 [0,1]"""
    image_bytes = b"fake-image-bytes"
    features1 = await provider.extract_features(image_bytes)
    features2 = await provider.extract_features(image_bytes)

    assert len(features1) == 64
    assert features1 == features2  # 相同输入应返回相同特征
    for v in features1:
        assert 0.0 <= v <= 1.0


@pytest.mark.asyncio
async def test_enhance_prompt_with_llm(provider):
    """测试 _enhance_prompt 使用 LLM"""
    result = await provider._enhance_prompt(
        prompt="a girl",
        character_description="long hair, blue eyes",
        mood="happy",
    )
    # LLM mock 返回 "enhanced prompt: ..."
    assert "enhanced prompt" in result
    # 验证 LLM 被调用
    provider.llm_provider.chat.assert_called_once()
    call_kwargs = provider.llm_provider.chat.call_args.kwargs
    assert call_kwargs["temperature"] == 0.5
    messages = call_kwargs["messages"]
    assert any(
        "漫画提示词增强助手" in m["content"]
        for m in messages
        if m["role"] == "system"
    )


@pytest.mark.asyncio
async def test_enhance_prompt_fallback():
    """测试无 llm_provider 时使用规则增强，验证结果包含 'masterpiece'"""
    provider = SoftConsistencyProvider(
        image_provider=_make_mock_image_provider(),
        llm_provider=None,
    )
    result = await provider._enhance_prompt(prompt="a girl", mood="happy")
    assert "masterpiece" in result
    assert "a girl" in result
    assert "happy" in result


@pytest.mark.asyncio
async def test_generate_consistent_success(provider):
    """测试 generate_consistent 成功 - mock image_provider.text2img 返回成功"""
    provider._initialized = True
    result = await provider.generate_consistent(
        prompt="a cute cat",
        reference_image=b"fake-image-bytes",
        character_description="fluffy white cat",
        mood="playful",
    )

    assert result.success is True
    assert result.content_type == "image/png"
    assert result.metadata["provider"] == "soft-consistency"
    assert result.metadata["consistency_seed"] == 42
    assert result.metadata["consistency_weight"] == 0.8
    assert result.metadata["character_description_provided"] is True
    assert result.metadata["mood"] == "playful"
    assert "enhanced_prompt" in result.metadata
    assert "elapsed_seconds" in result.metadata
    # 合并 image_provider 的 metadata
    assert result.metadata["model"] == "flux"

    # 验证 text2img 被调用，且 seed 使用了 consistency_seed
    provider.image_provider.text2img.assert_called_once()
    call_kwargs = provider.image_provider.text2img.call_args.kwargs
    assert call_kwargs["seed"] == 42


@pytest.mark.asyncio
async def test_generate_consistent_no_reference(provider):
    """测试空 reference_image 返回 success=False"""
    provider._initialized = True
    result = await provider.generate_consistent(
        prompt="a cat",
        reference_image=b"",
    )
    assert result.success is False
    assert result.error is not None


@pytest.mark.asyncio
async def test_health_check(provider):
    """测试健康检查 - mock image_provider.health_check 返回 True"""
    healthy = await provider.health_check()
    assert healthy is True
    provider.image_provider.health_check.assert_called_once()
