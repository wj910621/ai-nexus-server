"""图像优化器 - PNG→WebP 转换 + 缩略图生成"""
import io
import logging

from PIL import Image

logger = logging.getLogger(__name__)


class ImageOptimizer:
    """图像优化

    - PNG → WebP 转换 (平均减少 30-50% 体积)
    - 缩略图生成 (用于画廊列表，避免加载原图)
    - 支持自定义质量和最大尺寸
    """

    DEFAULT_QUALITY = 85
    DEFAULT_THUMBNAIL_SIZE = 256

    def to_webp(
        self,
        image_data: bytes,
        quality: int = DEFAULT_QUALITY,
    ) -> bytes:
        """将图像转换为 WebP 格式"""
        try:
            img = Image.open(io.BytesIO(image_data))
        except Exception as exc:
            raise ValueError(f"Invalid image data: {exc}")

        # Convert to RGB if necessary (WebP doesn't support all modes)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGBA")
        elif img.mode != "RGB":
            img = img.convert("RGB")

        buf = io.BytesIO()
        img.save(buf, format="WEBP", quality=quality, method=6)
        return buf.getvalue()

    def generate_thumbnail(
        self,
        image_data: bytes,
        max_size: int = DEFAULT_THUMBNAIL_SIZE,
    ) -> bytes:
        """生成缩略图 (保持宽高比，不放大)"""
        try:
            img = Image.open(io.BytesIO(image_data))
        except Exception as exc:
            raise ValueError(f"Invalid image data: {exc}")

        w, h = img.size
        if w <= max_size and h <= max_size:
            # No upscaling
            ratio = 1.0
        else:
            ratio = min(max_size / w, max_size / h)

        new_size = (max(1, int(w * ratio)), max(1, int(h * ratio)))
        thumb = img.resize(new_size, Image.LANCZOS)

        buf = io.BytesIO()
        thumb.save(buf, format="WEBP", quality=80, method=4)
        return buf.getvalue()

    def optimize(
        self,
        image_data: bytes,
        thumbnail_size: int = DEFAULT_THUMBNAIL_SIZE,
        quality: int = DEFAULT_QUALITY,
    ) -> dict[str, bytes]:
        """一站式优化：返回 WebP + 缩略图"""
        return {
            "webp": self.to_webp(image_data, quality=quality),
            "thumbnail": self.generate_thumbnail(image_data, max_size=thumbnail_size),
        }


image_optimizer = ImageOptimizer()
