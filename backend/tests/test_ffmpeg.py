"""测试 FFmpeg Video Composer Provider（使用 mock，不依赖真实 ffmpeg）"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.engines.video.ffmpeg import FFmpegVideoComposer
from app.engines.base import GenerationResult


@pytest.fixture
def provider():
    """Provider 实例"""
    return FFmpegVideoComposer()


def test_provider_init(provider):
    """测试初始化"""
    assert provider.name == "ffmpeg"
    assert provider.display_name == "FFmpeg (本地视频合成)"
    assert provider.SUPPORTED_FORMATS == ["mp4", "webm", "avi", "mov"]
    assert provider.DEFAULT_FPS == 24
    assert provider.DEFAULT_RESOLUTION == (1920, 1080)
    assert provider._initialized is False
    assert provider.ffmpeg_path == "ffmpeg"
    assert provider.timeout == 300


@pytest.mark.asyncio
async def test_provider_initialize(provider):
    """测试初始化方法 - mock _check_ffmpeg_available 返回 True"""
    with patch.object(provider, "_check_ffmpeg_available", return_value=True):
        await provider.initialize()
    assert provider._initialized is True


def test_check_ffmpeg_available(provider):
    """测试 ffmpeg 可用 - mock subprocess.run 返回 returncode=0"""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0, stdout="ffmpeg version 6.0", stderr=""
        )
        result = provider._check_ffmpeg_available()
    assert result is True
    mock_run.assert_called_once()


def test_check_ffmpeg_not_available(provider):
    """测试 ffmpeg 不可用 - mock subprocess.run 抛出 FileNotFoundError"""
    with patch("subprocess.run", side_effect=FileNotFoundError("ffmpeg not found")):
        result = provider._check_ffmpeg_available()
    assert result is False


@pytest.mark.asyncio
async def test_compose_success(provider):
    """测试合成成功（mock asyncio.create_subprocess_exec 和 _download_frame）"""
    mock_process = AsyncMock()
    mock_process.returncode = 0
    mock_process.communicate = AsyncMock(return_value=(b"", b""))

    with patch(
        "asyncio.create_subprocess_exec", new=AsyncMock(return_value=mock_process)
    ):
        with patch.object(
            provider,
            "_download_frame",
            new=AsyncMock(side_effect=lambda url, dir: f"{dir}/frame_001.png"),
        ):
            result = await provider.compose(
                frames=["http://example.com/1.png"],
                output_path="out.mp4",
                fps=24,
                resolution=(1920, 1080),
            )

    assert result.success is True
    assert result.content_type == "video/mp4"
    assert result.data == "out.mp4"
    assert result.error is None
    assert result.metadata["provider"] == "ffmpeg"
    assert result.metadata["frame_count"] == 1
    assert result.metadata["fps"] == 24
    assert result.metadata["resolution"] == [1920, 1080]
    assert result.metadata["audio_included"] is False
    assert "duration" in result.metadata
    assert "elapsed_seconds" in result.metadata
    assert "output_size_bytes" in result.metadata


@pytest.mark.asyncio
async def test_compose_no_frames(provider):
    """测试传入空 frames 列表时返回 success=False"""
    result = await provider.compose(frames=[], output_path="out.mp4")
    assert result.success is False
    assert result.error is not None
    assert "frames" in result.error.lower() or "空" in result.error


@pytest.mark.asyncio
async def test_health_check(provider):
    """测试健康检查 - mock _check_ffmpeg_available"""
    with patch.object(provider, "_check_ffmpeg_available", return_value=True):
        healthy = await provider.health_check()
    assert healthy is True

    with patch.object(provider, "_check_ffmpeg_available", return_value=False):
        healthy = await provider.health_check()
    assert healthy is False


def test_get_info(provider):
    """测试获取引擎信息"""
    with patch.object(provider, "_check_ffmpeg_available", return_value=True):
        info = provider.get_info()
    assert info["name"] == "ffmpeg"
    assert info["display_name"] == "FFmpeg (本地视频合成)"
    assert "supported_formats" in info
    assert info["supported_formats"] == ["mp4", "webm", "avi", "mov"]
    assert info["default_fps"] == 24
    assert info["default_resolution"] == [1920, 1080]
    assert info["ffmpeg_available"] is True
