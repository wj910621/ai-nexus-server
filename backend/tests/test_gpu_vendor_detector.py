"""Tests for GPUVendorDetector — NVIDIA/AMD/Intel vendor identification."""
import pytest
from unittest.mock import MagicMock, patch

from app.core.gpu_vendor_detector import (
    GPUVendor,
    GPUInfo,
    GPUVendorDetector,
)


def test_gpu_vendor_enum_values():
    """GPUVendor 枚举应有 4 个值"""
    assert GPUVendor.NVIDIA == "nvidia"
    assert GPUVendor.AMD == "amd"
    assert GPUVendor.INTEL == "intel"
    assert GPUVendor.NONE == "none"


def test_gpu_info_dataclass_fields():
    """GPUInfo dataclass 字段"""
    info = GPUInfo(
        vendor=GPUVendor.NVIDIA,
        device_name="NVIDIA RTX 4090",
        vram_gb=24.0,
        device_index=0,
        backend="cuda",
    )
    assert info.vendor == GPUVendor.NVIDIA
    assert info.device_name == "NVIDIA RTX 4090"
    assert info.vram_gb == 24.0
    assert info.device_index == 0
    assert info.backend == "cuda"


@pytest.mark.parametrize("device_name,expected_vendor", [
    ("NVIDIA GeForce RTX 4090", GPUVendor.NVIDIA),
    ("NVIDIA GeForce RTX 3060", GPUVendor.NVIDIA),
    ("NVIDIA RTX A6000", GPUVendor.NVIDIA),
    ("AMD Radeon RX 7900 XTX", GPUVendor.AMD),
    ("AMD Radeon PRO W7900", GPUVendor.AMD),
    ("AMD Instinct MI300X", GPUVendor.AMD),
    ("gfx1100", GPUVendor.AMD),  # ROCm GPU 命名
    ("gfx942", GPUVendor.AMD),
    ("Intel Arc A770", GPUVendor.INTEL),
    ("Intel(R) Arc(TM) A750", GPUVendor.INTEL),
    ("Intel(R) Data Center GPU Max 1100", GPUVendor.INTEL),
])
def test_vendor_identification_by_name(device_name, expected_vendor, monkeypatch):
    """测试厂商识别规则（基于设备名）"""
    detector = GPUVendorDetector()
    fake_torch = MagicMock()
    fake_torch.cuda.is_available.return_value = True
    fake_torch.cuda.device_count.return_value = 1
    fake_torch.cuda.get_device_name.return_value = device_name
    fake_torch.cuda.get_device_properties.return_value = MagicMock(
        total_memory=16 * 1024**3
    )
    # Mock torch.xpu 不可用
    fake_torch.xpu.is_available.return_value = False
    monkeypatch.setattr("app.core.gpu_vendor_detector.torch", fake_torch)
    monkeypatch.setattr("app.core.gpu_vendor_detector._TORCH_AVAILABLE", True)

    info = detector.detect()
    assert info is not None
    assert info.vendor == expected_vendor


def test_nvidia_cuda_available(monkeypatch):
    """NVIDIA CUDA 可用，backend 应为 cuda"""
    detector = GPUVendorDetector()
    fake_torch = MagicMock()
    fake_torch.cuda.is_available.return_value = True
    fake_torch.cuda.device_count.return_value = 1
    fake_torch.cuda.get_device_name.return_value = "NVIDIA GeForce RTX 4090"
    fake_torch.cuda.get_device_properties.return_value = MagicMock(
        total_memory=24 * 1024**3
    )
    fake_torch.xpu.is_available.return_value = False
    monkeypatch.setattr("app.core.gpu_vendor_detector.torch", fake_torch)
    monkeypatch.setattr("app.core.gpu_vendor_detector._TORCH_AVAILABLE", True)

    info = detector.detect()
    assert info.vendor == GPUVendor.NVIDIA
    assert info.backend == "cuda"
    assert info.vram_gb == 24.0


