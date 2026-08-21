"""DeviceManager - 设备管理单例

Phase 8 P2: AMD/Intel GPU 支持

唯一设备入口，封装：
- GPU 厂商探测（委托给 GPUVendorDetector）
- 设备字符串选择（cuda:0 / xpu:0 / cpu）
- torch dtype 推荐（bfloat16 / float16 / float32）
- LLM 引擎推荐（vllm / llama_cpp）
- 基准测试入口（委托给 BenchmarkSuite）

所有本地 Provider 通过 DeviceManager 获取设备信息，不直接调用 torch.cuda/xpu。
"""
import asyncio
import logging
from typing import Any, Optional

import psutil

from app.core.gpu_vendor_detector import GPUInfo, GPUVendor, GPUVendorDetector
from app.core.local_runtime import DeviceType, RuntimeInfo

logger = logging.getLogger(__name__)


class DeviceManager:
    """设备管理单例 - 唯一设备入口

    使用 get_instance() 获取实例，构造函数不应直接调用。
    """

    _instance: Optional["DeviceManager"] = None

    def __init__(self) -> None:
        self._gpu_info: Optional[GPUInfo] = None
        self._runtime_info: Optional[RuntimeInfo] = None
        self._benchmark: Optional[Any] = None  # BenchmarkReport，延迟 import 避免循环
        self._benchmark_timestamp: float = 0.0
        self._lock: asyncio.Lock = asyncio.Lock()
        self._initialized: bool = False

    @classmethod
    def get_instance(cls) -> "DeviceManager":
        """获取单例（线程安全）"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def initialize(self) -> None:
        """初始化：探测 GPU + CPU/RAM，结果缓存

        幂等：重复调用不会重复探测。
        并发安全：使用 asyncio.Lock 串行化。
        失败安全：探测失败回退 CPU 模式，不抛异常。
        """
        async with self._lock:
            if self._initialized:
                return

            # 探测 GPU
            try:
                self._gpu_info = GPUVendorDetector().detect()
                if self._gpu_info is not None:
                    logger.info(
                        f"[P2] GPU detected: vendor={self._gpu_info.vendor.value}, "
                        f"name={self._gpu_info.device_name!r}, "
                        f"vram={self._gpu_info.vram_gb:.1f}GB, "
                        f"backend={self._gpu_info.backend}"
                    )
            except Exception as exc:
                logger.warning(f"[P2] GPU detection failed: {exc}, fallback to CPU")
                self._gpu_info = None

            # 探测 RAM（psutil 必装，从不失败）
            ram_bytes = psutil.virtual_memory().total
            ram_gb = ram_bytes / (1024 ** 3)

            # 构造 RuntimeInfo（与 P1 LocalRuntimeDetector 兼容）
            if self._gpu_info is not None:
                self._runtime_info = RuntimeInfo(
                    device_type=DeviceType.GPU,
                    vram_gb=self._gpu_info.vram_gb,
                    ram_gb=ram_gb,
                    gpu_name=self._gpu_info.device_name,
                )
            else:
                self._runtime_info = RuntimeInfo(
                    device_type=DeviceType.CPU,
                    vram_gb=0.0,
                    ram_gb=ram_gb,
                    gpu_name="",
                )
                logger.info(f"[P2] CPU mode: {ram_gb:.1f} GB RAM")

            self._initialized = True

    def detect_vendor(self) -> GPUVendor:
        """返回当前 GPU 厂商（未初始化时返回 NONE）"""
        if self._gpu_info is None:
            return GPUVendor.NONE
        return self._gpu_info.vendor

    def get_device_string(self, engine_type: str = "image") -> str:
        """返回 Provider 应使用的 device 字符串

        Args:
            engine_type: "image" / "video" / "llm" / "tts"

        Returns:
            "cuda:0" (NVIDIA/AMD) / "xpu:0" (Intel) / "cpu" (无 GPU)
        """
        if self._gpu_info is None:
            return "cpu"
        backend = self._gpu_info.backend
        if backend == "cuda":
            return "cuda:0"
        if backend == "xpu":
            return "xpu:0"
        return "cpu"

    def get_torch_dtype(self, engine_type: str = "image") -> Any:
        """返回推荐的 torch dtype

        策略：
        - NVIDIA + >=16GB VRAM → bfloat16
        - NVIDIA + <16GB VRAM → float16
        - AMD → float16（bfloat16 在 ROCm 支持不完整）
        - Intel → float16（bfloat16 在 XPU 支持不完整）
        - CPU → float32

        Returns:
            torch.dtype 或字符串（torch 未安装时返回字符串，便于测试）
        """
        try:
            import torch
            torch_available = True
        except ImportError:
            torch = None  # type: ignore
            torch_available = False

        dtype_str = self._get_dtype_string(engine_type)

        if not torch_available:
            return dtype_str

        dtype_map = {
            "bfloat16": torch.bfloat16,
            "float16": torch.float16,
            "float32": torch.float32,
        }
        return dtype_map[dtype_str]

    def _get_dtype_string(self, engine_type: str = "image") -> str:
        """内部：返回 dtype 字符串（便于测试，无 torch 依赖）"""
        if self._gpu_info is None:
            return "float32"

        vendor = self._gpu_info.vendor
        vram_gb = self._gpu_info.vram_gb

        if vendor == GPUVendor.NVIDIA:
            return "bfloat16" if vram_gb >= 16.0 else "float16"
        if vendor == GPUVendor.AMD:
            return "float16"
        if vendor == GPUVendor.INTEL:
            return "float16"
        return "float32"

    def recommend_llm_engine(self) -> str:
        """LLM 引擎推荐

        - NVIDIA/AMD → "vllm"（QwenLocalProvider）
        - Intel/CPU → "llama_cpp"（LlamaCppProvider）
        """
        if self._gpu_info is None:
            return "llama_cpp"
        vendor = self._gpu_info.vendor
        if vendor in (GPUVendor.NVIDIA, GPUVendor.AMD):
            return "vllm"
        return "llama_cpp"

    def get_gpu_info(self) -> Optional[GPUInfo]:
        """返回缓存的 GPUInfo"""
        return self._gpu_info

    def get_runtime_info(self) -> Optional[RuntimeInfo]:
        """返回缓存的 RuntimeInfo"""
        return self._runtime_info

    async def benchmark(self, force: bool = False) -> Any:
        """运行基准测试（委托给 BenchmarkSuite）

        Args:
            force: True 跳过缓存重新测试

        Returns:
            BenchmarkReport
        """
        async with self._lock:
            import time

            from app.core.config import settings

            cache_ttl = getattr(settings, "benchmark_cache_ttl", 3600)
            now = time.time()

            if not force and self._benchmark is not None:
                if now - self._benchmark_timestamp < cache_ttl:
                    return self._benchmark

            from app.core.benchmark_suite import BenchmarkSuite

            suite = BenchmarkSuite(device_manager=self)
            report = await suite.run_full()
            self._benchmark = report
            self._benchmark_timestamp = now
            return report
