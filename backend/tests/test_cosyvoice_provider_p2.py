"""P2 Tests for CosyVoiceProvider - DeviceManager integration (Task 10)."""
def test_cosyvoice_uses_device_manager_for_device():
    """CosyVoiceProvider 应通过 DeviceManager 获取 device"""
    from app.core.device_manager import DeviceManager
    from app.core.gpu_vendor_detector import GPUVendor, GPUInfo
    from app.engines.tts.cosyvoice import CosyVoiceProvider

    DeviceManager._instance = None
    dm = DeviceManager.get_instance()
    dm._gpu_info = GPUInfo(
        vendor=GPUVendor.INTEL,
        device_name="Intel Arc A770",
        vram_gb=16.0,
        device_index=0,
        backend="xpu",
    )

    p = CosyVoiceProvider()
    assert p.device == "xpu:0"

    DeviceManager._instance = None


def test_cosyvoice_uses_device_manager_for_dtype():
    """CosyVoiceProvider 应通过 DeviceManager 获取 dtype"""
    from app.core.device_manager import DeviceManager
    from app.core.gpu_vendor_detector import GPUVendor, GPUInfo
    from app.engines.tts.cosyvoice import CosyVoiceProvider

    DeviceManager._instance = None
    dm = DeviceManager.get_instance()
    dm._gpu_info = GPUInfo(
        vendor=GPUVendor.AMD,
        device_name="AMD Radeon RX 7900 XTX",
        vram_gb=24.0,
        device_index=0,
        backend="cuda",
    )

    p = CosyVoiceProvider()
    dtype = p.dtype
    if isinstance(dtype, str):
        assert dtype == "float16"
    else:
        import torch
        assert dtype == torch.float16

    DeviceManager._instance = None


def test_cosyvoice_explicit_device_overrides_device_manager():
    """显式传入 device 应覆盖 DeviceManager"""
    from app.engines.tts.cosyvoice import CosyVoiceProvider
    p = CosyVoiceProvider(device="cuda:1")
    assert p.device == "cuda:1"
