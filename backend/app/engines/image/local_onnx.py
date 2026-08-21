"""本地图像生成 - ONNX Runtime INT8 (CPU only)

Task 15: Local AI Inference (Desktop)

使用 ONNX Runtime INT8 量化模型在 CPU 上推理。
速度较慢 (≤15s/1024x1024) 但通用且离线可用。

onnxruntime / optimum 是可选依赖（仅桌面 CPU 构建安装）。
"""
import io
import logging
from typing import Optional

from app.core.storage import storage
from app.engines.base import GenerationResult, ImageGenProvider
from app.engines.model_manager import model_manager

logger = logging.getLogger(__name__)


class LocalOnnxProvider(ImageGenProvider):
    """本地图像生成 Provider (CPU)

    使用 ONNX Runtime INT8 量化模型在 CPU 上推理。
    速度较慢 (≤15s/1024x1024) 但通用且离线可用。
    """

    name = "local-onnx"
    display_name = "Local ONNX Runtime (CPU)"

    def __init__(self, model_name: str = "sdxl-base-onnx") -> None:
        self.model_name = model_name
        self._session = None
        self._pipeline = None
        self._initialized = False

    async def initialize(self) -> None:
        self._initialized = True

    async def text2img(
        self,
        prompt: str,
        negative_prompt: str = "",
        width: int = 512,
        height: int = 512,
        seed: Optional[int] = None,
        model: Optional[str] = None,
        **kwargs,
    ) -> GenerationResult:
        """Generate image via ONNX Runtime."""
        # Lazy import — onnxruntime/optimum are optional desktop deps
        try:
            import numpy as np  # noqa: F401
            import onnxruntime as ort
            from optimum.onnxruntime import ORTStableDiffusionPipeline
        except ImportError as exc:
            return GenerationResult(
                success=False,
                data=b"",
                content_type="",
                metadata={"provider": self.name},
                error=f"onnxruntime/optimum not installed: {exc}",
            )

        # Resolve model path
        model_key = model or self.model_name
        model_path = model_manager.get_model_path(model_key)
        if model_path is None:
            return GenerationResult(
                success=False,
                data=b"",
                content_type="",
                metadata={"provider": self.name},
                error=f"Model {model_key} not downloaded",
            )

        # Load pipeline if not cached
        if self._pipeline is None:
            session_options = ort.SessionOptions()
            session_options.graph_optimization_level = (
                ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            )
            session_options.intra_op_num_threads = 4  # Limit threads for desktop
            self._pipeline = ORTStableDiffusionPipeline.from_pretrained(
                model_path,
                sess_options=session_options,
                provider="CPUExecutionProvider",
            )
            model_manager.cache_pipeline(model_key, self._pipeline)

        # Generate
        image = self._pipeline(
            prompt=prompt,
            num_inference_steps=kwargs.get("steps", 20),
            negative_prompt=negative_prompt or None,
        ).images[0]

        # Save to storage
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        url_path = storage.save(buf.getvalue(), extension="png", subdir="images")

        return GenerationResult(
            success=True,
            data=url_path,
            content_type="image/png",
            metadata={
                "provider": self.name,
                "model": model_key,
                "width": width,
                "height": height,
                "seed": seed,
                "device": "cpu",
                "is_local": True,
            },
        )

    async def health_check(self) -> bool:
        """Healthy when onnxruntime is importable."""
        try:
            import onnxruntime  # noqa: F401
            return True
        except ImportError:
            return False

    def get_info(self) -> dict:
        info = super().get_info()
        info["device"] = "cpu"
        info["model"] = self.model_name
        info["is_local"] = True
        info["available_models"] = ["sdxl-base-onnx", "sd1.5-onnx"]
        return info
