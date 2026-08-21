"""GPU 厂商识别 - NVIDIA/AMD/Intel 三大厂商探测

Phase 8 P2: AMD/Intel GPU 支持

探测顺序：
1. NVIDIA CUDA  (torch.cuda.is_available() + name 含 "NVIDIA")
2. AMD ROCm     (torch.cuda.is_available() + name 含 "AMD"/"Radeon"/"gfx")
3. Intel XPU    (torch.xpu.is_available())
4. 都没有 → None

torch 是可选依赖（仅桌面 GPU/CPU 推理构建中安装）。
"""
import enum
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# torch 是可选依赖
try:
    import torch
    _TORCH_AVAILABLE = True
except ImportError:
    torch = None  # type: ignore
    _TORCH_AVAILABLE = False


class GPUVendor(str, enum.Enum):
    """GPU 厂商枚举"""
    NVIDIA = "nvidia"
    AMD = "amd"
    INTEL = "intel"
    NONE = "none"


@dataclass
class GPUInfo:
    """GPU 信息"""
    vendor: GPUVendor
    device_name: str           # "NVIDIA GeForce RTX 4090" / "AMD Radeon RX 7900 XTX" / "Intel Arc A770"
    vram_gb: float
    device_index: int = 0
    backend: str = ""          # "cuda" (NVIDIA/AMD) / "xpu" (Intel)


class GPUVendorDetector:
    """GPU 厂商探测器 - 纯探测，无副作用

    识别规则：
    - name 以 "NVIDIA" 开头 → NVIDIA
    - name 以 "AMD" 开头 / 包含 "Radeon" / 以 "gfx" 开头（ROCm 命名） → AMD
    - name 以 "Intel" 开头 / 包含 "Arc" → Intel（走 XPU 路径）
    - 其他 → None（回退 CPU）
    """

    def detect(self) -> Optional[GPUInfo]:
        """探测 GPU，返回 GPUInfo 或 None

        探测失败不抛异常，最差返回 None（由调用方回退 CPU）。
        """
        if not _TORCH_AVAILABLE or torch is None:
            return None

        # 1. 尝试 CUDA（NVIDIA 或 AMD ROCm，两者都走 cuda API）
        try:
            if torch.cuda.is_available():
                return self._detect_via_cuda()
        except Exception as exc:
            logger.warning(f"[P2] CUDA detection failed: {exc}")

        # 2. 尝试 Intel XPU
        try:
            if hasattr(torch, "xpu") and torch.xpu.is_available():
                return self._detect_via_xpu()
        except Exception as exc:
            logger.warning(f"[P2] XPU detection failed: {exc}")

        return None

    def _detect_via_cuda(self) -> Optional[GPUInfo]:
        """通过 torch.cuda API 探测（NVIDIA 或 AMD ROCm）"""
        if torch is None:
            return None
        device_count = torch.cuda.device_count()
        if device_count == 0:
            return None

        name = torch.cuda.get_device_name(0)
        vram_bytes = torch.cuda.get_device_properties(0).total_memory
        vram_gb = vram_bytes / (1024 ** 3)

        vendor = self._identify_vendor_by_name(name)
        if vendor == GPUVendor.NONE:
            logger.warning(f"[P2] Unknown GPU vendor, name={name!r}, fallback to None")
            return None

        return GPUInfo(
            vendor=vendor,
            device_name=name,
            vram_gb=vram_gb,
            device_index=0,
            backend="cuda",  # NVIDIA 和 AMD ROCm 都走 cuda API
        )

    def _detect_via_xpu(self) -> Optional[GPUInfo]:
        """通过 torch.xpu API 探测 Intel"""
        if torch is None:
            return None
        device_count = torch.xpu.device_count()
        if device_count == 0:
            return None

        name = torch.xpu.get_device_name(0)
        vram_bytes = torch.xpu.get_device_properties(0).total_memory
        vram_gb = vram_bytes / (1024 ** 3)

        # Intel XPU 路径直接认定为 Intel 厂商
        return GPUInfo(
            vendor=GPUVendor.INTEL,
            device_name=name,
            vram_gb=vram_gb,
            device_index=0,
            backend="xpu",
        )

    @staticmethod
    def _identify_vendor_by_name(name: str) -> GPUVendor:
        """根据 GPU 名称识别厂商"""
        name_lower = name.lower()
        if name_lower.startswith("nvidia"):
            return GPUVendor.NVIDIA
        if name_lower.startswith("amd") or "radeon" in name_lower or name_lower.startswith("gfx"):
            return GPUVendor.AMD
        if name_lower.startswith("intel") or "arc" in name_lower:
            return GPUVendor.INTEL
        return GPUVendor.NONE
