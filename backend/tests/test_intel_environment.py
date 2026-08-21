"""P2 Task 17: Intel XPU 模拟环境 E2E 测试

模拟 Intel Arc GPU（Intel Arc A770）下：
- GPUVendorDetector 识别 vendor=INTEL
- DeviceManager.get_device_string() 返回 "xpu:0"
- DeviceManager.recommend_llm_engine() 返回 "llama_cpp"
- EngineManager LLM 路由跳过 qwen_local，选择 llama_cpp
"""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

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
        self.device_string = "xpu:0"

    async def initialize(self) -> None:
        self._initialized = True

    async def health_check(self) -> bool:
        return True

    async def chat(self, messages, **kwargs):
        return GenerationResult(success=True, data="llamacpp", metadata={"device": self.device_string})

    async def chat_stream(self, messages, **kwargs):
        yield "llamacpp"


@pytest.fixture
def _intel_torch(monkeypatch):
    """模拟 Intel XPU 环境：torch.cuda.is_available()=False，torch.xpu.is_available()=True"""
    fake_torch = MagicMock()
    fake_torch.cuda.is_available.return_value = False
    fake_torch.xpu.is_available.return_value = True
    props = MagicMock()
    props.name = "Intel Arc A770 Graphics"
    props.total_memory = 16 * 1024**3
    fake_torch.xpu.get_device_properties.return_value = props
    # 实际实现使用 get_device_name(0) 获取设备名，必须显式 mock
    fake_torch.xpu.get_device_name.return_value = "Intel Arc A770 Graphics"
    fake_torch.xpu.device_count.return_value = 1
    fake_torch.xpu.memory_allocated.return_value = 0
    return fake_torch


@pytest.fixture
def _reset_dm_singleton():
    from app.core.device_manager import DeviceManager
    inst = DeviceManager._instance
    DeviceManager._instance = None
    yield
    DeviceManager._instance = inst


def test_intel_vendor_detected(_intel_torch):
    """Intel 环境下 GPUVendorDetector 正确识别 vendor=INTEL"""
    with patch("app.core.gpu_vendor_detector._TORCH_AVAILABLE", True), \
         patch("app.core.gpu_vendor_detector.torch", _intel_torch):
        from app.core.gpu_vendor_detector import GPUVendorDetector, GPUVendor
        detector = GPUVendorDetector()
        info = detector.detect()
        assert info is not None
        assert info.vendor == GPUVendor.INTEL
        assert "Intel" in info.device_name or "Arc" in info.device_name
        assert info.vram_gb == 16.0
        assert info.backend == "xpu"


def test_intel_device_manager_returns_xpu_string(_intel_torch, _reset_dm_singleton):
    """Intel 环境下 DeviceManager.get_device_string() 返回 'xpu:0'"""
    with patch("app.core.gpu_vendor_detector._TORCH_AVAILABLE", True), \
         patch("app.core.gpu_vendor_detector.torch", _intel_torch):
        from app.core.device_manager import DeviceManager
        from app.core.gpu_vendor_detector import GPUVendorDetector

        dm = DeviceManager.get_instance()
        dm._gpu_info = GPUVendorDetector().detect()
        dm._initialized = True

        device_str = dm.get_device_string("image")
        assert device_str == "xpu:0"


def test_intel_device_manager_recommends_llama_cpp(_intel_torch, _reset_dm_singleton):
    """Intel 环境下 DeviceManager.recommend_llm_engine() 返回 'llama_cpp'"""
    with patch("app.core.gpu_vendor_detector._TORCH_AVAILABLE", True), \
         patch("app.core.gpu_vendor_detector.torch", _intel_torch):
        from app.core.device_manager import DeviceManager
        from app.core.gpu_vendor_detector import GPUVendorDetector

        dm = DeviceManager.get_instance()
        dm._gpu_info = GPUVendorDetector().detect()
        dm._initialized = True

        assert dm.recommend_llm_engine() == "llama_cpp"


