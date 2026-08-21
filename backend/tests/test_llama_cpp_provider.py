"""Tests for LlamaCppProvider — Intel XPU / CPU LLM Provider (Phase 8 P2)"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.engines.base import GenerationResult


@pytest.fixture(autouse=True)
def reset_device_manager_singleton():
    """每个测试前重置 DeviceManager 单例"""
    from app.core.device_manager import DeviceManager
    DeviceManager._instance = None
    yield
    DeviceManager._instance = None


@pytest.fixture
def cpu_device_manager():
    """CPU 模式 DeviceManager"""
    from app.core.device_manager import DeviceManager
    dm = DeviceManager.get_instance()
    dm._gpu_info = None  # CPU 模式
    dm._initialized = True
    return dm


@pytest.fixture
def intel_device_manager():
    """Intel XPU 模式 DeviceManager"""
    from app.core.device_manager import DeviceManager
    from app.core.gpu_vendor_detector import GPUVendor, GPUInfo
    dm = DeviceManager.get_instance()
    dm._gpu_info = GPUInfo(
        vendor=GPUVendor.INTEL,
        device_name="Intel Arc A770",
        vram_gb=16.0,
        device_index=0,
        backend="xpu",
    )
    dm._initialized = True
    return dm


def test_provider_class_attributes():
    """LlamaCppProvider 类属性"""
    from app.engines.llm.llama_cpp import LlamaCppProvider
    assert LlamaCppProvider.name == "llama_cpp"
    assert LlamaCppProvider.is_local is True
    assert "Qwen/Qwen2.5-7B-Instruct-GGUF" in LlamaCppProvider.supported_models


def test_initialize_cpu_mode(cpu_device_manager):
    """CPU 模式下 n_gpu_layers 应为 0"""
    from app.engines.llm.llama_cpp import LlamaCppProvider
    p = LlamaCppProvider()
    # CPU 模式 → n_gpu_layers=0
    assert p._n_gpu_layers == 0
    assert p.device_string == "cpu"


def test_initialize_intel_xpu_mode(intel_device_manager):
    """Intel XPU 模式下 n_gpu_layers 应为 -1（全卸载到 Vulkan）"""
    from app.engines.llm.llama_cpp import LlamaCppProvider
    p = LlamaCppProvider()
    assert p._n_gpu_layers == -1
    assert p.device_string == "xpu:0"


@pytest.mark.asyncio
async def test_chat_returns_generation_result(cpu_device_manager):
    """chat 返回 GenerationResult 结构"""
    from app.engines.llm.llama_cpp import LlamaCppProvider

    with patch("app.engines.llm.llama_cpp._LLAMA_CPP_AVAILABLE", True):
        with patch("app.engines.llm.llama_cpp.Llama") as mock_llama_cls:
            mock_model = MagicMock()
            # 真实 llama-cpp-python API: {"choices": [{"message": {"content": "..."}}]}
            mock_response = {
                "choices": [{"message": {"content": "hello world"}}],
                "usage": {"completion_tokens": 2},
            }
            mock_model.create_chat_completion.return_value = mock_response
            mock_llama_cls.return_value = mock_model

            p = LlamaCppProvider()
            p._model = mock_model
            p._initialized = True

            result = await p.chat(
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=100,
            )

    assert isinstance(result, GenerationResult)
    assert result.success is True
    assert isinstance(result.data, str)
    assert "hello" in result.data


@pytest.mark.asyncio
async def test_chat_not_initialized_returns_error(cpu_device_manager):
    """未初始化时返回错误"""
    from app.engines.llm.llama_cpp import LlamaCppProvider

    with patch("app.engines.llm.llama_cpp._LLAMA_CPP_AVAILABLE", True):
        p = LlamaCppProvider()
        p._model = None
        p._initialized = False

        result = await p.chat(messages=[{"role": "user", "content": "hi"}])

    assert result.success is False
    assert "未初始化" in result.error or "not initialized" in result.error.lower()


@pytest.mark.asyncio
async def test_chat_stream_yields_tokens(cpu_device_manager):
    """流式生成逐 token yield"""
    from app.engines.llm.llama_cpp import LlamaCppProvider

    with patch("app.engines.llm.llama_cpp._LLAMA_CPP_AVAILABLE", True):
        mock_model = MagicMock()

        # 模拟 create_chat_completion 返回同步流式 generator（匹配真实 llama-cpp-python API）
        def mock_stream(*args, **kwargs):
            for chunk in [{"choices": [{"delta": {"content": "hello"}}]},
                          {"choices": [{"delta": {"content": " world"}}]}]:
                yield chunk

        mock_model.create_chat_completion = mock_stream

        p = LlamaCppProvider()
        p._model = mock_model
        p._initialized = True

        tokens = []
        async for tok in p.chat_stream(messages=[{"role": "user", "content": "hi"}]):
            tokens.append(tok)

    assert len(tokens) == 2
    assert tokens[0] == "hello"
    assert tokens[1] == " world"


@pytest.mark.asyncio
async def test_initialize_failure_sets_init_error(cpu_device_manager):
    """llama_cpp 未安装时 initialize 设置 _init_error"""
    from app.engines.llm.llama_cpp import LlamaCppProvider

    with patch("app.engines.llm.llama_cpp._LLAMA_CPP_AVAILABLE", False):
        p = LlamaCppProvider()
        await p.initialize()

    assert p._initialized is False
    assert p._init_error is not None
    assert "llama_cpp" in p._init_error.lower() or "not installed" in p._init_error.lower()


@pytest.mark.asyncio
async def test_health_check_returns_false_when_unavailable(cpu_device_manager):
    """未初始化时 health_check 返回 False"""
    from app.engines.llm.llama_cpp import LlamaCppProvider

    with patch("app.engines.llm.llama_cpp._LLAMA_CPP_AVAILABLE", False):
        p = LlamaCppProvider()
        result = await p.health_check()
    assert result is False


def test_get_info_includes_engine_hint(intel_device_manager):
    """get_info 应包含 engine_hint"""
    from app.engines.llm.llama_cpp import LlamaCppProvider
    p = LlamaCppProvider()
    info = p.get_info()
    assert "device_string" in info
    assert info["device_string"] == "xpu:0"


def test_module_registration():
    """模块导入时自动注册到 provider_registry"""
    import importlib
    import app.engines.llm.llama_cpp  # noqa: F401
    from app.engines.registry import ProviderRegistry

    providers = ProviderRegistry.list_providers("llm")
    assert "llama_cpp" in providers
