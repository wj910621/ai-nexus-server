"""Tests for BenchmarkSuite — LLM/Image/VRAM 基准测试 (Phase 8 P2)"""
import asyncio
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.benchmark_suite import (
    BenchmarkMetric,
    BenchmarkReport,
    BenchmarkSuite,
)


def test_benchmark_metric_dataclass():
    """BenchmarkMetric dataclass 字段"""
    m = BenchmarkMetric(
        name="llm_tokens_per_sec",
        value=42.5,
        unit="tokens/s",
        details={"model": "qwen_local"},
    )
    assert m.name == "llm_tokens_per_sec"
    assert m.value == 42.5
    assert m.unit == "tokens/s"
    assert m.details == {"model": "qwen_local"}


def test_benchmark_report_dataclass():
    """BenchmarkReport dataclass 字段"""
    metrics = [BenchmarkMetric(name="m1", value=1.0, unit="u")]
    r = BenchmarkReport(
        vendor="nvidia",
        device_name="NVIDIA RTX 4090",
        metrics=metrics,
        timestamp="2026-07-20T10:00:00",
        duration_sec=10.5,
    )
    assert r.vendor == "nvidia"
    assert r.device_name == "NVIDIA RTX 4090"
    assert len(r.metrics) == 1
    assert r.duration_sec == 10.5


def test_benchmark_report_to_dict():
    """to_dict() 返回可序列化字典"""
    metrics = [
        BenchmarkMetric(name="m1", value=1.0, unit="u"),
        BenchmarkMetric(name="m2", value=2.0, unit="v", details={"k": "v"}),
    ]
    r = BenchmarkReport(
        vendor="intel",
        device_name="Intel Arc A770",
        metrics=metrics,
        timestamp="2026-07-20T10:00:00",
        duration_sec=5.0,
    )
    d = r.to_dict()
    assert d["vendor"] == "intel"
    assert d["device_name"] == "Intel Arc A770"
    assert len(d["metrics"]) == 2
    assert d["metrics"][0]["name"] == "m1"


@pytest.fixture
def mock_device_manager():
    """Mock DeviceManager"""
    from app.core.device_manager import DeviceManager
    from app.core.gpu_vendor_detector import GPUVendor, GPUInfo

    DeviceManager._instance = None
    dm = DeviceManager.get_instance()
    dm._gpu_info = GPUInfo(
        vendor=GPUVendor.NVIDIA,
        device_name="NVIDIA RTX 4090",
        vram_gb=24.0,
        device_index=0,
        backend="cuda",
    )
    dm._initialized = True
    yield dm
    DeviceManager._instance = None


@pytest.mark.asyncio
async def test_run_full_returns_report(mock_device_manager):
    """完整基准测试返回 BenchmarkReport"""
    suite = BenchmarkSuite(device_manager=mock_device_manager)

    # Mock 各 runner
    with patch.object(suite, "run_llm", new_callable=AsyncMock) as mock_llm:
        with patch.object(suite, "run_image", new_callable=AsyncMock) as mock_image:
            with patch.object(suite, "run_vram_peak", new_callable=AsyncMock) as mock_vram:
                mock_llm.return_value = BenchmarkMetric(
                    name="llm_tokens_per_sec", value=100.0, unit="tokens/s"
                )
                mock_image.return_value = BenchmarkMetric(
                    name="image_t2i_throughput", value=2.0, unit="img/s"
                )
                mock_vram.return_value = BenchmarkMetric(
                    name="vram_peak_gb", value=12.5, unit="GB"
                )

                report = await suite.run_full()

    assert isinstance(report, BenchmarkReport)
    assert report.vendor == "nvidia"
    assert report.device_name == "NVIDIA RTX 4090"
    assert len(report.metrics) == 3
    assert any(m.name == "llm_tokens_per_sec" for m in report.metrics)
    assert any(m.name == "image_t2i_throughput" for m in report.metrics)
    assert any(m.name == "vram_peak_gb" for m in report.metrics)


@pytest.mark.asyncio
async def test_metric_failure_isolated(mock_device_manager):
    """单项失败不影响其他项"""
    suite = BenchmarkSuite(device_manager=mock_device_manager)

    with patch.object(suite, "run_llm", new_callable=AsyncMock) as mock_llm:
        with patch.object(suite, "run_image", new_callable=AsyncMock) as mock_image:
            with patch.object(suite, "run_vram_peak", new_callable=AsyncMock) as mock_vram:
                mock_llm.return_value = BenchmarkMetric(
                    name="llm_tokens_per_sec", value=100.0, unit="tokens/s"
                )
                # Image 抛异常
                mock_image.side_effect = RuntimeError("diffusers not installed")
                mock_vram.return_value = BenchmarkMetric(
                    name="vram_peak_gb", value=12.5, unit="GB"
                )

                report = await suite.run_full()

    # 应有 3 项 metric，其中 image 项 value=0 + error
    assert len(report.metrics) == 3
    image_metric = next(m for m in report.metrics if m.name == "run_image")
    assert image_metric.value == 0
    assert "error" in image_metric.details
    assert "diffusers" in image_metric.details["error"]

    # LLM 与 VRAM 项正常
    llm_metric = next(m for m in report.metrics if m.name == "llm_tokens_per_sec")
    assert llm_metric.value == 100.0


@pytest.mark.asyncio
async def test_timeout_protection(mock_device_manager):
    """超时保护：单项目 >120s 应超时"""
    suite = BenchmarkSuite(device_manager=mock_device_manager)

    async def slow_llm():
        await asyncio.sleep(200)
        return BenchmarkMetric(name="llm_tokens_per_sec", value=100.0, unit="tokens/s")

    with patch.object(suite, "run_llm", side_effect=slow_llm):
        with patch.object(suite, "run_image", new_callable=AsyncMock) as mock_image:
            with patch.object(suite, "run_vram_peak", new_callable=AsyncMock) as mock_vram:
                mock_image.return_value = BenchmarkMetric(
                    name="image_t2i_throughput", value=2.0, unit="img/s"
                )
                mock_vram.return_value = BenchmarkMetric(
                    name="vram_peak_gb", value=12.5, unit="GB"
                )

                # 将超时时间缩短为 0.1s 加速测试
                import app.core.benchmark_suite as bs_module
                original_wait_for = asyncio.wait_for

                async def fast_wait_for(coro, timeout):
                    return await original_wait_for(coro, 0.1)

                with patch("app.core.benchmark_suite.asyncio.wait_for", side_effect=fast_wait_for):
                    report = await suite.run_full()

    # LLM 项应超时
    llm_metric = next(m for m in report.metrics if m.name == "run_llm")
    assert llm_metric.value == 0
    assert "timeout" in llm_metric.details.get("error", "").lower()
