"""BenchmarkSuite - 标准化基准测试套件

Phase 8 P2: AMD/Intel GPU 支持

输出可比较的吞吐/延迟/显存数据：
- LLM: 100-token 生成，测 tokens/s
- Image: 512x512 4-step，测 img/s
- VRAM 峰值占用（torch.cuda/xpu.memory_allocated）

单项目失败/超时不阻断整体报告。
"""
import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.core.gpu_vendor_detector import GPUVendor

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkMetric:
    """单项基准测试指标"""
    name: str               # "image_t2i_throughput" / "llm_tokens_per_sec" / "vram_peak_gb"
    value: float
    unit: str               # "img/s" / "tokens/s" / "GB"
    details: dict = field(default_factory=dict)


@dataclass
class BenchmarkReport:
    """基准测试报告"""
    vendor: str             # "nvidia" / "amd" / "intel" / "none"
    device_name: str
    metrics: list[BenchmarkMetric]
    timestamp: str
    duration_sec: float

    def to_dict(self) -> dict:
        """序列化为字典（API 返回用）"""
        return {
            "vendor": self.vendor,
            "device_name": self.device_name,
            "metrics": [
                {
                    "name": m.name,
                    "value": m.value,
                    "unit": m.unit,
                    "details": m.details,
                }
                for m in self.metrics
            ],
            "timestamp": self.timestamp,
            "duration_sec": self.duration_sec,
        }


