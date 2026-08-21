"""P2 Tests for HunyuanProvider - DeviceManager integration (Task 9)."""
def test_hunyuan_uses_device_manager_for_device():
    """HunyuanProvider 应通过 DeviceManager 获取 device"""
    from app.core.device_manager import DeviceManager
    from app.core.gpu_vendor_detector import GPUVendor, GPUInfo
    from app.engines.video.hunyuan import HunyuanProvider

    DeviceManager._instance = None
    dm = DeviceManager.get_instance()
    dm._gpu_info = GPUInfo(
        vendor=GPUVendor.INTEL,
        device_name="Intel Arc A770",
        vram_gb=16.0,
        device_index=0,
        backend="xpu",
    )

    p = HunyuanProvider()
    assert p.device == "xpu:0"

    DeviceManager._instance = None


def test_hunyuan_uses_device_manager_for_dtype():
    """HunyuanProvider 应通过 DeviceManager 获取 dtype"""
    from app.core.device_manager import DeviceManager
    from app.core.gpu_vendor_detector import GPUVendor, GPUInfo
    from app.engines.video.hunyuan import HunyuanProvider

    DeviceManager._instance = None
    dm = DeviceManager.get_instance()
    dm._gpu_info = GPUInfo(
        vendor=GPUVendor.AMD,
        device_name="AMD Radeon RX 7900 XTX",
        vram_gb=24.0,
        device_index=0,
        backend="cuda",
    )

    p = HunyuanProvider()
    dtype = p.dtype
    if isinstance(dtype, str):
        assert dtype == "float16"
    else:
        import torch
        assert dtype == torch.float16

    DeviceManager._instance = None


def test_hunyuan_explicit_device_overrides_device_manager():
    """显式传入 device 应覆盖 DeviceManager"""
    from app.engines.video.hunyuan import HunyuanProvider
    p = HunyuanProvider(device="cuda:1")
    assert p.device == "cuda:1"
