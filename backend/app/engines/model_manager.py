"""模型管理器 - HuggingFace 下载 / 注册表 / LoRA 加载

Task 15: Local AI Inference (Desktop)

职责:
1. 注册可用模型 (从 config 或 DB)
2. 下载模型 (HuggingFace snapshot_download)
3. 加载模型 (lazy, cached in memory)
4. 加载 LoRA 适配器
5. 运行时切换活跃模型

huggingface_hub 是可选依赖（仅桌面构建安装）。
"""
import enum
import logging
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


class ModelState(str, enum.Enum):
    NOT_DOWNLOADED = "not_downloaded"
    DOWNLOADING = "downloading"
    READY = "ready"
    ERROR = "error"


@dataclass
class ModelInfo:
    """模型元信息"""
    name: str
    type: str  # image|llm|tts|character
    size_mb: int
    repo_id: str = ""
    state: ModelState = ModelState.NOT_DOWNLOADED
    local_path: str = ""
    progress_percent: float = 0.0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["state"] = self.state.value
        return d


# huggingface_hub 是可选依赖（仅桌面构建安装）
try:
    from huggingface_hub import snapshot_download
    _HF_AVAILABLE = True
except ImportError:
    snapshot_download = None  # type: ignore
    _HF_AVAILABLE = False


class ModelManager:
    """模型管理器

    职责:
    1. 注册可用模型 (从 config 或 DB)
    2. 下载模型 (HuggingFace snapshot_download)
    3. 加载模型 (lazy, cached in memory)
    4. 加载 LoRA 适配器
    5. 运行时切换活跃模型
    """

    def __init__(self, model_dir: Optional[str] = None) -> None:
        self.model_dir = Path(
            model_dir
            or settings.local_model_dir
            or os.path.expanduser("~/.comicstudio/models")
        )
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self._registry: dict[str, ModelInfo] = {}
        self._pipelines: dict[str, object] = {}  # Cached loaded pipelines
        self._init_default_registry()

    def _init_default_registry(self) -> None:
        """Populate registry with default models from config."""
        defaults = [
            ModelInfo(
                name="sdxl-base",
                type="image",
                size_mb=6500,
                repo_id="stabilityai/stable-diffusion-xl-base-1.0",
            ),
            ModelInfo(
                name="qwen2.5-7b",
                type="llm",
                size_mb=4500,
                repo_id="Qwen/Qwen2.5-7B-Instruct-Q4_K_M",
            ),
            ModelInfo(
                name="piper-en-lessac",
                type="tts",
                size_mb=60,
                repo_id="rhasspy/piper-voices/v1/en/en_US/lessac/medium",
            ),
        ]
        for m in defaults:
            self._registry[m.name] = m

    async def download(
        self,
        name: str,
        repo_id: Optional[str] = None,
    ) -> ModelInfo:
        """Download a model from HuggingFace."""
        if name not in self._registry and repo_id is None:
            raise ValueError(f"Unknown model: {name}")
        info = self._registry.get(name) or ModelInfo(
            name=name, type="image", size_mb=0, repo_id=repo_id or ""
        )
        # Update repo_id if explicitly provided
        if repo_id:
            info.repo_id = repo_id
        info.state = ModelState.DOWNLOADING
        info.progress_percent = 0.0
        self._registry[name] = info

        if snapshot_download is None:
            raise RuntimeError("huggingface_hub not installed; cannot download models")

        try:
            local_path = snapshot_download(
                repo_id=info.repo_id,
                local_dir=str(self.model_dir / name),
                local_dir_use_symlinks=False,
            )
            info.local_path = str(local_path)
            info.state = ModelState.READY
            info.progress_percent = 100.0
            logger.info(f"Model {name} downloaded to {local_path}")
        except Exception as exc:
            info.state = ModelState.ERROR
            logger.error(f"Failed to download {name}: {exc}")
            raise
        return info

    def list_models(self, model_type: Optional[str] = None) -> list[ModelInfo]:
        """List all registered models."""
        if model_type:
            return [m for m in self._registry.values() if m.type == model_type]
        return list(self._registry.values())

    async def delete(self, name: str) -> None:
        """Delete a model's local files and remove from registry."""
        info = self._registry.get(name)
        if info is None:
            return
        if info.local_path:
            import shutil
            shutil.rmtree(info.local_path, ignore_errors=True)
        # Unload pipeline if cached
        self._pipelines.pop(name, None)
        del self._registry[name]

    def get_model_path(self, name: str) -> Optional[str]:
        """Get local path for a READY model, None otherwise."""
        info = self._registry.get(name)
        if info is None or info.state != ModelState.READY:
            return None
        return info.local_path

    async def _load_pipeline(self, name: str) -> object:
        """Lazy-load a diffusers pipeline (cached).

        Implementation depends on provider type; providers register their
        loader via ``register_pipeline_loader`` or call ``cache_pipeline``.
        Default raises NotImplementedError for unknown models.
        """
        if name in self._pipelines:
            return self._pipelines[name]
        raise NotImplementedError(
            f"No pipeline loader registered for model: {name}"
        )

    def cache_pipeline(self, name: str, pipeline: object) -> None:
        """Cache a loaded pipeline for later reuse (called by providers)."""
        self._pipelines[name] = pipeline

    async def load_lora(
        self,
        base_model: str,
        lora_path: str,
        weight: float = 1.0,
    ) -> str:
        """Attach LoRA weights to a loaded base model."""
        pipeline = await self._load_pipeline(base_model)
        if hasattr(pipeline, "load_lora_weights"):
            pipeline.load_lora_weights(lora_path, weight=weight)
            logger.info(
                f"LoRA {lora_path} attached to {base_model} (weight={weight})"
            )
        return lora_path


# 模块级单例
model_manager = ModelManager()
