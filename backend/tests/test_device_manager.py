"""Tests for DeviceManager — 设备/dtype/引擎推荐单例"""
import asyncio
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from app.core.gpu_vendor_detector import GPUVendor, GPUInfo
from app.core.device_manager import DeviceManager


@pytest.fixture(autouse=True)
def reset_device_manager_singleton():
    """每个测试前重置 DeviceManager 单例"""
    DeviceManager._instance = None
    yield
    DeviceManager._instance = None


def make_gpu_info(vendor: GPUVendor, vram_gb: float = 16.0) -> GPUInfo:
    """构造测试用 GPUInfo"""
    names = {
        GPUVendor.NVIDIA: "NVIDIA RTX 4090",
        GPUVendor.AMD: "AMD Radeon RX 7900 XTX",
        GPUVendor.INTEL: "Intel Arc A770",
        GPUVendor.NONE: "",
    }
    backends = {
        GPUVendor.NVIDIA: "cuda",
        GPUVendor.AMD: "cuda",
        GPUVendor.INTEL: "xpu",
        GPUVendor.NONE: "",
    }
    return GPUInfo(
        vendor=vendor,
        device_name=names[vendor],
        vram_gb=vram_gb,
        device_index=0,
        backend=backends[vendor],
    )


def test_singleton_pattern():
    """两次 get_instance 返回同一对象"""
    dm1 = DeviceManager.get_instance()
    dm2 = DeviceManager.get_instance()
    assert dm1 is dm2


def test_get_device_string_nvidia():
    """NVIDIA → cuda:0"""
    dm = DeviceManager.get_instance()
    dm._gpu_info = make_gpu_info(GPUVendor.NVIDIA, vram_gb=24.0)
    assert dm.get_device_string("image") == "cuda:0"
    assert dm.get_device_string("video") == "cuda:0"
    assert dm.get_device_string("llm") == "cuda:0"


def test_get_device_string_amd():
    """AMD → cuda:0（ROCm 走 cuda API）"""
    dm = DeviceManager.get_instance()
    dm._gpu_info = make_gpu_info(GPUVendor.AMD, vram_gb=24.0)
    assert dm.get_device_string("image") == "cuda:0"


def test_get_device_string_intel():
    """Intel → xpu:0"""
    dm = DeviceManager.get_instance()
    dm._gpu_info = make_gpu_info(GPUVendor.INTEL, vram_gb=16.0)
    assert dm.get_device_string("image") == "xpu:0"
    assert dm.get_device_string("llm") == "xpu:0"


def test_get_device_string_no_gpu_cpu():
    """无 GPU → cpu"""
    dm = DeviceManager.get_instance()
    dm._gpu_info = None
    assert dm.get_device_string("image") == "cpu"
    assert dm.get_device_string("llm") == "cpu"


def test_get_torch_dtype_nvidia_high_vram():
    """NVIDIA + 16GB+ VRAM → bfloat16"""
    dm = DeviceManager.get_instance()
    dm._gpu_info = make_gpu_info(GPUVendor.NVIDIA, vram_gb=24.0)
    dtype = dm.get_torch_dtype("image")
    # 测试中 torch 可能未安装，dtype 为字符串
    if isinstance(dtype, str):
        assert dtype == "bfloat16"
    else:
        import torch
        assert dtype == torch.bfloat16


def test_get_torch_dtype_nvidia_low_vram():
    """NVIDIA + <16GB VRAM → float16"""
    dm = DeviceManager.get_instance()
    dm._gpu_info = make_gpu_info(GPUVendor.NVIDIA, vram_gb=8.0)
    dtype = dm.get_torch_dtype("image")
    if isinstance(dtype, str):
        assert dtype == "float16"
    else:
        import torch
        assert dtype == torch.float16


def test_get_torch_dtype_amd():
    """AMD → float16（bfloat16 在 ROCm 支持不完整）"""
    dm = DeviceManager.get_instance()
    dm._gpu_info = make_gpu_info(GPUVendor.AMD, vram_gb=24.0)
    dtype = dm.get_torch_dtype("image")
    if isinstance(dtype, str):
        assert dtype == "float16"
    else:
        import torch
        assert dtype == torch.float16


def test_get_torch_dtype_intel():
    """Intel → float16（bfloat16 在 XPU 支持不完整）"""
    dm = DeviceManager.get_instance()
    dm._gpu_info = make_gpu_info(GPUVendor.INTEL, vram_gb=16.0)
    dtype = dm.get_torch_dtype("image")
    if isinstance(dtype, str):
        assert dtype == "float16"
    else:
        import torch
        assert dtype == torch.float16


def test_get_torch_dtype_cpu():
    """CPU → float32"""
    dm = DeviceManager.get_instance()
    dm._gpu_info = None
    dtype = dm.get_torch_dtype("image")
    if isinstance(dtype, str):
        assert dtype == "float32"
    else:
        import torch
        assert dtype == torch.float32


def test_recommend_llm_engine_nvidia():
    """NVIDIA → vllm"""
    dm = DeviceManager.get_instance()
    dm._gpu_info = make_gpu_info(GPUVendor.NVIDIA)
    assert dm.recommend_llm_engine() == "vllm"


