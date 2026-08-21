"""bge-m3 Embedding 服务

P1: 语义缓存配套

- 懒加载（首次调用时加载，避免阻塞启动）
- 持久化缓存到 data/models/bge-m3/
- normalize_embeddings=True（cosine = 内积，更快）
- CPU 推理 ~20ms/请求，无需 GPU
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# sentence_transformers 是可选依赖（仅启用语义缓存时安装）
try:
    from sentence_transformers import SentenceTransformer
    _ST_AVAILABLE = True
except ImportError:
    SentenceTransformer = None  # type: ignore
    _ST_AVAILABLE = False


class EmbeddingService:
    """bge-m3 Embedding 服务

    懒加载模型（首次调用时加载），支持批量编码。
    模型大小 ~2.3GB，首次启动时从 HuggingFace 下载。
    """

    MODEL_NAME = "BAAI/bge-m3"
    EMBEDDING_DIM = 1024
    MAX_SEQ_LENGTH = 8192  # tokens

    def __init__(self, model_cache_dir: str = "data/models/bge-m3"):
        self._model_cache_dir = model_cache_dir
        self._model: Optional["SentenceTransformer"] = None

    async def initialize(self) -> None:
        """懒加载模型（在首次 lookup/store 时调用）"""
        if self._model is not None:
            return
        if SentenceTransformer is None:
            raise RuntimeError(
                "sentence-transformers 未安装，请运行: pip install sentence-transformers"
            )
        logger.info(f"Loading bge-m3 model from {self._model_cache_dir}...")
        self._model = SentenceTransformer(
            self.MODEL_NAME,
            cache_folder=self._model_cache_dir,
        )
        logger.info("bge-m3 model loaded")

    async def encode(self, text: str) -> list[float]:
        """编码单个文本 → 1024 维向量

        Args:
            text: 输入文本

        Returns:
            1024 维归一化向量
        """
        await self.initialize()
        return self._model.encode(text, normalize_embeddings=True).tolist()

    async def encode_batch(self, texts: list[str]) -> list[list[float]]:
        """批量编码

        Args:
            texts: 输入文本列表

        Returns:
            多个 1024 维归一化向量
        """
        await self.initialize()
        return self._model.encode(
            texts,
            batch_size=32,
            normalize_embeddings=True,
        ).tolist()

    async def health_check(self) -> bool:
        """健康检查"""
        try:
            await self.initialize()
            return self._model is not None
        except Exception as exc:
            logger.warning(f"EmbeddingService health check failed: {exc}")
            return False