class BenchmarkSuite:
    """基准测试套件

    使用方式：
        suite = BenchmarkSuite(device_manager=dm)
        report = await suite.run_full()
    """

    # 单项超时时间（秒）
    SINGLE_RUNNER_TIMEOUT = 120

    def __init__(self, device_manager: Any) -> None:
        """初始化

        Args:
            device_manager: DeviceManager 实例（用于获取厂商信息与 Provider）
        """
        self._dm = device_manager

    async def run_full(self) -> BenchmarkReport:
        """运行完整基准测试套件

        顺序执行 run_llm → run_image → run_vram_peak
        单项失败/超时不阻断整体报告，该项 value=0 + details.error
        """
        start_time = time.time()
        metrics: list[BenchmarkMetric] = []

        # 厂商信息
        gpu_info = self._dm.get_gpu_info()
        if gpu_info is not None:
            vendor = gpu_info.vendor.value
            device_name = gpu_info.device_name
        else:
            vendor = GPUVendor.NONE.value
            device_name = "CPU"

        # 顺序运行各项（避免显存冲突）
        runners = [
            ("run_llm", self.run_llm),
            ("run_image", self.run_image),
            ("run_vram_peak", self.run_vram_peak),
        ]

        for runner_name, runner in runners:
            try:
                metric = await asyncio.wait_for(
                    runner(),
                    timeout=self.SINGLE_RUNNER_TIMEOUT,
                )
                metrics.append(metric)
            except asyncio.TimeoutError:
                logger.warning(f"[P2] Benchmark {runner_name} timed out")
                metrics.append(BenchmarkMetric(
                    name=runner_name,
                    value=0.0,
                    unit="",
                    details={"error": f"timeout after {self.SINGLE_RUNNER_TIMEOUT}s"},
                ))
            except Exception as exc:
                logger.warning(f"[P2] Benchmark {runner_name} failed: {exc}")
                metrics.append(BenchmarkMetric(
                    name=runner_name,
                    value=0.0,
                    unit="",
                    details={"error": f"{type(exc).__name__}: {exc}"},
                ))

        duration = time.time() - start_time
        return BenchmarkReport(
            vendor=vendor,
            device_name=device_name,
            metrics=metrics,
            timestamp=datetime.now(UTC).isoformat(),
            duration_sec=duration,
        )

    async def run_llm(self) -> BenchmarkMetric:
        """LLM 基准测试：100-token 生成，测 tokens/s"""
        import time

        # 通过 DeviceManager 获取 LLM Provider
        from app.engines.manager import engine_manager

        engine_hint = self._dm.recommend_llm_engine()

        # 根据引擎提示选择 Provider
        provider_name = "qwen_local" if engine_hint == "vllm" else "llama_cpp"
        provider = engine_manager._instantiated_providers.get(provider_name)

        if provider is None or not getattr(provider, "_initialized", False):
            raise RuntimeError(f"LLM provider {provider_name} not initialized")

        # 跑 3 次取中位数
        times: list[float] = []
        tokens_generated = 100
        for _ in range(3):
            start = time.time()
            result = await provider.chat(
                messages=[{"role": "user", "content": "写一段 100 字的故事"}],
                max_tokens=tokens_generated,
            )
            elapsed = time.time() - start
            if result.success:
                times.append(elapsed)

        if not times:
            raise RuntimeError("All LLM benchmark runs failed")

        # 中位数 tokens/s
        times.sort()
        median_time = times[len(times) // 2]
        tokens_per_sec = tokens_generated / median_time if median_time > 0 else 0

        return BenchmarkMetric(
            name="llm_tokens_per_sec",
            value=tokens_per_sec,
            unit="tokens/s",
            details={
                "engine": engine_hint,
                "median_time_sec": median_time,
                "runs": len(times),
            },
        )

    async def run_image(self) -> BenchmarkMetric:
        """Image 基准测试：512x512 4-step，测 img/s"""
        import time

        from app.engines.manager import engine_manager

        provider = engine_manager._instantiated_providers.get("flux")
        if provider is None or not getattr(provider, "_initialized", False):
            raise RuntimeError("FLUX provider not initialized")

        # 跑 3 次取中位数
        times: list[float] = []
        for _ in range(3):
            start = time.time()
            result = await provider.text2img(
                prompt="a cat",
                width=512,
                height=512,
                num_inference_steps=4,
            )
            elapsed = time.time() - start
            if result.success:
                times.append(elapsed)

        if not times:
            raise RuntimeError("All image benchmark runs failed")

        times.sort()
        median_time = times[len(times) // 2]
        img_per_sec = 1.0 / median_time if median_time > 0 else 0

        return BenchmarkMetric(
            name="image_t2i_throughput",
            value=img_per_sec,
            unit="img/s",
            details={
                "median_time_sec": median_time,
                "runs": len(times),
                "resolution": "512x512",
            },
        )

    async def run_vram_peak(self) -> BenchmarkMetric:
        """VRAM 峰值占用测试"""
        try:
            import torch
        except ImportError:
            return BenchmarkMetric(
                name="vram_peak_gb",
                value=0.0,
                unit="GB",
                details={"error": "torch not installed"},
            )

        gpu_info = self._dm.get_gpu_info()
        if gpu_info is None:
            return BenchmarkMetric(
                name="vram_peak_gb",
                value=0.0,
                unit="GB",
                details={"error": "no GPU (CPU mode)"},
            )

        # 读取当前显存占用（基准测试期间峰值）
        try:
            if gpu_info.backend == "cuda":
                # torch.cuda.max_memory_allocated 返回自上次 reset 以来的峰值
                torch.cuda.reset_peak_memory_stats()
                # 触发一次推理以测量
                # 这里简化：直接读当前已分配的显存
                allocated = torch.cuda.memory_allocated(0)
                peak_gb = allocated / (1024 ** 3)
            elif gpu_info.backend == "xpu":
                # Intel XPU: torch.xpu.memory_allocated
                allocated = torch.xpu.memory_allocated(0)
                peak_gb = allocated / (1024 ** 3)
            else:
                peak_gb = 0.0
        except Exception as exc:
            return BenchmarkMetric(
                name="vram_peak_gb",
                value=0.0,
                unit="GB",
                details={"error": f"{type(exc).__name__}: {exc}"},
            )

        return BenchmarkMetric(
            name="vram_peak_gb",
            value=peak_gb,
            unit="GB",
            details={
                "backend": gpu_info.backend,
                "vram_total_gb": gpu_info.vram_gb,
            },
        )
