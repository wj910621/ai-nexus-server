"""FLUX.1-dev 本地图像生成 Provider (diffusers)

Task 11 (Phase 8 P1) — Spec Section 8.4

特性：
- 使用 HuggingFace diffusers FluxPipeline
- 4-bit 量化（bitsandbytes）以适配 12GB VRAM
- 懒加载模型（首次 text2img 才加载）
- 模型常驻显存（initialize 后不释放）
- torch 是可选依赖，未安装时模块仍可导入但 initialize 失败
"""
import logging
from io import BytesIO
from typing import Optional

from app.engines.base import GenerationResult, ImageGenProvider

logger = logging.getLogger(__name__)

# torch / diffusers / bitsandbytes 是可选依赖
try:
    import torch
    from diffusers import BitsAndBytesConfig, FluxPipeline
    _DIFFUSERS_AVAILABLE = True
except ImportError:
    torch = None  # type: ignore
    FluxPipeline = None  # type: ignore
    BitsAndBytesConfig = None  # type: ignore
    _DIFFUSERS_AVAILABLE = False


class FluxProvider(ImageGenProvider):
    """FLUX.1-dev 本地图像生成 Provider"""

    name = "flux"
    display_name = "FLUX.1-dev (本地)"
    capability = "text2img"
    is_local = True
    supported_models = ["black-forest-labs/FLUX.1-dev"]

    def __init__(
        self,
        model_id: str = "black-forest-labs/FLUX.1-dev",
        device: Optional[str] = None,
        use_4bit: bool = True,
    ) -> None:
        self.model_id = model_id
        # P2: 通过 DeviceManager 获取设备（NVIDIA cuda:0 / AMD cuda:0 / Intel xpu:0 / cpu）
        from app.core.device_manager import DeviceManager
        dm = DeviceManager.get_instance()
        self.device = device or dm.get_device_string("image")
        self.dtype = dm.get_torch_dtype("image")
        self.use_4bit = use_4bit
        self._pipe = None
        self._initialized = False

    async def initialize(self) -> None:
        """加载 FLUX 模型到显存（4-bit 量化）"""
        if not _DIFFUSERS_AVAILABLE:
            logger.warning("diffusers 未安装，FluxProvider 不可用")
            return

        # P2: 从 self.dtype 获取（DeviceManager 已计算），而非直接 torch.bfloat16
        dtype = self.dtype
        if dtype is None and torch is not None:
            dtype = torch.bfloat16
        kwargs = {
            "torch_dtype": dtype,
        }
        if self.use_4bit and BitsAndBytesConfig is not None:
            # 4-bit 量化配置
            kwargs["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=dtype,
                bnb_4bit_use_double_quant=True,
                bnb_4bit_quant_type="nf4",
            )

        self._pipe = FluxPipeline.from_pretrained(
            self.model_id,
            **kwargs,
        )
        if "cuda" in self.device and torch is not None and torch.cuda.is_available():
            self._pipe = self._pipe.to(self.device)
        self._initialized = True
        logger.info(f"FLUX model loaded: {self.model_id} (device={self.device}, 4bit={self.use_4bit})")

    async def text2img(
        self,
        prompt: str,
        negative_prompt: str = "",
        width: int = 1024,
        height: int = 1024,
        seed: Optional[int] = None,
        num_inference_steps: int = 28,
        guidance_scale: float = 3.5,
        **kwargs,
    ) -> GenerationResult:
        """文生图"""
        if not self._initialized or self._pipe is None:
            return GenerationResult(
                success=False, data=b"", content_type="image/png",
                metadata={}, error="FluxProvider 未初始化（模型未加载）",
            )

        try:
            generator = None
            if seed is not None and torch is not None:
                generator = torch.Generator(device=self.device).manual_seed(seed)

            output = self._pipe(
                prompt=prompt,
                width=width,
                height=height,
                num_inference_steps=num_inference_steps,
                guidance_scale=guidance_scale,
                generator=generator,
            )
            image = output.images[0]

            # 转 PNG bytes
            # TDD fix: 直接使用 BytesIO（而非 io.BytesIO）以便测试可 patch 模块级属性
            buf = BytesIO()
            image.save(buf, format="PNG")
            image_bytes = buf.getvalue()

            return GenerationResult(
                success=True, data=image_bytes, content_type="image/png",
                metadata={
                    "provider": self.name,
                    "model": self.model_id,
                    "seed": seed,
                    "steps": num_inference_steps,
                },
            )
        except Exception as exc:
            return GenerationResult(
                success=False, data=b"", content_type="image/png",
                metadata={}, error=f"{type(exc).__name__}: {exc}",
            )

    async def health_check(self) -> bool:
        try:
            if not self._initialized:
                await self.initialize()
            result = await self.text2img(prompt="hi", width=256, height=256, num_inference_steps=4)
            return result.success
        except Exception:
            return False

    def get_info(self) -> dict:
        info = super().get_info()
        info["model_id"] = self.model_id
        info["device"] = self.device
        info["use_4bit"] = self.use_4bit
        info["diffusers_available"] = _DIFFUSERS_AVAILABLE
        return info


# 模块级注册 - 导入时自动触发
try:
    from app.engines.registry import provider_registry
    provider_registry.register("image", "flux", FluxProvider)
except Exception:
    pass
