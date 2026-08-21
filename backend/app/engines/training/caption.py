"""CaptionGenerator — BLIP-2 自动图片描述

Phase 8 P3: LoRA 训练 UI
"""
import logging
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


class CaptionGenerator:
    """BLIP-2 图片自动描述生成器"""

    def __init__(self, model: Optional[str] = None):
        self._model_name = model or settings.blip_model_name
        self._processor = None
        self._model = None

    async def generate(self, image_path: str, trigger_word: str = "") -> str:
        """生成单张图片的 caption

        Args:
            image_path: 图片路径
            trigger_word: 触发词（追加到 caption 末尾）

        Returns:
            caption 字符串
        """
        try:
            self._load_model()
        except ImportError as e:
            raise RuntimeError(f"caption 模型加载失败: {e}")

        caption = self._generate_caption(image_path)

        if trigger_word:
            caption = f"{caption}, {trigger_word} character"

        return caption

    async def batch_generate(
        self, image_paths: list[str], trigger_word: str = "",
    ) -> list[str]:
        """批量生成 caption

        Args:
            image_paths: 图片路径列表
            trigger_word: 触发词

        Returns:
            caption 列表（与输入顺序一致）
        """
        results = []
        for path in image_paths:
            caption = await self.generate(path, trigger_word)
            results.append(caption)
        return results

    def _load_model(self):
        """懒加载 BLIP 模型"""
        if self._model is not None:
            return

        from transformers import BlipForConditionalGeneration, BlipProcessor

        logger.info(f"Loading BLIP model: {self._model_name}")
        self._processor = BlipProcessor.from_pretrained(self._model_name)
        self._model = BlipForConditionalGeneration.from_pretrained(
            self._model_name
        )

    def _generate_caption(self, image_path: str) -> str:
        """用 BLIP 生成图片描述"""
        from PIL import Image

        image = Image.open(image_path).convert("RGB")
        inputs = self._processor(image, return_tensors="pt")

        import torch
        with torch.no_grad():
            output = self._model.generate(**inputs, max_new_tokens=50)

        caption = self._processor.decode(output[0], skip_special_tokens=True)
        return caption.strip()
