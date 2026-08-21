"""Tests for QwenLocalProvider (vLLM)."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.engines.base import GenerationResult


@pytest.fixture(autouse=True)
def reset_device_manager_singleton():
    """每个测试前重置 DeviceManager 单例（P2 改造后 QwenLocalProvider 依赖 DeviceManager）"""
    from app.core.device_manager import DeviceManager
    DeviceManager._instance = None
    yield
    DeviceManager._instance = None


@pytest.fixture
def qwen_provider():
    from app.core.device_manager import DeviceManager
    from app.core.gpu_vendor_detector import GPUVendor, GPUInfo
    from app.engines.llm.qwen_local import QwenLocalProvider

    # P2: 设为 NVIDIA 环境，使 engine_hint="vllm"、_available=True
    dm = DeviceManager.get_instance()
    dm._gpu_info = GPUInfo(
        vendor=GPUVendor.NVIDIA,
        device_name="NVIDIA RTX 4090",
        vram_gb=24.0,
        device_index=0,
        backend="cuda",
    )

    p = QwenLocalProvider(model_id="Qwen/Qwen2.5-7B-Instruct")
    p._initialized = True
    return p


def test_import_with_mocked_vllm():
    """vllm 未安装时仍可导入模块"""
    import sys
    original = sys.modules.get("vllm")
    sys.modules["vllm"] = MagicMock()  # type: ignore
    try:
        import importlib
        import app.engines.llm.qwen_local as qwen_mod
        importlib.reload(qwen_mod)
    finally:
        if original is not None:
            sys.modules["vllm"] = original
        else:
            del sys.modules["vllm"]


@pytest.mark.asyncio
async def test_chat_success(qwen_provider):
    """对话生成成功"""
    fake_engine = MagicMock()
    fake_output = MagicMock()
    fake_output.outputs = [MagicMock(text="你好，我是 Qwen！")]
    fake_engine.generate = AsyncMock(return_value=fake_output)
    qwen_provider._engine = fake_engine
    qwen_provider._tokenizer = MagicMock()
    qwen_provider._tokenizer.apply_chat_template = MagicMock(return_value=[1, 2, 3])
    qwen_provider._tokenizer.decode = MagicMock(return_value="你好，我是 Qwen！")

    result = await qwen_provider.chat(
        messages=[{"role": "user", "content": "你是谁"}],
        max_tokens=100,
    )

    assert result.success is True
    assert result.data == "你好，我是 Qwen！"
    assert result.content_type == "text/plain"
    assert result.metadata["provider"] == "qwen_local"
    assert result.metadata["model"] == "Qwen/Qwen2.5-7B-Instruct"


@pytest.mark.asyncio
async def test_chat_not_initialized():
    """未初始化返回错误"""
    from app.engines.llm.qwen_local import QwenLocalProvider
    p = QwenLocalProvider(model_id="test-model")
    result = await p.chat(messages=[{"role": "user", "content": "hi"}])
    assert result.success is False
    assert "未初始化" in result.error or "not initialized" in result.error.lower()


@pytest.mark.asyncio
async def test_chat_streaming(qwen_provider):
    """流式生成（async generator）"""
    fake_engine = MagicMock()

    async def fake_generate_stream(*args, **kwargs):
        # 模拟 3 个 token 输出
        for token in ["你", "好", "！"]:
            output = MagicMock()
            output.outputs = [MagicMock(text=token)]
            yield output

    fake_engine.generate = MagicMock(side_effect=fake_generate_stream)
    qwen_provider._engine = fake_engine
    qwen_provider._tokenizer = MagicMock()
    qwen_provider._tokenizer.apply_chat_template = MagicMock(return_value=[1, 2, 3])

    chunks = []
    async for chunk in qwen_provider.chat_stream(
        messages=[{"role": "user", "content": "hi"}],
    ):
        chunks.append(chunk)

    assert "".join(chunks) == "你好！"


@pytest.mark.asyncio
async def test_health_check(qwen_provider):
    """健康检查"""
    with patch.object(qwen_provider, "chat", new=AsyncMock(return_value=GenerationResult(
        success=True, data="hi", content_type="text/plain", metadata={},
    ))):
        result = await qwen_provider.health_check()
    assert result is True