def test_intel_device_manager_torch_dtype_is_float16(_intel_torch, _reset_dm_singleton):
    """Intel 环境下 DeviceManager.get_torch_dtype() 返回 float16"""
    with patch("app.core.gpu_vendor_detector._TORCH_AVAILABLE", True), \
         patch("app.core.gpu_vendor_detector.torch", _intel_torch):
        from app.core.device_manager import DeviceManager
        from app.core.gpu_vendor_detector import GPUVendorDetector

        dm = DeviceManager.get_instance()
        dm._gpu_info = GPUVendorDetector().detect()
        dm._initialized = True

        dtype = dm.get_torch_dtype("image")
        # DeviceManager.get_torch_dtype() 内部 import torch（真实 torch，非 mock），
        # 因此可能返回字符串（torch 未装）或真实 torch.float16。
        if isinstance(dtype, str):
            assert dtype == "float16"
        else:
            import torch
            assert dtype == torch.float16


@pytest.mark.asyncio
async def test_intel_engine_manager_routes_to_llama_cpp(_intel_torch, _reset_dm_singleton):
    """Intel 环境下 EngineManager LLM 路由跳过 qwen_local，选择 llama_cpp"""
    with patch("app.core.gpu_vendor_detector._TORCH_AVAILABLE", True), \
         patch("app.core.gpu_vendor_detector.torch", _intel_torch):
        from app.core.device_manager import DeviceManager
        from app.core.gpu_vendor_detector import GPUVendorDetector
        from app.engines.manager import EngineManager

        dm = DeviceManager.get_instance()
        dm._gpu_info = GPUVendorDetector().detect()
        dm._initialized = True

        qwen = _FakeQwenLocal()
        llama = _FakeLlamaCpp()

        mgr = EngineManager()
        mgr._instantiated_providers = {
            "llm": {"qwen_local": qwen, "llama_cpp": llama},
        }
        mgr._router = MagicMock()
        # 简化的 select：从过滤后的清单中选 llama_cpp（qwen_local 应被过滤掉）
        async def _select(ctx, providers):
            llm_pool = providers.get("llm", {})
            # 在 Intel 环境下，过滤后应只剩 llama_cpp
            assert "qwen_local" not in llm_pool, "qwen_local should be filtered out in Intel env"
            return llm_pool.get("llama_cpp")
        mgr._router.select = _select
        mgr._quota_guard = MagicMock()
        mgr._quota_guard.check = AsyncMock(return_value=True)
        mgr._subscription_guard = MagicMock()
        mgr._subscription_guard.verify = AsyncMock(return_value=True)

        provider = await mgr.get_engine_routed(
            engine_type="llm",
            user_id=1,
            subscription_tier="pro",
        )
        assert provider is not None
        assert provider.name == "llama_cpp"


def test_intel_flux_provider_uses_xpu_device(_intel_torch, _reset_dm_singleton):
    """Intel 环境下 FluxProvider 通过 DeviceManager 获取 'xpu:0' 设备字符串"""
    with patch("app.core.gpu_vendor_detector._TORCH_AVAILABLE", True), \
         patch("app.core.gpu_vendor_detector.torch", _intel_torch):
        from app.core.device_manager import DeviceManager
        from app.core.gpu_vendor_detector import GPUVendorDetector

        dm = DeviceManager.get_instance()
        dm._gpu_info = GPUVendorDetector().detect()
        dm._initialized = True

        from app.engines.image.flux import FluxProvider
        with patch("app.engines.image.flux._DIFFUSERS_AVAILABLE", False):
            p = FluxProvider(model_id="black-forest-labs/FLUX.1-dev")
            # FluxProvider 在 P2 Task 7 改造后，通过 DeviceManager 获取设备字符串并赋值给 self.device
            device_str = p._resolve_device_string() if hasattr(p, "_resolve_device_string") else p.device
            assert device_str == "xpu:0"
