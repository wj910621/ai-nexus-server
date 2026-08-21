"""测试 DeepSeek LLM Provider（使用 mock，不依赖真实网络）"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.engines.llm.deepseek import DeepSeekProvider
from app.engines.base import GenerationResult


@pytest.fixture
def provider():
    """Provider 实例（使用测试 api_key）"""
    return DeepSeekProvider(api_key="test-api-key")


def test_provider_init(provider):
    """测试初始化"""
    assert provider.name == "deepseek"
    assert provider.display_name == "DeepSeek (OpenAI 兼容)"
    assert provider._initialized is False
    assert provider.client is None
    assert "deepseek-chat" in provider.AVAILABLE_MODELS
    assert "deepseek-reasoner" in provider.AVAILABLE_MODELS
    assert provider.DEFAULT_MODEL == "deepseek-chat"


@pytest.mark.asyncio
async def test_provider_initialize():
    """测试初始化方法 - mock settings 提供 api_key"""
    with patch("app.engines.llm.deepseek.settings") as mock_settings:
        mock_settings.deepseek_api_key = "test-key-from-settings"
        mock_settings.deepseek_api_base = "https://api.deepseek.com"
        provider = DeepSeekProvider()
        assert provider.api_key == "test-key-from-settings"
        await provider.initialize()
        assert provider._initialized is True
        assert provider.client is not None
        await provider.client.aclose()


@pytest.mark.asyncio
async def test_chat_success(provider):
    """测试对话成功（mock 网络）"""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "Hello!"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
    }
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    provider.client = mock_client
    provider._initialized = True

    result = await provider.chat(
        messages=[{"role": "user", "content": "Hi"}],
        model="deepseek-chat",
    )

    assert result.success is True
    assert result.data == "Hello!"
    assert result.content_type == "text/plain"
    assert result.metadata["provider"] == "deepseek"
    assert result.metadata["model"] == "deepseek-chat"
    assert result.metadata["model_used"] == "deepseek-chat"
    assert result.metadata["prompt_tokens"] == 5
    assert result.metadata["completion_tokens"] == 3
    assert result.metadata["total_tokens"] == 8
    assert result.metadata["finish_reason"] == "stop"
    assert result.error is None

    # 验证 post 调用参数
    mock_client.post.assert_called_once()
    call_args = mock_client.post.call_args
    url = call_args[0][0] if call_args[0] else call_args.kwargs.get("url", "")
    assert "/v1/chat/completions" in url
    headers = call_args.kwargs.get("headers", {})
    assert headers["Authorization"] == "Bearer test-api-key"
    json_payload = call_args.kwargs.get("json", {})
    assert json_payload["model"] == "deepseek-chat"
    assert json_payload["messages"] == [{"role": "user", "content": "Hi"}]
    assert json_payload["stream"] is False


@pytest.mark.asyncio
async def test_chat_with_custom_model(provider):
    """测试使用 deepseek-reasoner 模型"""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [
            {"message": {"content": "Reasoning result"}, "finish_reason": "stop"}
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
    }
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    provider.client = mock_client
    provider._initialized = True

    result = await provider.chat(
        messages=[{"role": "user", "content": "explain quantum mechanics"}],
        model="deepseek-reasoner",
    )

    assert result.success is True
    assert result.data == "Reasoning result"
    assert result.metadata["model"] == "deepseek-reasoner"
    assert result.metadata["model_used"] == "deepseek-reasoner"

    # 验证 post 调用使用了正确的 model
    call_kwargs = mock_client.post.call_args.kwargs
    assert call_kwargs["json"]["model"] == "deepseek-reasoner"


@pytest.mark.asyncio
async def test_chat_http_error(provider):
    """测试 HTTP 错误"""
    import httpx

    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.text = "Unauthorized"
    mock_response.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError(
            "401", request=MagicMock(), response=mock_response
        )
    )

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    provider.client = mock_client
    provider._initialized = True

    result = await provider.chat(messages=[{"role": "user", "content": "hi"}])

    assert result.success is False
    assert "401" in result.error
    assert "Unauthorized" in result.error


@pytest.mark.asyncio
async def test_chat_no_api_key():
    """测试 api_key 为空时返回 success=False"""
    provider = DeepSeekProvider(api_key="")
    result = await provider.chat(messages=[{"role": "user", "content": "hi"}])

    assert result.success is False
    assert result.error == "DeepSeek API key 未配置"
    assert result.data == ""


@pytest.mark.asyncio
async def test_health_check(provider):
    """测试健康检查"""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "hi"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    provider.client = mock_client
    provider._initialized = True

    healthy = await provider.health_check()
    assert healthy is True


def test_get_info(provider):
    """测试获取引擎信息"""
    info = provider.get_info()
    assert info["name"] == "deepseek"
    assert info["display_name"] == "DeepSeek (OpenAI 兼容)"
    assert "available_models" in info
    assert "deepseek-chat" in info["available_models"]
    assert "deepseek-reasoner" in info["available_models"]
    assert info["default_model"] == "deepseek-chat"
    assert info["api_base"] == "https://api.deepseek.com"
    assert info["api_key_configured"] is True


# ===== Task 21: SemanticCache 集成测试 =====


@pytest.fixture
def deepseek_with_cache():
    """DeepSeek + mock SemanticCache"""
    p = DeepSeekProvider(api_key="test-key", api_base="https://api.test.com")
    p.client = AsyncMock()
    p._initialized = True

    mock_cache = MagicMock()
    mock_cache.lookup = AsyncMock(return_value=None)  # 默认未命中
    mock_cache.store = AsyncMock()
    p._cache = mock_cache
    return p


@pytest.mark.asyncio
async def test_chat_cache_hit_skips_api(deepseek_with_cache):
    """缓存命中时跳过 API 调用"""
    cached_result = GenerationResult(
        success=True,
        data="cached answer",
        content_type="text/plain",
        metadata={"provider": "deepseek", "cached": True},
    )
    deepseek_with_cache._cache.lookup = AsyncMock(return_value=cached_result)

    result = await deepseek_with_cache.chat(
        messages=[{"role": "user", "content": "hello"}],
        max_tokens=500,
    )

    assert result.success is True
    assert result.data == "cached answer"
    assert result.metadata.get("cached") is True
    # API 不应被调用
    deepseek_with_cache.client.post.assert_not_called()


@pytest.mark.asyncio
async def test_chat_cache_miss_stores_response(deepseek_with_cache):
    """缓存未命中 → 调 API → 存储"""
    api_resp = MagicMock()
    api_resp.status_code = 200
    api_resp.json.return_value = {
        "choices": [{"message": {"content": "fresh answer"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 5, "completion_tokens": 10, "total_tokens": 15},
    }
    api_resp.raise_for_status = MagicMock()
    deepseek_with_cache.client.post.return_value = api_resp

    result = await deepseek_with_cache.chat(
        messages=[{"role": "user", "content": "hello"}],
        max_tokens=500,
    )

    assert result.success is True
    assert result.data == "fresh answer"
    # 验证 lookup 被调用
    deepseek_with_cache._cache.lookup.assert_called_once()
    # 验证 store 被调用
    deepseek_with_cache._cache.store.assert_called_once()
    store_args = deepseek_with_cache._cache.store.call_args
    assert store_args[1]["response"] == "fresh answer"


@pytest.mark.asyncio
async def test_chat_streaming_skips_cache(deepseek_with_cache):
    """streaming=True 时跳过缓存（不查询，不存储）"""
    # mock 流式响应
    async def fake_aiter_lines():
        yield 'data: {"choices":[{"delta":{"content":"hi"}}]}'
        yield 'data: [DONE]'

    fake_stream_ctx = MagicMock()
    fake_stream_ctx.__aenter__ = AsyncMock(return_value=fake_stream_ctx)
    fake_stream_ctx.__aexit__ = AsyncMock(return_value=None)
    fake_stream_ctx.aiter_lines = fake_aiter_lines
    fake_stream_ctx.raise_for_status = MagicMock()
    deepseek_with_cache.client.stream = MagicMock(return_value=fake_stream_ctx)

    result = await deepseek_with_cache.chat(
        messages=[{"role": "user", "content": "hi"}],
        stream=True,
        max_tokens=500,
    )

    assert result.success is True
    # streaming 模式不应查询或存储缓存
    deepseek_with_cache._cache.lookup.assert_not_called()
    deepseek_with_cache._cache.store.assert_not_called()


@pytest.mark.asyncio
async def test_chat_low_max_tokens_skips_cache(deepseek_with_cache):
    """max_tokens < 100 时跳过缓存"""
    api_resp = MagicMock()
    api_resp.status_code = 200
    api_resp.json.return_value = {
        "choices": [{"message": {"content": "short"}, "finish_reason": "stop"}],
        "usage": {"total_tokens": 5},
    }
    api_resp.raise_for_status = MagicMock()
    deepseek_with_cache.client.post.return_value = api_resp

    result = await deepseek_with_cache.chat(
        messages=[{"role": "user", "content": "hi"}],
        max_tokens=50,  # < 100，跳过缓存
    )

    assert result.success is True
    deepseek_with_cache._cache.lookup.assert_not_called()
    deepseek_with_cache._cache.store.assert_not_called()
