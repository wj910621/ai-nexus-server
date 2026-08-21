"""测试 Edge TTS Provider（使用 mock，不依赖真实网络）"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.engines.tts.edge_tts import EdgeTTSProvider
from app.engines.base import GenerationResult


@pytest.fixture
def provider():
    """Provider 实例"""
    return EdgeTTSProvider()


def test_provider_init(provider):
    """测试初始化"""
    assert provider.name == "edge-tts"
    assert provider.display_name == "Edge TTS (微软免费)"
    assert provider._initialized is False


def test_popular_voices(provider):
    """测试常用声音列表"""
    assert "zh-CN-XiaoxiaoNeural" in provider.POPULAR_VOICES
    assert "zh-CN-YunxiNeural" in provider.POPULAR_VOICES
    assert "zh-CN-YunyangNeural" in provider.POPULAR_VOICES
    assert "en-US-JennyNeural" in provider.POPULAR_VOICES
    assert "en-US-GuyNeural" in provider.POPULAR_VOICES


@pytest.mark.asyncio
async def test_provider_initialize(provider):
    """测试初始化方法"""
    await provider.initialize()
    assert provider._initialized is True


@pytest.mark.asyncio
async def test_synthesize_success(provider):
    """测试合成成功（mock edge_tts）"""
    provider._initialized = True

    # mock edge_tts.Communicate.stream() 返回音频流
    mock_communicate = MagicMock()

    async def mock_stream():
        yield {"type": "audio", "data": b"fake-audio-chunk-1"}
        yield {"type": "audio", "data": b"fake-audio-chunk-2"}
        yield {"type": "WordBoundary", "offset": 0, "duration": 100}

    mock_communicate.stream = mock_stream

    with patch("app.engines.tts.edge_tts.edge_tts") as mock_edge_tts:
        mock_edge_tts.Communicate.return_value = mock_communicate

        result = await provider.synthesize(
            text="你好，世界",
            voice="zh-CN-XiaoxiaoNeural",
        )

    assert result.success is True
    assert result.content_type == "audio/mp3"
    assert result.metadata["provider"] == "edge-tts"
    assert result.metadata["voice"] == "zh-CN-XiaoxiaoNeural"
    assert result.metadata["text_length"] == len("你好，世界")
    assert "/uploads/audio/" in result.data
    assert result.error is None

    # 验证 Communicate 被正确调用
    mock_edge_tts.Communicate.assert_called_once()
    call_args = mock_edge_tts.Communicate.call_args
    assert call_args[0][0] == "你好，世界"  # text 位置参数
    assert call_args[0][1] == "zh-CN-XiaoxiaoNeural"  # voice 位置参数
    # 默认 rate/pitch/volume
    assert call_args.kwargs["rate"] == "+0%"
    assert call_args.kwargs["pitch"] == "+0Hz"
    assert call_args.kwargs["volume"] == "+0%"


@pytest.mark.asyncio
async def test_synthesize_with_rate_pitch(provider):
    """测试 rate/pitch/volume 参数传递"""
    provider._initialized = True

    mock_communicate = MagicMock()

    async def mock_stream():
        yield {"type": "audio", "data": b"fake-audio"}

    mock_communicate.stream = mock_stream

    with patch("app.engines.tts.edge_tts.edge_tts") as mock_edge_tts:
        mock_edge_tts.Communicate.return_value = mock_communicate

        result = await provider.synthesize(
            text="测试语速音调",
            voice="zh-CN-YunxiNeural",
            rate=50,
            pitch=10,
            volume=-20,
        )

    assert result.success is True
    assert result.metadata["rate"] == 50
    assert result.metadata["pitch"] == 10
    assert result.metadata["volume"] == -20

    # 验证 rate/pitch/volume 转换为 edge-tts 格式
    call_kwargs = mock_edge_tts.Communicate.call_args.kwargs
    assert call_kwargs["rate"] == "+50%"
    assert call_kwargs["pitch"] == "+10Hz"
    assert call_kwargs["volume"] == "-20%"


@pytest.mark.asyncio
async def test_health_check(provider):
    """测试健康检查 - mock edge-tts 可用"""
    provider._initialized = True

    with patch("app.engines.tts.edge_tts.edge_tts", new=MagicMock()):
        healthy = await provider.health_check()
        assert healthy is True


def test_get_info(provider):
    """测试获取引擎信息"""
    info = provider.get_info()
    assert info["name"] == "edge-tts"
    assert info["display_name"] == "Edge TTS (微软免费)"
    assert "popular_voices" in info
    assert "zh-CN-XiaoxiaoNeural" in info["popular_voices"]
    assert info["default_voice"] == "zh-CN-XiaoxiaoNeural"
