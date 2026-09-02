"""Tests for Task 14: EngineManager LLM 引擎适配过滤 (P2)."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.engines.base import LLMProvider, GenerationResult


class _FakeQwenLocal(LLMProvider):
    name = "qwen_local"
    is_local = True
    supported_models = ["Qwen/Qwen2.5-14B-Instruct"]

    def __init__(self):
        self._initialized = True

    async def initialize(self) -> None:
        self._initialized = True

    async def health_check(self) -> bool:
        return True

    async def chat(self, messages, **kwargs):
        return GenerationResult(success=True, data="qwen", metadata={})

    async def chat_stream(self, messages, **kwargs):
        yield "qwen"


class _FakeLlamaCpp(LLMProvider):
    name = "llama_cpp"
    is_local = True
    supported_models = ["Qwen/Qwen2.5-7B-Instruct-GGUF"]

    def __init__(self):
        self._initialized = True

    async def initialize(self) -> None:
        self._initialized = True

    async def health_check(self) -> bool:
        return True

    async def chat(self, messages, **kwargs):
        return GenerationResult(success=True, data="llamacpp", metadata={})

    async def chat_stream(self, messages, **kwargs):
        yield "llamacpp"


class _FakeDeepSeek(LLMProvider):
    name = "deepseek"
    is_local = False
    supported_models = ["deepseek-chat"]

    def __init__(self):
        self._initialized = True

    async def initialize(self) -> None:
        self._initialized = True

    async def health_check(self) -> bool:
        return True

    async def chat(self, messages, **kwargs):
        return GenerationResult(success=True, data="ds", metadata={})

    async def chat_stream(self, messages, **kwargs):
        yield "ds"


@pytest.fixture
def _reset_dm_singleton():
    """重置 DeviceManager 单例，避免污染其他测试"""
    from app.core.device_manager import DeviceManager
    inst = DeviceManager._instance
    DeviceManager._instance = None
    yield
    DeviceManager._instance = inst


@pytest.mark.asyncio
async def test_llm_route_skips_qwen_local_when_intel(_reset_dm_singleton):
    """Intel 环境（recommend_llm_engine 返回 llama_cpp）下 LLM 路由不应返回 qwen_local"""
    from app.engines.manager import EngineManager
    from app.core.device_manager import DeviceManager, GPUVendor, GPUInfo

    # mock DeviceManager 单例
    fake_dm = MagicMock()
    fake_dm.recommend_llm_engine.return_value = "llama_cpp"
    fake_dm.get_device_string.return_value = "xpu:0"
    DeviceManager._instance = fake_dm

    qwen = _FakeQwenLocal()
    llama = _FakeLlamaCpp()
    deepseek = _FakeDeepSeek()

    mgr = EngineManager()
    # 注入已实例化 Provider 清单（扁平结构，与 _instantiate_all_providers 一致）
    mgr._instantiated_providers = {
        "qwen_local": qwen, "llama_cpp": llama, "deepseek": deepseek,
    }
    # mock 路由组件
    mgr._router = MagicMock()
    mgr._router.select = AsyncMock(side_effect=lambda ctx, providers: _select_for_test(ctx, providers))
    mgr._quota_guard = MagicMock()
    mgr._quota_guard.check = AsyncMock(return_value=True)
    mgr._subscription_guard = MagicMock()

    provider = await mgr.get_engine_routed(
        engine_type="llm",
        user_id=1,
        subscription_tier="pro",
    )
    assert provider is not None
    # 在 Intel 环境下，应该跳过 qwen_local，选择 llama_cpp
    assert provider.name == "llama_cpp"


@pytest.mark.asyncio
async def test_llm_route_uses_qwen_local_when_nvidia(_reset_dm_singleton):
    """NVIDIA 环境（recommend_llm_engine 返回 vllm）下 LLM 路由可返回 qwen_local"""
    from app.engines.manager import EngineManager
    from app.core.device_manager import DeviceManager

    fake_dm = MagicMock()
    fake_dm.recommend_llm_engine.return_value = "vllm"
    DeviceManager._instance = fake_dm

    qwen = _FakeQwenLocal()
    llama = _FakeLlamaCpp()
    deepseek = _FakeDeepSeek()

    mgr = EngineManager()
    mgr._instantiated_providers = {
        "qwen_local": qwen, "llama_cpp": llama, "deepseek": deepseek,
    }
    mgr._router = MagicMock()
    mgr._router.select = AsyncMock(side_effect=lambda ctx, providers: _select_for_test(ctx, providers))
    mgr._quota_guard = MagicMock()
    mgr._quota_guard.check = AsyncMock(return_value=True)
    mgr._subscription_guard = MagicMock()

    provider = await mgr.get_engine_routed(
        engine_type="llm",
        user_id=1,
        subscription_tier="pro",
    )
    assert provider is not None
    # 在 NVIDIA 环境下，应该选择 qwen_local（优先级最高）
    assert provider.name == "qwen_local"


@pytest.mark.asyncio
async def test_llm_route_fallback_to_api_when_no_local_matches(_reset_dm_singleton):
    """Intel 环境下若未实例化 llama_cpp，则降级到 API Provider"""
    from app.engines.manager import EngineManager
    from app.core.device_manager import DeviceManager

    fake_dm = MagicMock()
    fake_dm.recommend_llm_engine.return_value = "llama_cpp"
    DeviceManager._instance = fake_dm

    qwen = _FakeQwenLocal()
    deepseek = _FakeDeepSeek()

    mgr = EngineManager()
    # 未实例化 llama_cpp
    mgr._instantiated_providers = {
        "qwen_local": qwen, "deepseek": deepseek,
    }
    mgr._router = MagicMock()
    mgr._router.select = AsyncMock(side_effect=lambda ctx, providers: _select_for_test(ctx, providers))
    mgr._quota_guard = MagicMock()
    mgr._quota_guard.check = AsyncMock(return_value=True)
    mgr._subscription_guard = MagicMock()

    provider = await mgr.get_engine_routed(
        engine_type="llm",
        user_id=1,
        subscription_tier="pro",
    )
    assert provider is not None
    # Intel 环境下 qwen_local 被跳过，且没有 llama_cpp，降级到 deepseek
    assert provider.name == "deepseek"


@pytest.mark.asyncio
async def test_image_route_not_affected_by_llm_filter(_reset_dm_singleton):
    """LLM 引擎过滤不影响 image 路由"""
    from app.engines.manager import EngineManager
    from app.core.device_manager import DeviceManager

    fake_dm = MagicMock()
    fake_dm.recommend_llm_engine.return_value = "llama_cpp"
    DeviceManager._instance = fake_dm

    flux = MagicMock()
    flux.name = "flux"
    flux.is_local = True

    mgr = EngineManager()
    mgr._instantiated_providers = {"flux": flux}
    mgr._router = MagicMock()
    mgr._router.select = AsyncMock(return_value=flux)
    mgr._quota_guard = MagicMock()
    mgr._quota_guard.check = AsyncMock(return_value=True)
    mgr._subscription_guard = MagicMock()

    provider = await mgr.get_engine_routed(
        engine_type="image",
        user_id=1,
        subscription_tier="pro",
    )
    assert provider is not None
    assert provider.name == "flux"


def _select_for_test(ctx, providers):
    """测试用 Router 替身：从扁平 providers dict 中按候选顺序选第一个可用的"""
    # _instantiated_providers 是扁平结构 {provider_name: instance}
    # 兼容旧测试传 {engine_type: {name: instance}} 的嵌套结构
    flat = providers
    if any(isinstance(v, dict) for v in providers.values()):
        flat = providers.get(ctx.engine_type, {})
    if not flat:
        return None
    # 简单返回第一个（按插入序）
    return next(iter(flat.values()))