def test_amd_rocm_available(monkeypatch):
    """AMD ROCm 可用（走 torch.cuda API），backend 仍为 cuda"""
    detector = GPUVendorDetector()
    fake_torch = MagicMock()
    fake_torch.cuda.is_available.return_value = True
    fake_torch.cuda.device_count.return_value = 1
    fake_torch.cuda.get_device_name.return_value = "AMD Radeon RX 7900 XTX"
    fake_torch.cuda.get_device_properties.return_value = MagicMock(
        total_memory=24 * 1024**3
    )
    fake_torch.xpu.is_available.return_value = False
    monkeypatch.setattr("app.core.gpu_vendor_detector.torch", fake_torch)
    monkeypatch.setattr("app.core.gpu_vendor_detector._TORCH_AVAILABLE", True)

    info = detector.detect()
    assert info.vendor == GPUVendor.AMD
    assert info.backend == "cuda"  # ROCm 走 cuda API


def test_intel_xpu_available(monkeypatch):
    """Intel XPU 可用，backend 应为 xpu"""
    detector = GPUVendorDetector()
    fake_torch = MagicMock()
    fake_torch.cuda.is_available.return_value = False
    fake_torch.xpu.is_available.return_value = True
    fake_torch.xpu.device_count.return_value = 1
    fake_torch.xpu.get_device_name.return_value = "Intel Arc A770"
    fake_torch.xpu.get_device_properties.return_value = MagicMock(
        total_memory=16 * 1024**3
    )
    monkeypatch.setattr("app.core.gpu_vendor_detector.torch", fake_torch)
    monkeypatch.setattr("app.core.gpu_vendor_detector._TORCH_AVAILABLE", True)

    info = detector.detect()
    assert info.vendor == GPUVendor.INTEL
    assert info.backend == "xpu"
    assert info.vram_gb == 16.0


def test_no_gpu_fallback_to_none(monkeypatch):
    """无 GPU 时返回 None"""
    detector = GPUVendorDetector()
    fake_torch = MagicMock()
    fake_torch.cuda.is_available.return_value = False
    fake_torch.xpu.is_available.return_value = False
    monkeypatch.setattr("app.core.gpu_vendor_detector.torch", fake_torch)
    monkeypatch.setattr("app.core.gpu_vendor_detector._TORCH_AVAILABLE", True)

    info = detector.detect()
    assert info is None


def test_detection_torch_not_available(monkeypatch):
    """torch 未安装时返回 None"""
    detector = GPUVendorDetector()
    monkeypatch.setattr("app.core.gpu_vendor_detector._TORCH_AVAILABLE", False)

    info = detector.detect()
    assert info is None


def test_detection_cuda_exception_swallowed(monkeypatch):
    """torch.cuda 抛异常应被吞掉，回退 None"""
    detector = GPUVendorDetector()
    fake_torch = MagicMock()
    fake_torch.cuda.is_available.side_effect = RuntimeError("driver error")
    fake_torch.xpu.is_available.return_value = False
    monkeypatch.setattr("app.core.gpu_vendor_detector.torch", fake_torch)
    monkeypatch.setattr("app.core.gpu_vendor_detector._TORCH_AVAILABLE", True)

    info = detector.detect()
    assert info is None


def test_unknown_gpu_name_falls_back_to_none(monkeypatch):
    """未知 GPU 名称应回退到 None"""
    detector = GPUVendorDetector()
    fake_torch = MagicMock()
    fake_torch.cuda.is_available.return_value = True
    fake_torch.cuda.device_count.return_value = 1
    fake_torch.cuda.get_device_name.return_value = "Unknown Mystery GPU"
    fake_torch.cuda.get_device_properties.return_value = MagicMock(
        total_memory=8 * 1024**3
    )
    fake_torch.xpu.is_available.return_value = False
    monkeypatch.setattr("app.core.gpu_vendor_detector.torch", fake_torch)
    monkeypatch.setattr("app.core.gpu_vendor_detector._TORCH_AVAILABLE", True)

    info = detector.detect()
    assert info is None
