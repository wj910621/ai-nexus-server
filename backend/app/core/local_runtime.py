"""本地运行时检测 - 自动识别 GPU/CPU 资源

Task 15: Local AI Inference (Desktop)
Phase 8 P2: 委托给 DeviceManager，支持 NVIDIA/AMD/Intel

优先级:
1. GPU (NVIDIA CUDA / AMD ROCm / Intel XPU) — 最快
2. CPU (ONNX Runtime INT8) — 较慢但通用
3. None — 退回到远程 API

torch 是可选依赖（仅在桌面 GPU/CPU 推理构建中安装）。
psutil 是必装依赖（在主 requirements 中）。
"""
import enum
import logging
from dataclasses import asdict, dataclass
from typing import Optional

import psutil

logger = logging.getLogger(__name__)

# torch 是可选依赖（仅桌面 GPU/CPU 推理构建中安装）
try:
    import torch
    _TORCH_AVAILABLE = True
except ImportError:
    torch = None  # type: ignore
    _TORCH_AVAILABLE = False


class DeviceType(str, enum.Enum):
    GPU = "gpu"
    CPU = "cpu"
    NONE = "none"


@dataclass
class RuntimeInfo:
    """运行时检测结果"""
    device_type: DeviceType
    vram_gb: float = 0.0
    ram_gb: float = 0.0
    gpu_name: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["device_type"] = self.device_type.value
        return d


class LocalRuntimeDetector:
    """检测本地 AI 推理能力

    P2: 委托给 DeviceManager 进行 GPU 探测，对外 API 完全兼容。

    优先级:
    1. GPU (NVIDIA/AMD/Intel) — 最快
    2. CPU (ONNX Runtime INT8) — 较慢但通用
    3. None — 退回到远程 API
    """

    def __init__(
        self,
        min_vram_gb: int = 6,
        min_ram_gb: int = 8,
    ) -> None:
        self.min_vram_gb = min_vram_gb
        self.min_ram_gb = min_ram_gb

    def detect(self) -> RuntimeInfo:
        """检测本地运行时能力（委托给 DeviceManager）"""
        # P2: 优先从 DeviceManager 获取 GPU 信息
        try:
            from app.core.device_manager import DeviceManager
            dm = DeviceManager.get_instance()
            gpu_info = dm.get_gpu_info()
            if gpu_info is not None and gpu_info.vram_gb >= self.min_vram_gb:
                logger.info(
                    f"[P2] GPU detected via DeviceManager: "
                    f"{gpu_info.device_name} ({gpu_info.vram_gb:.1f} GB VRAM)"
                )
                return RuntimeInfo(
                    device_type=DeviceType.GPU,
                    vram_gb=gpu_info.vram_gb,
                    gpu_name=gpu_info.device_name,
                )
        except ImportError:
            pass  # DeviceManager 未就绪（早期启动），回退到原始探测
        except Exception as exc:
            logger.warning(f"[P2] DeviceManager probe failed: {exc}, fallback to legacy detection")

        # 回退：原始 torch.cuda 探测（向后兼容）
        if _TORCH_AVAILABLE and torch is not None and torch.cuda.is_available():
            try:
                props = torch.cuda.get_device_properties(0)
                vram_gb = props.total_memory / (1024**3)
                gpu_name = props.name
                if vram_gb >= self.min_vram_gb:
                    logger.info(f"GPU detected: {gpu_name} ({vram_gb:.1f} GB VRAM)")
                    return RuntimeInfo(
                        device_type=DeviceType.GPU,
                        vram_gb=vram_gb,
                        gpu_name=gpu_name,
                    )
                logger.warning(
                    f"GPU VRAM insufficient: {vram_gb:.1f} GB < {self.min_vram_gb} GB"
                )
            except Exception as exc:
                logger.warning(f"GPU detection failed: {exc}")

        # 回退到 CPU
        ram_gb = psutil.virtual_memory().total / (1024**3)
        if ram_gb >= self.min_ram_gb:
            logger.info(f"CPU mode: {ram_gb:.1f} GB RAM")
            return RuntimeInfo(device_type=DeviceType.CPU, ram_gb=ram_gb)

        # 资源不足
        logger.warning("Insufficient resources for local inference")
        return RuntimeInfo(device_type=DeviceType.NONE, ram_gb=ram_gb)

    def detect_vendor(self):
        """P2: 透传 DeviceManager 的厂商探测"""
        try:
            from app.core.device_manager import DeviceManager
            return DeviceManager.get_instance().detect_vendor()
        except ImportError:
            from app.core.gpu_vendor_detector import GPUVendor
            return GPUVendor.NONE

    def recommend_image_provider(self) -> Optional[str]:
        """根据检测结果推荐图像生成 provider"""
        info = self.detect()
        if info.device_type == DeviceType.GPU:
            return "diffusers"
        if info.device_type == DeviceType.CPU:
            return "onnx"
        return None

    def recommend_llm_provider(self) -> Optional[str]:
        """推荐 LLM provider"""
        info = self.detect()
        if info.device_type in (DeviceType.GPU, DeviceType.CPU):
            return "llama_cpp"
        return None

    def recommend_tts_provider(self) -> Optional[str]:
        """推荐 TTS provider"""
        info = self.detect()
        if info.device_type in (DeviceType.GPU, DeviceType.CPU):
            return "piper"
        return None


# 模块级单例
local_runtime_detector = LocalRuntimeDetector()
