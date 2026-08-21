"""A4: 文件上传安全测试 - Phase 8 P7"""
import io
import pytest
from fastapi import HTTPException

from app.core.upload_security import (
    sanitize_filename,
    validate_magic_bytes,
    validate_upload,
    MAX_UPLOAD_SIZE,
    ALLOWED_EXTENSIONS,
)


def _image_bytes(fmt: str) -> bytes:
    from PIL import Image

    output = io.BytesIO()
    Image.new("RGB", (2, 2), color="white").save(output, format=fmt)
    return output.getvalue()


def _make_upload_file(data: bytes, filename: str, content_type: str = "image/png"):
    """构造 Starlette UploadFile 用于测试"""
    from starlette.datastructures import UploadFile
    f = UploadFile(filename=filename, file=io.BytesIO(data))
    f.headers = {"content-type": content_type}
    return f


async def test_valid_png_upload():
    """合法 PNG 文件应通过校验"""
    png = _image_bytes("PNG")
    f = _make_upload_file(png, "test.png", "image/png")
    data = await validate_upload(f)
    assert data == png


async def test_invalid_extension_rejected():
    """不允许的扩展名应被拒绝"""
    f = _make_upload_file(b"data", "evil.exe", "application/octet-stream")
    with pytest.raises(HTTPException) as exc:
        await validate_upload(f)
    assert exc.value.status_code == 400


async def test_oversized_file_rejected():
    """超过 20MB 的文件应被拒绝"""
    big = b"\x89PNG\r\n\x1a\n" + b"\x00" * (MAX_UPLOAD_SIZE + 1)
    f = _make_upload_file(big, "big.png", "image/png")
    with pytest.raises(HTTPException) as exc:
        await validate_upload(f)
    assert exc.value.status_code == 413


async def test_magic_bytes_mismatch_rejected():
    """扩展名是 png 但内容不是 PNG 应被拒绝"""
    f = _make_upload_file(b"not a png at all", "fake.png", "image/png")
    with pytest.raises(HTTPException) as exc:
        await validate_upload(f)
    assert exc.value.status_code == 400
    assert "不匹配" in exc.value.detail


async def test_image_signature_must_match_extension_and_mime():
    """JPEG 内容伪装成 PNG 时必须拒绝。"""
    jpg = _image_bytes("JPEG")
    f = _make_upload_file(jpg, "fake.png", "image/png")
    with pytest.raises(HTTPException) as exc:
        await validate_upload(f)
    assert exc.value.status_code == 400
    assert "扩展名" in exc.value.detail


def test_filename_sanitization():
    """文件名应被剥离路径并替换特殊字符"""
    # 包含路径穿越
    assert sanitize_filename("../etc/passwd") == "passwd"
    # 包含特殊字符
    sanitized = sanitize_filename("file name with spaces.png")
    assert " " not in sanitized
    assert sanitized.endswith(".png")
    # 长文件名应被截断
    long_name = "a" * 200 + ".png"
    sanitized = sanitize_filename(long_name)
    assert len(sanitized) <= 128
    assert sanitized.endswith(".png")


def test_magic_bytes_validation():
    """magic bytes 校验各格式"""
    assert validate_magic_bytes(b"\x89PNG\r\n\x1a\n" + b"rest") is True
    assert validate_magic_bytes(b"\xff\xd8\xff" + b"rest") is True
    assert validate_magic_bytes(b"GIF87a" + b"rest") is True
    assert validate_magic_bytes(b"GIF89a" + b"rest") is True
    assert validate_magic_bytes(b"RIFF\x00\x00\x00\x00WEBP" + b"rest") is True
    assert validate_magic_bytes(b"plain text") is False


async def test_jpeg_upload_accepted():
    """JPEG 应通过校验"""
    jpg = _image_bytes("JPEG")
    f = _make_upload_file(jpg, "photo.jpg", "image/jpeg")
    data = await validate_upload(f)
    assert data == jpg


async def test_invalid_mime_rejected():
    """扩展名合法但 MIME 不在白名单应被拒绝"""
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
    f = _make_upload_file(png, "ok.png", "application/evil")
    with pytest.raises(HTTPException) as exc:
        await validate_upload(f)
    assert exc.value.status_code == 400


async def test_truncated_image_rejected_after_header_validation():
    """只有合法签名但不能完整解码的图片必须拒绝。"""
    truncated = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
    f = _make_upload_file(truncated, "truncated.png", "image/png")
    with pytest.raises(HTTPException) as exc:
        await validate_upload(f)
    assert exc.value.status_code == 400
    assert "损坏" in exc.value.detail
