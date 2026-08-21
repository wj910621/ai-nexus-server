"""Tests for ImageOptimizer."""
import io
import random
import pytest
from PIL import Image

from app.services.image_optimizer import ImageOptimizer, image_optimizer


def _make_png_bytes(size=(512, 512), color=(255, 0, 0)) -> bytes:
    """Generate a PNG image as bytes."""
    img = Image.new("RGB", size, color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_noisy_png_bytes(size=(512, 512)) -> bytes:
    """Generate a PNG with random pixel noise so quality affects output size."""
    img = Image.new("RGB", size)
    pixels = img.load()
    rng = random.Random(42)  # Deterministic for reproducible tests
    for y in range(size[1]):
        for x in range(size[0]):
            pixels[x, y] = (rng.randint(0, 255), rng.randint(0, 255), rng.randint(0, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_png_to_webp_reduces_size():
    """WebP is smaller than PNG for the same image."""
    png_data = _make_png_bytes(size=(512, 512))
    webp_data = image_optimizer.to_webp(png_data, quality=85)
    assert len(webp_data) < len(png_data)
    # WebP should be at least 10% smaller
    assert len(webp_data) / len(png_data) < 0.9


def test_png_to_webp_preserves_dimensions():
    """WebP output has same dimensions as input."""
    png_data = _make_png_bytes(size=(640, 480))
    webp_data = image_optimizer.to_webp(png_data, quality=85)
    img = Image.open(io.BytesIO(webp_data))
    assert img.size == (640, 480)


def test_generate_thumbnail_creates_smaller_image():
    """Thumbnail is smaller than original."""
    png_data = _make_png_bytes(size=(1024, 1024))
    thumb = image_optimizer.generate_thumbnail(png_data, max_size=256)
    img = Image.open(io.BytesIO(thumb))
    assert img.size == (256, 256)


def test_generate_thumbnail_preserves_aspect_ratio():
    """Thumbnail preserves aspect ratio."""
    png_data = _make_png_bytes(size=(800, 400))
    thumb = image_optimizer.generate_thumbnail(png_data, max_size=200)
    img = Image.open(io.BytesIO(thumb))
    # 800:400 = 2:1, max 200 → 200x100
    assert img.size == (200, 100)


def test_generate_thumbnail_no_upscale_for_small_images():
    """Small images are not upscaled."""
    png_data = _make_png_bytes(size=(100, 100))
    thumb = image_optimizer.generate_thumbnail(png_data, max_size=256)
    img = Image.open(io.BytesIO(thumb))
    assert img.size == (100, 100)


def test_optimize_returns_both_webp_and_thumbnail():
    """optimize() returns a dict with webp + thumbnail keys."""
    png_data = _make_png_bytes(size=(512, 512))
    result = image_optimizer.optimize(png_data, thumbnail_size=128, quality=85)
    assert "webp" in result
    assert "thumbnail" in result
    assert isinstance(result["webp"], bytes)
    assert isinstance(result["thumbnail"], bytes)


def test_optimize_handles_invalid_image_gracefully():
    """Invalid image bytes raise ValueError."""
    with pytest.raises(ValueError):
        image_optimizer.to_webp(b"not an image")


def test_webp_quality_affects_size():
    """Lower quality → smaller file (for complex/noisy images)."""
    # Solid-color images compress so well that quality barely matters; use a
    # noisy image to ensure the quality parameter has a measurable effect.
    png_data = _make_noisy_png_bytes(size=(256, 256))
    high_q = image_optimizer.to_webp(png_data, quality=95)
    low_q = image_optimizer.to_webp(png_data, quality=30)
    assert len(low_q) < len(high_q)
