"""视频合成引擎"""
from app.engines.video.base import GenerationResult, VideoComposerProvider
from app.engines.video.ffmpeg import FFmpegVideoComposer


def get_default_provider() -> VideoComposerProvider:
    """获取默认视频合成 Provider（零成本默认策略：FFmpeg 本地免费开源）"""
    return FFmpegVideoComposer()


__all__ = [
    "VideoComposerProvider",
    "GenerationResult",
    "FFmpegVideoComposer",
    "get_default_provider",
]
