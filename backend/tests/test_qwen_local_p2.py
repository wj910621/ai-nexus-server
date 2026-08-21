"""Tests for QwenLocalProvider P2 改造 — engine_hint + DeviceManager 适配

Phase 8 P2 Task 11: AMD/Intel GPU 支持

测试场景：
- DeviceManager 获取 device 字符串
- engine_hint=vllm（NVIDIA/AMD）
- engine_hint=llama_cpp（Intel/CPU）→ _available=False
- _available=False 时 health_check 返回 False
"""
import pytest


@pytest.fixture(autouse=True)
def reset_device_manager_singleton():
    """每个测试前重置 DeviceManager 单例"""
    from app.core.device_manager import DeviceManager
    DeviceManager._instance = None
    yield
    DeviceManager._instance = None


def test_qwen_local_uses_device_manager_for_device():
    """QwenLocalProvider 应通过 DeviceManager 获取 device"""
    from app.core.device_manager import DeviceManager
    from app.core.gpu_vendor_detector import GPUVendor, GPUInfo
    from app.engines.llm.qwen_local import QwenLocalProvider

    DeviceManager._instance = None
    dm = DeviceManager.get_instance()
    dm._gpu_info = GPUInfo(
        vendor=GPUVendor.NVIDIA,
        device_name="NVIDIA RTX 4090",
        vram_gb=24.0,
        device_index=0,
        backend="cuda",
    )

    p = QwenLocalProvider()
    assert p.device == "cuda:0"

    DeviceManager._instance = None


def test_qwen_local_engine_hint_vllm_for_nvidia():
    """NVIDIA 环境 → engine_hint='vllm'"""
    from app.core.device_manager import DeviceManager
    from app.core.gpu_vendor_detector import GPUVendor, GPUInfo
    from app.engines.llm.qwen_local import QwenLocalProvider

    DeviceManager._instance = None
    dm = DeviceManager.get_instance()
    dm._gpu_info = GPUInfo(
        vendor=GPUVendor.NVIDIA,
        device_name="NVIDIA RTX 4090",
        vram_gb=24.0,
        device_index=0,
        backend="cuda",
    )

    p = QwenLocalProvider()
    assert p.engine_hint == "vllm"
    # vllm 引擎下，_available 应取决于 vllm 是否安装
    assert p._available in (True, False)  # 不强制，只看属性存在

    DeviceManager._instance = None


def test_qwen_local_engine_hint_llama_cpp_for_intel():
    """Intel 环境 → engine_hint='llama_cpp'，_available=False"""
    from app.core.device_manager import DeviceManager
    from app.core.gpu_vendor_detector import GPUVendor, GPUInfo
    from app.engines.llm.qwen_local import QwenLocalProvider

    DeviceManager._instance = None
    dm = DeviceManager.get_instance()
    dm._gpu_info = GPUInfo(
        vendor=GPUVendor.INTEL,
        device_name="Intel Arc A770",
        vram_gb=16.0,
        device_index=0,
        backend="xpu",
    )

    p = QwenLocalProvider()
    assert p.engine_hint == "llama_cpp"
    assert p._available is False  # Intel 下由 LlamaCppProvider 接管

    DeviceManager._instance = None


def test_qwen_local_engine_hint_llama_cpp_for_cpu():
    """CPU 环境 → engine_hint='llama_cpp'"""
    from app.core.device_manager import DeviceManager
    from app.engines.llm.qwen_local import QwenLocalProvider

    DeviceManager._instance = None
    dm = DeviceManager.get_instance()
    dm._gpu_info = None  # CPU 模式

    p = QwenLocalProvider()
    assert p.engine_hint == "llama_cpp"
    assert p._available is False

    DeviceManager._instance = None


@pytest.mark.asyncio
async def test_qwen_local_health_check_returns_false_when_unavailable():
    """_available=False 时 health_check 返回 False"""
    from app.core.device_manager import DeviceManager
    from app.core.gpu_vendor_detector import GPUVendor, GPUInfo
    from app.engines.llm.qwen_local import QwenLocalProvider

    DeviceManager._instance = None
    dm = DeviceManager.get_instance()
    dm._gpu_info = GPUInfo(
        vendor=GPUVendor.INTEL,
        device_name="Intel Arc A770",
        vram_gb=16.0,
        device_index=0,
        backend="xpu",
    )

    p = QwenLocalProvider()
    result = await p.health_check()
    assert result is False

    DeviceManager._instance = None
