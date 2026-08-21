"""P2 Tests: FluxProvider 接入 DeviceManager（Task 7）"""
import pytest


def test_flux_uses_device_manager_for_device(monkeypatch):
    """FluxProvider 应通过 DeviceManager 获取 device 字符串"""
    from app.core.device_manager import DeviceManager
    from app.core.gpu_vendor_detector import GPUVendor, GPUInfo
    from app.engines.image.flux import FluxProvider

    DeviceManager._instance = None
    dm = DeviceManager.get_instance()
    dm._gpu_info = GPUInfo(
        vendor=GPUVendor.INTEL,
        device_name="Intel Arc A770",
        vram_gb=16.0,
        device_index=0,
        backend="xpu",
    )

    p = FluxProvider(model_id="test-model")
    assert p.device == "xpu:0"

    DeviceManager._instance = None


def test_flux_uses_device_manager_for_dtype(monkeypatch):
    """FluxProvider 应通过 DeviceManager 获取 dtype"""
    from app.core.device_manager import DeviceManager
    from app.core.gpu_vendor_detector import GPUVendor, GPUInfo
    from app.engines.image.flux import FluxProvider

    DeviceManager._instance = None
    dm = DeviceManager.get_instance()
    dm._gpu_info = GPUInfo(
        vendor=GPUVendor.AMD,
        device_name="AMD Radeon RX 7900 XTX",
        vram_gb=24.0,
        device_index=0,
        backend="cuda",
    )

    p = FluxProvider(model_id="test-model")
    dtype = p.dtype
    if isinstance(dtype, str):
        assert dtype == "float16"  # AMD → float16
    else:
        import torch
        assert dtype == torch.float16

    DeviceManager._instance = None


def test_flux_explicit_device_overrides_device_manager():
    """显式传入 device 参数应覆盖 DeviceManager"""
    from app.engines.image.flux import FluxProvider
    p = FluxProvider(model_id="test-model", device="cuda:1")
    assert p.device == "cuda:1"
