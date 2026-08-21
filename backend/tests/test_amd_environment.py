"""P2 Task 17: AMD ROCm 模拟环境 E2E 测试

模拟 AMD GPU（gfx1100 / Radeon RX 7900 XTX）下：
- GPUVendorDetector 识别 vendor=AMD
- DeviceManager.get_device_string() 返回 "cuda:0"（ROCm 兼容）
- DeviceManager.recommend_llm_engine() 返回 "vllm"
- EngineManager LLM 路由选择 qwen_local（不跳过）
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
        self.device_string = "cuda:0"

    async def initialize(self) -> None:
        self._initialized = True

    async def health_check(self) -> bool:
        return True

    async def chat(self, messages, **kwargs):
        return GenerationResult(success=True, data="qwen", metadata={"device": self.device_string})

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


@pytest.fixture
def _amd_torch(monkeypatch):
    """模拟 AMD ROCm 环境：torch.cuda.is_available()=True，设备名为 gfx1100"""
    fake_torch = MagicMock()
    fake_torch.cuda.is_available.return_value = True
    fake_torch.xpu.is_available.return_value = False
    props = MagicMock()
    props.name = "AMD Radeon RX 7900 XTX"  # 设备名含 "AMD" / "Radeon"
    props.total_memory = 24 * 1024**3
    fake_torch.cuda.get_device_properties.return_value = props
    # 实际实现使用 get_device_name(0) 获取设备名，必须显式 mock
    fake_torch.cuda.get_device_name.return_value = "AMD Radeon RX 7900 XTX"
    fake_torch.cuda.device_count.return_value = 1
    fake_torch.cuda.memory_allocated.return_value = 0
    # 触发 AMD 路径的关键：torch.version.hip 存在（ROCm 标识）
    fake_torch.version.hip = "5.7.0"
    fake_torch.version.cuda = None
    return fake_torch


@pytest.fixture
def _reset_dm_singleton():
    from app.core.device_manager import DeviceManager
    inst = DeviceManager._instance
    DeviceManager._instance = None
    yield
    DeviceManager._instance = inst


def test_amd_vendor_detected(_amd_torch, monkeypatch):
    """AMD 环境下 GPUVendorDetector 正确识别 vendor=AMD"""
    with patch("app.core.gpu_vendor_detector._TORCH_AVAILABLE", True), \
         patch("app.core.gpu_vendor_detector.torch", _amd_torch):
        from app.core.gpu_vendor_detector import GPUVendorDetector, GPUVendor
        detector = GPUVendorDetector()
        info = detector.detect()
        assert info is not None
        assert info.vendor == GPUVendor.AMD
        assert "Radeon" in info.device_name or "AMD" in info.device_name
        assert info.vram_gb == 24.0
        assert info.backend == "cuda"  # ROCm 兼容 CUDA API


def test_amd_device_manager_returns_cuda_string(_amd_torch, _reset_dm_singleton, monkeypatch):
    """AMD 环境下 DeviceManager.get_device_string() 返回 'cuda:0'"""
    with patch("app.core.gpu_vendor_detector._TORCH_AVAILABLE", True), \
         patch("app.core.gpu_vendor_detector.torch", _amd_torch):
        from app.core.device_manager import DeviceManager
        from app.core.gpu_vendor_detector import GPUVendorDetector

        dm = DeviceManager.get_instance()
        # 同步初始化（绕过 async initialize）
        dm._gpu_info = GPUVendorDetector().detect()
        dm._initialized = True

        device_str = dm.get_device_string("image")
        assert device_str == "cuda:0"


def test_amd_device_manager_recommends_vllm(_amd_torch, _reset_dm_singleton):
    """AMD 环境下 DeviceManager.recommend_llm_engine() 返回 'vllm'"""
    with patch("app.core.gpu_vendor_detector._TORCH_AVAILABLE", True), \
         patch("app.core.gpu_vendor_detector.torch", _amd_torch):
        from app.core.device_manager import DeviceManager
        from app.core.gpu_vendor_detector import GPUVendorDetector

        dm = DeviceManager.get_instance()
        dm._gpu_info = GPUVendorDetector().detect()
        dm._initialized = True

        assert dm.recommend_llm_engine() == "vllm"


def test_amd_device_manager_torch_dtype_is_float16(_amd_torch, _reset_dm_singleton):
    """AMD 环境下 DeviceManager.get_torch_dtype() 返回 float16（避免 bf16 兼容问题）"""
    with patch("app.core.gpu_vendor_detector._TORCH_AVAILABLE", True), \
         patch("app.core.gpu_vendor_detector.torch", _amd_torch):
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
async def test_amd_engine_manager_routes_to_qwen_local(_amd_torch, _reset_dm_singleton):
    """AMD 环境下 EngineManager LLM 路由保留 qwen_local（vLLM ROCm 支持）"""
    with patch("app.core.gpu_vendor_detector._TORCH_AVAILABLE", True), \
         patch("app.core.gpu_vendor_detector.torch", _amd_torch):
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
        # 简化的 select：从过滤后的清单中选 qwen_local
        async def _select(ctx, providers):
            llm_pool = providers.get("llm", {})
            return llm_pool.get("qwen_local")
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
        assert provider.name == "qwen_local"


def test_amd_flux_provider_uses_cuda_device(_amd_torch, _reset_dm_singleton, monkeypatch):
    """AMD 环境下 FluxProvider 通过 DeviceManager 获取 'cuda:0' 设备字符串"""
    with patch("app.core.gpu_vendor_detector._TORCH_AVAILABLE", True), \
         patch("app.core.gpu_vendor_detector.torch", _amd_torch):
        from app.core.device_manager import DeviceManager
        from app.core.gpu_vendor_detector import GPUVendorDetector

        dm = DeviceManager.get_instance()
        dm._gpu_info = GPUVendorDetector().detect()
        dm._initialized = True

        # 模拟 FluxProvider 初始化时调用 DeviceManager
        from app.engines.image.flux import FluxProvider
        with patch("app.engines.image.flux._DIFFUSERS_AVAILABLE", False):
            p = FluxProvider(model_id="black-forest-labs/FLUX.1-dev")
            # FluxProvider 在 P2 Task 7 改造后，通过 DeviceManager 获取设备字符串并赋值给 self.device
            device_str = p._resolve_device_string() if hasattr(p, "_resolve_device_string") else p.device
            assert device_str == "cuda:0"
