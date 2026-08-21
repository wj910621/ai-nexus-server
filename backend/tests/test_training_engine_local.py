"""Tests for LocalTrainingEngine (P3 Task 6)."""
from unittest.mock import MagicMock, patch

import pytest


def test_local_engine_check_available_fails_closed_until_implemented():
    """即使硬件满足，也不能把占位训练循环暴露为可用能力"""
    from app.core.device_manager import DeviceManager
    from app.core.gpu_vendor_detector import GPUInfo, GPUVendor
    from app.engines.training.local import LocalTrainingEngine

    # 重置单例
    DeviceManager._instance = None
    fake_dm = MagicMock()
    fake_dm.get_gpu_info.return_value = GPUInfo(
        vendor=GPUVendor.NVIDIA,
        device_name="NVIDIA RTX 3060",
        vram_gb=12.0,
        backend="cuda",
    )
    DeviceManager._instance = fake_dm

    eng = LocalTrainingEngine()
    with patch("app.engines.training.local._check_peft_installed", return_value=True):
        ok, reason = eng.check_available()
    assert ok is False
    assert "尚未完成生产实现" in reason


def test_local_engine_check_available_vram_insufficient():
    """VRAM<8GB → 不可用"""
    from app.core.device_manager import DeviceManager
    from app.core.gpu_vendor_detector import GPUInfo, GPUVendor
    from app.engines.training.local import LocalTrainingEngine

    DeviceManager._instance = None
    fake_dm = MagicMock()
    fake_dm.get_gpu_info.return_value = GPUInfo(
        vendor=GPUVendor.NVIDIA,
        device_name="NVIDIA GTX 1050",
        vram_gb=4.0,
        backend="cuda",
    )
    DeviceManager._instance = fake_dm

    eng = LocalTrainingEngine()
    with patch("app.engines.training.local._check_peft_installed", return_value=True):
        ok, reason = eng.check_available()
    assert ok is False
    assert "VRAM" in reason


def test_local_engine_check_available_no_gpu():
    """无 GPU（vram_gb=0）→ 不可用"""
    from app.core.device_manager import DeviceManager
    from app.core.gpu_vendor_detector import GPUInfo, GPUVendor
    from app.engines.training.local import LocalTrainingEngine

    DeviceManager._instance = None
    fake_dm = MagicMock()
    fake_dm.get_gpu_info.return_value = GPUInfo(
        vendor=GPUVendor.NONE,
        device_name="",
        vram_gb=0.0,
        backend="",
    )
    DeviceManager._instance = fake_dm

    eng = LocalTrainingEngine()
    with patch("app.engines.training.local._check_peft_installed", return_value=True):
        ok, reason = eng.check_available()
    assert ok is False


def test_local_engine_check_available_peft_missing():
    """peft 未安装 → 不可用"""
    from app.core.device_manager import DeviceManager
    from app.core.gpu_vendor_detector import GPUInfo, GPUVendor
    from app.engines.training.local import LocalTrainingEngine

    DeviceManager._instance = None
    fake_dm = MagicMock()
    fake_dm.get_gpu_info.return_value = GPUInfo(
        vendor=GPUVendor.NVIDIA,
        device_name="NVIDIA RTX 3060",
        vram_gb=12.0,
        backend="cuda",
    )
    DeviceManager._instance = fake_dm

    eng = LocalTrainingEngine()
    with patch("app.engines.training.local._check_peft_installed", return_value=False):
        ok, reason = eng.check_available()
    assert ok is False
    assert "peft" in reason.lower()


@pytest.mark.asyncio
async def test_local_engine_train_fails_closed(tmp_path):
    """本地训练不得生成空或伪造 adapter"""
    from app.engines.training.base import TrainingParams
    from app.engines.training.local import LocalTrainingEngine

    dataset_dir = tmp_path / "dataset"
    dataset_dir.mkdir()
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    eng = LocalTrainingEngine()
    params = TrainingParams.from_preset("quick", trigger_word="zkq")

    async def cb(p, m):
        pass

    with pytest.raises(RuntimeError, match="尚未完成生产实现"):
        await eng.train(
            dataset_path=str(dataset_dir),
            output_dir=str(output_dir),
            params=params,
            progress_callback=cb,
        )
