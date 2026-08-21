"""文件上传安全 - 类型/大小/magic bytes 校验"""
import io
import warnings

from fastapi import HTTPException, UploadFile
from PIL import Image

ALLOWED_MIME_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
MAX_UPLOAD_SIZE = 20 * 1024 * 1024  # 20MB
MAX_IMAGE_PIXELS = 40_000_000

MAGIC_BYTES = {
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"\xff\xd8\xff": "image/jpeg",
    b"RIFF....WEBP": "image/webp",  # 简化，实际校验 RIFF + offset 8 WEBP
    b"GIF87a": "image/gif",
    b"GIF89a": "image/gif",
}

EXTENSION_MIME_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
}


def sanitize_filename(name: str) -> str:
    """剥离路径、替换特殊字符、限制长度"""
    import os
    import re
    name = os.path.basename(name)
    name = re.sub(r"[^\w.\-]", "_", name)
    if len(name) > 128:
        ext = os.path.splitext(name)[1]
        name = name[:128-len(ext)] + ext
    return name


def detect_image_mime(data: bytes) -> str | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):
        return "image/gif"
    return None


def validate_magic_bytes(data: bytes) -> bool:
    return detect_image_mime(data) is not None


async def validate_upload(file: UploadFile, max_size: int = MAX_UPLOAD_SIZE) -> bytes:
    """校验上传文件：扩展名/MIME/大小/magic bytes，返回文件内容 bytes。"""
    ext = "." + (file.filename or "").rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"不支持的文件类型: {ext}")
    if file.content_type and file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(400, f"不支持的 MIME 类型: {file.content_type}")
    # Limit the read itself so oversized requests cannot force unbounded memory use.
    data = await file.read(max_size + 1)
    if len(data) > max_size:
        raise HTTPException(413, f"文件过大: {len(data)} bytes > {max_size}")
    detected_mime = detect_image_mime(data)
    if detected_mime is None:
        raise HTTPException(400, "文件内容与扩展名不匹配")
    if detected_mime != EXTENSION_MIME_TYPES[ext]:
        raise HTTPException(400, "文件内容与扩展名不匹配")
    if file.content_type and detected_mime != file.content_type:
        raise HTTPException(400, "文件内容与 MIME 类型不匹配")

    # Header checks are not enough: force Pillow to parse the complete image
    # and reject truncated/corrupt files and decompression bombs.
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as image:
                width, height = image.size
                if width <= 0 or height <= 0 or width * height > MAX_IMAGE_PIXELS:
                    raise HTTPException(413, "图片像素数量超过限制")
                if image.format and Image.MIME.get(image.format) != detected_mime:
                    raise HTTPException(400, "图片解码格式与声明类型不匹配")
                image.verify()
    except HTTPException:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise HTTPException(413, "图片像素数量超过限制")
    except (OSError, SyntaxError, ValueError):
        raise HTTPException(400, "图片文件损坏或无法完整解码")
    return data
