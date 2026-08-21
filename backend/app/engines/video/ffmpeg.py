"""FFmpeg 本地视频合成 Provider

文档：https://ffmpeg.org
- 零成本：FFmpeg 是本地免费开源工具（系统 PATH 中需可访问）
- 支持图像序列合成视频
- 支持音频合成（音视频）
- 支持多种编码格式（mp4, webm, avi, mov）
- 支持过渡效果（fade）

Task 11: parallel frame download via shared HTTP/2 client + asyncio.Semaphore.
"""
import asyncio
import os
import shutil
import subprocess
import tempfile
import time
from typing import Optional

from app.core.http_client import http_client_factory
from app.engines.base import GenerationResult, VideoComposerProvider

# Concurrency limit for parallel frame downloads (Task 11).
# Prevents overwhelming upstream image hosts while still parallelizing.
_FRAME_DOWNLOAD_CONCURRENCY = 8


async def _save_frame(data: bytes, dest_path: str) -> None:
    """Save a single frame's bytes to disk (Task 11).

    Extracted as a module-level coroutine so tests can patch it without
    touching disk.
    """
    with open(dest_path, "wb") as f:
        f.write(data)


class FFmpegVideoComposer(VideoComposerProvider):
    """FFmpeg 本地视频合成"""

    name = "ffmpeg"
    display_name = "FFmpeg (本地视频合成)"

    SUPPORTED_FORMATS = ["mp4", "webm", "avi", "mov"]
    DEFAULT_FPS = 24
    DEFAULT_RESOLUTION = (1920, 1080)

    def __init__(self, ffmpeg_path: str = "ffmpeg", timeout: int = 300):
        """
        初始化 FFmpeg Provider

        Args:
            ffmpeg_path: ffmpeg 可执行文件路径（默认 "ffmpeg"，使用系统 PATH）
            timeout: 视频合成超时时间（秒），视频合成较慢，默认 300 秒
        """
        self.ffmpeg_path = ffmpeg_path
        self.timeout = timeout
        self._initialized = False

    async def initialize(self) -> None:
        """初始化引擎 - 验证 ffmpeg 可用并标记 _initialized"""
        self._check_ffmpeg_available()
        self._initialized = True

    def _check_ffmpeg_available(self) -> bool:
        """检查 ffmpeg 是否可用（同步调用 subprocess.run）"""
        try:
            result = subprocess.run(
                [self.ffmpeg_path, "-version"],
                capture_output=True,
            )
            return result.returncode == 0
        except (FileNotFoundError, OSError):
            return False

    async def _download_frame(self, url: str, temp_dir: str) -> str:
        """
        下载或验证单帧图像 (Task 11: 使用共享 HTTP/2 client)

        Args:
            url: 图像 URL 或本地路径
            temp_dir: 临时目录路径

        Returns:
            本地文件路径
        """
        if url.startswith("http://") or url.startswith("https://"):
            ext = os.path.splitext(url.split("?")[0])[1] or ".png"
            filename = f"src_{abs(hash(url))}{ext}"
            local_path = os.path.join(temp_dir, filename)
            # Task 11: shared HTTP/2 client (keep-alive + connection pool)
            client = http_client_factory.get_client(
                "", timeout=self.timeout
            )
            resp = await client.get(url)
            resp.raise_for_status()
            await _save_frame(resp.content, local_path)
            return local_path
        else:
            if not os.path.exists(url):
                raise FileNotFoundError(f"帧图像不存在: {url}")
            return url

    async def _download_frames(
        self,
        frame_urls: list[str],
        dest_dir: str,
    ) -> list[str]:
        """Download all frames in parallel using shared HTTP/2 client (Task 11).

        Uses ``asyncio.gather`` with ``asyncio.Semaphore(8)`` to bound
        concurrency. Frames are saved as ``frame_{idx:06d}.png`` (0-indexed,
        6-digit zero-padded) into ``dest_dir``.

        Args:
            frame_urls: List of frame URLs to download.
            dest_dir: Directory to save frame files.

        Returns:
            List of local file paths in the same order as ``frame_urls``.

        Raises:
            httpx.HTTPStatusError: if any frame download fails (propagated
                from ``asyncio.gather``).
        """
        os.makedirs(dest_dir, exist_ok=True)
        # Shared HTTP/2 client — no base_url; URLs are absolute.
        client = http_client_factory.get_client("", timeout=self.timeout)
        sem = asyncio.Semaphore(_FRAME_DOWNLOAD_CONCURRENCY)

        async def download_one(idx: int, url: str) -> str:
            async with sem:
                resp = await client.get(url)
                resp.raise_for_status()
                dest = os.path.join(dest_dir, f"frame_{idx:06d}.png")
                await _save_frame(resp.content, dest)
                return dest

        paths = await asyncio.gather(
            *[download_one(i, u) for i, u in enumerate(frame_urls)]
        )
        return paths

    async def compose(
        self,
        frames: list[str],
        audio: Optional[str] = None,
        output_path: str = "output.mp4",
        fps: int = 24,
        resolution: tuple[int, int] = (1920, 1080),
        transition: str = "none",
        duration_per_frame: Optional[float] = None,
        **kwargs,
    ) -> GenerationResult:
        """
        合成视频

        Args:
            frames: 图像路径或 URL 列表
            audio: 音频路径（可选）
            output_path: 输出视频路径
            fps: 帧率（每秒帧数）
            resolution: 分辨率 (width, height)
            transition: 过渡效果（"none" 或 "fade"）
            duration_per_frame: 每帧显示时长（秒），如提供则覆盖 fps
            **kwargs: 其他参数
        """
        if not frames:
            return GenerationResult(
                success=False,
                data="",
                content_type="video/mp4",
                metadata={},
                error="frames 列表为空",
            )

        start_time = time.time()
        temp_dir = tempfile.mkdtemp(prefix="ffmpeg_compose_")

        try:
            # 下载/复制所有 frames 到临时目录，命名 frame_001.png, frame_002.png...
            for i, frame in enumerate(frames, start=1):
                local_path = await self._download_frame(frame, temp_dir)
                target_path = os.path.join(temp_dir, f"frame_{i:03d}.png")
                if os.path.abspath(local_path) != os.path.abspath(target_path):
                    shutil.move(local_path, target_path)

            # 计算实际帧率和总时长
            if duration_per_frame is not None and duration_per_frame > 0:
                effective_fps = 1.0 / duration_per_frame
                duration = len(frames) * duration_per_frame
            else:
                effective_fps = fps
                duration = len(frames) / fps if fps > 0 else 0.0

            width, height = resolution

            # 构建 ffmpeg 命令
            cmd = [
                self.ffmpeg_path,
                "-y",  # 覆盖输出
                "-framerate", str(effective_fps),
                "-i", os.path.join(temp_dir, "frame_%03d.png"),
            ]

            # 音频输入
            audio_included = False
            if audio:
                cmd.extend(["-i", audio])
                audio_included = True

            # 视频滤镜（过渡效果 + 缩放）
            vf_filters = []
            if transition == "fade" and duration > 1:
                fade_out_start = max(0, duration - 1)
                vf_filters.append("fade=t=in:st=0:d=1")
                vf_filters.append(f"fade=t=out:st={fade_out_start}:d=1")
            vf_filters.append(f"scale={width}:{height}")

            cmd.extend(["-vf", ",".join(vf_filters)])

            # 视频编码
            cmd.extend(["-c:v", "libx264", "-pix_fmt", "yuv420p"])

            # 音频编码
            if audio_included:
                cmd.extend(["-c:a", "aac", "-shortest"])

            cmd.append(output_path)

            # 异步执行 ffmpeg
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            try:
                await asyncio.wait_for(
                    process.communicate(), timeout=self.timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.communicate()
                return GenerationResult(
                    success=False,
                    data="",
                    content_type="video/mp4",
                    metadata={
                        "provider": self.name,
                        "frame_count": len(frames),
                    },
                    error=f"ffmpeg 执行超时（{self.timeout}s）",
                )

            if process.returncode != 0:
                return GenerationResult(
                    success=False,
                    data="",
                    content_type="video/mp4",
                    metadata={
                        "provider": self.name,
                        "frame_count": len(frames),
                        "returncode": process.returncode,
                    },
                    error=f"ffmpeg 退出码 {process.returncode}",
                )

            elapsed = time.time() - start_time

            # 获取输出文件大小
            output_size = 0
            if os.path.exists(output_path):
                output_size = os.path.getsize(output_path)

            return GenerationResult(
                success=True,
                data=output_path,
                content_type="video/mp4",
                metadata={
                    "provider": self.name,
                    "frame_count": len(frames),
                    "fps": fps,
                    "resolution": list(resolution),
                    "audio_included": audio_included,
                    "duration": round(duration, 2),
                    "elapsed_seconds": round(elapsed, 2),
                    "output_size_bytes": output_size,
                },
            )

        except Exception as e:
            return GenerationResult(
                success=False,
                data="",
                content_type="video/mp4",
                metadata={
                    "provider": self.name,
                    "frame_count": len(frames),
                },
                error=f"{type(e).__name__}: {str(e)}",
            )
        finally:
            # 清理临时目录
            shutil.rmtree(temp_dir, ignore_errors=True)

    async def health_check(self) -> bool:
        """健康检查 - ffmpeg 是否可用"""
        return self._check_ffmpeg_available()

    def get_info(self) -> dict:
        """获取引擎信息"""
        info = super().get_info()
        info["supported_formats"] = self.SUPPORTED_FORMATS
        info["default_fps"] = self.DEFAULT_FPS
        info["default_resolution"] = list(self.DEFAULT_RESOLUTION)
        info["ffmpeg_available"] = self._check_ffmpeg_available()
        return info
