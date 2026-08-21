"""Tests for Task 15: Local AI Inference — LocalRuntimeDetector."""
import pytest
from unittest.mock import patch, MagicMock

from app.core.local_runtime import LocalRuntimeDetector, RuntimeInfo, DeviceType


def test_detect_returns_runtime_info():
    """detect() returns RuntimeInfo with device_type, vram, ram."""
    detector = LocalRuntimeDetector()
    info = detector.detect()
    assert isinstance(info, RuntimeInfo)
    assert info.device_type in (DeviceType.GPU, DeviceType.CPU, DeviceType.NONE)


def test_detect_gpu_when_torch_cuda_available(monkeypatch):
    """When torch.cuda.is_available() is True, device_type is GPU."""
    fake_torch = MagicMock()
    fake_torch.cuda.is_available.return_value = True
    fake_torch.cuda.get_device_properties.return_value.total_memory = 8 * 1024**3
    fake_torch.cuda.get_device_properties.return_value.name = "NVIDIA RTX 3060"
    monkeypatch.setattr("app.core.local_runtime.torch", fake_torch)
    monkeypatch.setattr("app.core.local_runtime._TORCH_AVAILABLE", True)
    detector = LocalRuntimeDetector()
    info = detector.detect()
    assert info.device_type == DeviceType.GPU
    assert info.vram_gb == 8.0


def test_detect_cpu_when_no_gpu(monkeypatch):
    """When no GPU, device_type is CPU (if RAM sufficient)."""
    fake_torch = MagicMock()
    fake_torch.cuda.is_available.return_value = False
    monkeypatch.setattr("app.core.local_runtime.torch", fake_torch)
    monkeypatch.setattr("app.core.local_runtime._TORCH_AVAILABLE", True)
    monkeypatch.setattr("psutil.virtual_memory", lambda: MagicMock(total=16 * 1024**3))
    detector = LocalRuntimeDetector()
    info = detector.detect()
    assert info.device_type == DeviceType.CPU
    assert info.ram_gb == 16.0


def test_detect_none_when_insufficient_resources(monkeypatch):
    """When no GPU and insufficient RAM, device_type is NONE."""
    fake_torch = MagicMock()
    fake_torch.cuda.is_available.return_value = False
    monkeypatch.setattr("app.core.local_runtime.torch", fake_torch)
    monkeypatch.setattr("app.core.local_runtime._TORCH_AVAILABLE", True)
    monkeypatch.setattr("psutil.virtual_memory", lambda: MagicMock(total=2 * 1024**3))
    detector = LocalRuntimeDetector(min_ram_gb=8)
    info = detector.detect()
    assert info.device_type == DeviceType.NONE


def test_recommend_provider_returns_diffusers_for_gpu(monkeypatch):
    """recommend_image_provider() returns 'diffusers' when GPU available."""
    fake_torch = MagicMock()
    fake_torch.cuda.is_available.return_value = True
    fake_torch.cuda.get_device_properties.return_value.total_memory = 8 * 1024**3
    fake_torch.cuda.get_device_properties.return_value.name = "NVIDIA RTX 3060"
    monkeypatch.setattr("app.core.local_runtime.torch", fake_torch)
    monkeypatch.setattr("app.core.local_runtime._TORCH_AVAILABLE", True)
    detector = LocalRuntimeDetector()
    assert detector.recommend_image_provider() == "diffusers"


def test_recommend_provider_returns_onnx_for_cpu(monkeypatch):
    """recommend_image_provider() returns 'onnx' when only CPU available."""
    fake_torch = MagicMock()
    fake_torch.cuda.is_available.return_value = False
    monkeypatch.setattr("app.core.local_runtime.torch", fake_torch)
    monkeypatch.setattr("app.core.local_runtime._TORCH_AVAILABLE", True)
    monkeypatch.setattr("psutil.virtual_memory", lambda: MagicMock(total=16 * 1024**3))
    detector = LocalRuntimeDetector()
    assert detector.recommend_image_provider() == "onnx"


def test_recommend_provider_returns_none_when_no_resources(monkeypatch):
    """recommend_image_provider() returns None when no local inference possible."""
    fake_torch = MagicMock()
    fake_torch.cuda.is_available.return_value = False
    monkeypatch.setattr("app.core.local_runtime.torch", fake_torch)
    monkeypatch.setattr("app.core.local_runtime._TORCH_AVAILABLE", True)
    monkeypatch.setattr("psutil.virtual_memory", lambda: MagicMock(total=2 * 1024**3))
    detector = LocalRuntimeDetector(min_ram_gb=8)
    assert detector.recommend_image_provider() is None


def test_runtime_info_serializable():
    """RuntimeInfo can be serialized to dict."""
    info = RuntimeInfo(
        device_type=DeviceType.GPU,
        vram_gb=8.0,
        ram_gb=16.0,
        gpu_name="NVIDIA RTX 3060",
    )
    d = info.to_dict()
    assert d["device_type"] == "gpu"
    assert d["vram_gb"] == 8.0
