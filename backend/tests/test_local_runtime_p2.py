"""Tests for Phase 8 P2 Task 3: LocalRuntimeDetector 委托给 DeviceManager."""
import pytest
from unittest.mock import patch, MagicMock

from app.core.local_runtime import LocalRuntimeDetector, RuntimeInfo, DeviceType


def test_detect_uses_device_manager(monkeypatch):
    """detect() 应委托给 DeviceManager.get_gpu_info()"""
    from app.core.device_manager import DeviceManager
    from app.core.gpu_vendor_detector import GPUInfo, GPUVendor
    from app.core.local_runtime import LocalRuntimeDetector, DeviceType

    # 重置单例
    DeviceManager._instance = None
    dm = DeviceManager.get_instance()
    dm._gpu_info = GPUInfo(
        vendor=GPUVendor.AMD,
        device_name="AMD Radeon RX 7900 XTX",
        vram_gb=24.0,
        device_index=0,
        backend="cuda",
    )
    dm._initialized = True

    detector = LocalRuntimeDetector()
    info = detector.detect()
    assert info.device_type == DeviceType.GPU
    assert info.gpu_name == "AMD Radeon RX 7900 XTX"
    assert info.vram_gb == 24.0

    # 清理
    DeviceManager._instance = None


def test_detect_vendor_passthrough(monkeypatch):
    """detect_vendor() 透传 DeviceManager"""
    from app.core.device_manager import DeviceManager
    from app.core.gpu_vendor_detector import GPUVendor, GPUInfo
    from app.core.local_runtime import LocalRuntimeDetector

    DeviceManager._instance = None
    dm = DeviceManager.get_instance()
    dm._gpu_info = GPUInfo(
        vendor=GPUVendor.INTEL,
        device_name="Intel Arc A770",
        vram_gb=16.0,
        device_index=0,
        backend="xpu",
    )
    dm._initialized = True

    detector = LocalRuntimeDetector()
    assert detector.detect_vendor() == GPUVendor.INTEL

    DeviceManager._instance = None
