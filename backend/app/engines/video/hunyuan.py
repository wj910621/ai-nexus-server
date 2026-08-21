"""HunyuanVideo 本地视频生成 Provider (diffusers)

Task 17 (Phase 8 P1) — Spec Section 8.7

腾讯混元视频生成：
- 使用 diffusers HunyuanVideoPipeline
- 懒加载（首次 text2video 才加载）
- 模型常驻显存
- diffusers 是可选依赖
"""
import logging
import os
from typing import Optional

from app.engines.base import BaseEngine, GenerationResult

logger = logging.getLogger(__name__)

try:
    import torch
    from diffusers import HunyuanVideoPipeline
    _DIFFUSERS_AVAILABLE = True
except ImportError:
    torch = None  # type: ignore
    HunyuanVideoPipeline = None  # type: ignore
    _DIFFUSERS_AVAILABLE = False


class HunyuanProvider(BaseEngine):
    """腾讯混元视频生成 Provider (本地)"""

    name = "hunyuan"
    display_name = "腾讯混元 HunyuanVideo (本地)"
    capability = "text2video"
    is_local = True
    supported_models = ["tencent/HunyuanVideo"]

    DEFAULT_MODEL = "tencent/HunyuanVideo"

    def __init__(
        self,
        model_id: str = DEFAULT_MODEL,
        device: Optional[str] = None,
    ) -> None:
        self.model_id = model_id
        # P2: 通过 DeviceManager 获取设备（NVIDIA cuda:0 / AMD cuda:0 / Intel xpu:0 / cpu）
        from app.core.device_manager import DeviceManager
        dm = DeviceManager.get_instance()
        self.device = device or dm.get_device_string("video")
        self.dtype = dm.get_torch_dtype("video")
        self._pipe = None
        self._initialized = False

    async def initialize(self) -> None:
        if not _DIFFUSERS_AVAILABLE:
            logger.warning("diffusers 未安装，HunyuanProvider 不可用")
            return
        self._pipe = HunyuanVideoPipeline.from_pretrained(
            self.model_id,
            torch_dtype=torch.bfloat16,
        )
        if "cuda" in self.device and torch.cuda.is_available():
            self._pipe = self._pipe.to(self.device)
        self._initialized = True
        logger.info(f"HunyuanVideo loaded: {self.model_id}")

    async def text2video(
        self,
        prompt: str,
        duration: int = 5,
        fps: int = 24,
        resolution: str = "720p",
        seed: Optional[int] = None,
        output_path: str = "output.mp4",
        num_frames: int = 49,
        **kwargs,
    ) -> GenerationResult:
        if not self._initialized or self._pipe is None:
            return GenerationResult(
                success=False, data=b"", content_type="video/mp4",
                metadata={}, error="HunyuanProvider 未初始化（模型未加载）",
            )

        try:
            generator = None
            if seed is not None and torch is not None:
                generator = torch.Generator(device=self.device).manual_seed(seed)

            num_frames = max(num_frames, duration * fps)
            output = self._pipe(
                prompt=prompt,
                num_frames=num_frames,
                num_inference_steps=kwargs.get("num_inference_steps", 30),
                generator=generator,
            )

            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
            video_frames = output.frames[0]
            try:
                import imageio
                imageio.mimsave(output_path, video_frames, fps=fps)
            except ImportError:
                for i, frame in enumerate(video_frames):
                    frame.save(f"{output_path}_{i:04d}.png")

            with open(output_path, "rb") as f:
                video_bytes = f.read()

            return GenerationResult(
                success=True, data=video_bytes, content_type="video/mp4",
                metadata={
                    "provider": self.name,
                    "model": self.model_id,
                    "duration": duration,
                    "fps": fps,
                    "num_frames": num_frames,
                    "output_path": output_path,
                },
            )
        except Exception as exc:
            return GenerationResult(
                success=False, data=b"", content_type="video/mp4",
                metadata={}, error=f"{type(exc).__name__}: {exc}",
            )

    async def health_check(self) -> bool:
        try:
            if not self._initialized:
                await self.initialize()
            result = await self.text2video(prompt="hi", duration=1, num_frames=8)
            return result.success
        except Exception:
            return False

    def get_info(self) -> dict:
        info = super().get_info()
        info["model_id"] = self.model_id
        info["diffusers_available"] = _DIFFUSERS_AVAILABLE
        return info


# 模块级注册 - 导入时自动触发
try:
    from app.engines.registry import provider_registry
    provider_registry.register("video", "hunyuan", HunyuanProvider)
except Exception:
    pass
