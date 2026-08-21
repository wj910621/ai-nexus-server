"""Tests for Task 11.7b: FFmpeg parallel frame download."""
import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.engines.video.ffmpeg import FFmpegVideoComposer


@pytest.mark.asyncio
async def test_frame_downloads_use_shared_client():
    """Frame downloads use HttpClientFactory shared client (not per-frame new client)."""
    engine = FFmpegVideoComposer()
    frames = [f"https://example.com/frame{i}.png" for i in range(5)]

    mock_resp = MagicMock()
    mock_resp.content = b"fake-image-bytes"
    mock_resp.raise_for_status = MagicMock()

    with patch("app.engines.video.ffmpeg.http_client_factory") as mock_factory, \
         patch("app.engines.video.ffmpeg._save_frame", new=AsyncMock()):
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_factory.get_client.return_value = mock_client

        await engine._download_frames(frames, dest_dir="/tmp/test")

    # Single shared client used for all frames
    mock_factory.get_client.assert_called_once()
    # All 5 frames downloaded via the shared client
    assert mock_client.get.await_count == 5


@pytest.mark.asyncio
async def test_frame_downloads_run_in_parallel():
    """5 frames download concurrently (not serially).

    Serial 5x100ms = 500ms+; parallel with Semaphore(8) ≈ 100ms.
    """
    engine = FFmpegVideoComposer()
    frames = [f"https://example.com/frame{i}.png" for i in range(5)]

    async def slow_get(url):
        await asyncio.sleep(0.1)  # 100ms per request
        resp = MagicMock()
        resp.content = b"data"
        resp.raise_for_status = MagicMock()
        return resp

    mock_client = AsyncMock()
    mock_client.get = slow_get

    with patch("app.engines.video.ffmpeg.http_client_factory") as mock_factory, \
         patch("app.engines.video.ffmpeg._save_frame", new=AsyncMock()):
        mock_factory.get_client.return_value = mock_client

        import time
        t0 = time.monotonic()
        await engine._download_frames(frames, dest_dir="/tmp/test")
        elapsed = time.monotonic() - t0

    # Parallel: ~100ms. Serial would be ~500ms. Allow 300ms headroom.
    assert elapsed < 0.35, f"Frame download took {elapsed:.2f}s, expected parallel (<0.35s)"


@pytest.mark.asyncio
async def test_concurrency_limited_by_semaphore():
    """At most 8 concurrent downloads (Semaphore prevents overwhelming upstream)."""
    engine = FFmpegVideoComposer()
    frames = [f"https://example.com/frame{i}.png" for i in range(20)]

    current = 0
    peak = 0

    async def tracked_get(url):
        nonlocal current, peak
        current += 1
        peak = max(peak, current)
        await asyncio.sleep(0.02)
        current -= 1
        resp = MagicMock()
        resp.content = b"data"
        resp.raise_for_status = MagicMock()
        return resp

    mock_client = AsyncMock()
    mock_client.get = tracked_get

    with patch("app.engines.video.ffmpeg.http_client_factory") as mock_factory, \
         patch("app.engines.video.ffmpeg._save_frame", new=AsyncMock()):
        mock_factory.get_client.return_value = mock_client
        await engine._download_frames(frames, dest_dir="/tmp/test")

    assert peak <= 8, f"Peak concurrent downloads {peak} exceeded Semaphore(8) limit"
    assert peak >= 2, "Expected parallel downloads (peak >= 2)"


@pytest.mark.asyncio
async def test_frame_download_failure_propagates():
    """A failed frame download raises and aborts the gather."""
    engine = FFmpegVideoComposer()
    frames = ["https://example.com/ok.png", "https://example.com/bad.png"]

    async def failing_get(url):
        if "bad" in url:
            raise httpx.HTTPStatusError(
                "404", request=MagicMock(), response=MagicMock(status_code=404)
            )
        resp = MagicMock()
        resp.content = b"data"
        resp.raise_for_status = MagicMock()
        return resp

    mock_client = AsyncMock()
    mock_client.get = failing_get

    import httpx
    with patch("app.engines.video.ffmpeg.http_client_factory") as mock_factory, \
         patch("app.engines.video.ffmpeg._save_frame", new=AsyncMock()):
        mock_factory.get_client.return_value = mock_client
        with pytest.raises(httpx.HTTPStatusError):
            await engine._download_frames(frames, dest_dir="/tmp/test")