def test_recommend_llm_engine_amd():
    """AMD → vllm（vLLM ROCm 支持）"""
    dm = DeviceManager.get_instance()
    dm._gpu_info = make_gpu_info(GPUVendor.AMD)
    assert dm.recommend_llm_engine() == "vllm"


def test_recommend_llm_engine_intel():
    """Intel → llama_cpp"""
    dm = DeviceManager.get_instance()
    dm._gpu_info = make_gpu_info(GPUVendor.INTEL)
    assert dm.recommend_llm_engine() == "llama_cpp"


def test_recommend_llm_engine_cpu():
    """CPU → llama_cpp"""
    dm = DeviceManager.get_instance()
    dm._gpu_info = None
    assert dm.recommend_llm_engine() == "llama_cpp"


def test_detect_vendor():
    """detect_vendor() 返回 GPUVendor"""
    dm = DeviceManager.get_instance()
    dm._gpu_info = make_gpu_info(GPUVendor.AMD)
    assert dm.detect_vendor() == GPUVendor.AMD

    dm._gpu_info = None
    assert dm.detect_vendor() == GPUVendor.NONE


def test_get_gpu_info():
    """get_gpu_info() 返回缓存的 GPUInfo"""
    dm = DeviceManager.get_instance()
    gpu_info = make_gpu_info(GPUVendor.NVIDIA)
    dm._gpu_info = gpu_info
    assert dm.get_gpu_info() is gpu_info


@pytest.mark.asyncio
async def test_initialize_caches_gpu_info(monkeypatch):
    """initialize() 应缓存 GPUInfo"""
    dm = DeviceManager.get_instance()
    gpu_info = make_gpu_info(GPUVendor.NVIDIA, vram_gb=24.0)

    def mock_detect(self):
        return gpu_info

    monkeypatch.setattr("app.core.device_manager.GPUVendorDetector.detect", mock_detect)
    monkeypatch.setattr("psutil.virtual_memory", lambda: MagicMock(total=32 * 1024**3))

    await dm.initialize()
    assert dm.get_gpu_info() is gpu_info
    assert dm.detect_vendor() == GPUVendor.NVIDIA


@pytest.mark.asyncio
async def test_initialize_fallback_on_detection_failure(monkeypatch):
    """探测抛异常时应回退 CPU 模式，不抛异常"""
    dm = DeviceManager.get_instance()

    def mock_detect_raises(self):
        raise RuntimeError("driver broken")

    monkeypatch.setattr("app.core.device_manager.GPUVendorDetector.detect", mock_detect_raises)
    monkeypatch.setattr("psutil.virtual_memory", lambda: MagicMock(total=16 * 1024**3))

    # 不应抛异常
    await dm.initialize()
    assert dm.get_gpu_info() is None
    assert dm.detect_vendor() == GPUVendor.NONE
    assert dm.get_device_string("image") == "cpu"


@pytest.mark.asyncio
async def test_initialize_idempotent(monkeypatch):
    """重复 initialize 不应重复探测"""
    dm = DeviceManager.get_instance()
    call_count = 0
    gpu_info = make_gpu_info(GPUVendor.NVIDIA)

    def mock_detect(self):
        nonlocal call_count
        call_count += 1
        return gpu_info

    monkeypatch.setattr("app.core.device_manager.GPUVendorDetector.detect", mock_detect)
    monkeypatch.setattr("psutil.virtual_memory", lambda: MagicMock(total=32 * 1024**3))

    await dm.initialize()
    await dm.initialize()
    await dm.initialize()
    assert call_count == 1


@pytest.mark.asyncio
async def test_initialize_lock_serializes_concurrent_calls(monkeypatch):
    """并发 initialize 应串行化"""
    dm = DeviceManager.get_instance()
    call_count = 0
    gpu_info = make_gpu_info(GPUVendor.NVIDIA)

    async def mock_detect_async(self):
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.01)
        return gpu_info

    # 模拟 detect 为同步方法但被多次调用
    def mock_detect(self):
        nonlocal call_count
        call_count += 1
        return gpu_info

    monkeypatch.setattr("app.core.device_manager.GPUVendorDetector.detect", mock_detect)
    monkeypatch.setattr("psutil.virtual_memory", lambda: MagicMock(total=32 * 1024**3))

    # 并发调用 3 次
    await asyncio.gather(dm.initialize(), dm.initialize(), dm.initialize())
    # 由于 idempotent 检查，只应调用 1 次
    assert call_count == 1


def test_get_runtime_info(monkeypatch):
    """get_runtime_info() 返回 RuntimeInfo"""
    from app.core.local_runtime import RuntimeInfo, DeviceType
    dm = DeviceManager.get_instance()
    dm._gpu_info = make_gpu_info(GPUVendor.NVIDIA, vram_gb=24.0)
    dm._runtime_info = RuntimeInfo(
        device_type=DeviceType.GPU,
        vram_gb=24.0,
        ram_gb=32.0,
        gpu_name="NVIDIA RTX 4090",
    )
    info = dm.get_runtime_info()
    assert info.device_type == DeviceType.GPU
    assert info.vram_gb == 24.0
