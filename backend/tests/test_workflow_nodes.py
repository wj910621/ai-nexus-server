# backend/tests/test_workflow_nodes.py
"""测试内置节点"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.engines.workflow.nodes.generation_nodes import (
    TextToImageNode, TTSNode, LLMChatNode, VideoComposeNode, CharacterGenNode,
)
from app.engines.workflow.nodes.utility_nodes import (
    TextInputNode, TextConcatNode, ImagePreviewNode,
)
from app.engines.base import GenerationResult


def test_text_to_image_definition():
    """测试文生图节点定义"""
    defn = TextToImageNode.get_definition()
    assert defn.type == "text_to_image"
    assert defn.name == "文生图"
    assert defn.category.value == "generation"
    assert len(defn.inputs) == 2
    assert defn.outputs[0].name == "image"


def test_tts_definition():
    """测试 TTS 节点定义"""
    defn = TTSNode.get_definition()
    assert defn.type == "tts"
    assert defn.outputs[0].name == "audio"


def test_llm_chat_definition():
    """测试 LLM 节点定义"""
    defn = LLMChatNode.get_definition()
    assert defn.type == "llm_chat"
    assert defn.outputs[0].name == "response"


def test_video_compose_definition():
    """测试视频合成节点定义"""
    defn = VideoComposeNode.get_definition()
    assert defn.type == "video_compose"
    assert defn.category.value == "composite"


def test_character_gen_definition():
    """测试角色生成节点定义"""
    defn = CharacterGenNode.get_definition()
    assert defn.type == "character_gen"
    assert defn.inputs[1].name == "reference_image"


def test_text_input_definition():
    """测试文本输入节点"""
    defn = TextInputNode.get_definition()
    assert defn.type == "text_input"
    assert defn.category.value == "input"


@pytest.mark.asyncio
async def test_text_input_execute():
    """测试文本输入节点执行"""
    node = TextInputNode("t1", {"value": "hello"})
    result = await node.execute({})
    assert result == {"text": "hello"}


@pytest.mark.asyncio
async def test_text_concat_execute():
    """测试文本拼接节点"""
    node = TextConcatNode("c1", {"separator": " | "})
    result = await node.execute({"text1": "a", "text2": "b", "text3": "c"})
    assert result == {"text": "a | b | c"}


@pytest.mark.asyncio
async def test_text_concat_skip_empty():
    """测试拼接跳过空值"""
    node = TextConcatNode("c1", {})
    result = await node.execute({"text1": "a", "text2": "", "text3": "c"})
    assert result == {"text": "a, c"}


@pytest.mark.asyncio
async def test_image_preview_execute():
    """测试图像预览节点"""
    node = ImagePreviewNode("p1")
    result = await node.execute({"image": "/uploads/test.png"})
    assert result == {"image": "/uploads/test.png"}


@pytest.mark.asyncio
async def test_image_preview_missing_input():
    """测试图像预览缺输入"""
    node = ImagePreviewNode("p1")
    with pytest.raises(ValueError, match="缺少"):
        await node.execute({})


@pytest.mark.asyncio
async def test_text_to_image_execute_success():
    """测试文生图节点执行成功"""
    mock_engine = AsyncMock()
    mock_engine.text2img = AsyncMock(return_value=GenerationResult(
        success=True, data="/uploads/images/test.png",
        content_type="image/png", metadata={}
    ))
    with patch("app.engines.workflow.nodes.generation_nodes.engine_manager") as mock_manager:
        mock_manager.get_image_engine.return_value = mock_engine
        node = TextToImageNode("img1", {"width": 512, "height": 512, "model": "flux"})
        result = await node.execute({"prompt": "a cute cat"})
        assert result == {"image": "/uploads/images/test.png"}
        mock_engine.text2img.assert_called_once()


@pytest.mark.asyncio
async def test_text_to_image_missing_prompt():
    """测试文生图缺 prompt"""
    node = TextToImageNode("img1")
    with pytest.raises(ValueError, match="prompt"):
        await node.execute({})


@pytest.mark.asyncio
async def test_text_to_image_engine_failure():
    """测试文生图引擎失败"""
    mock_engine = AsyncMock()
    mock_engine.text2img = AsyncMock(return_value=GenerationResult(
        success=False, data=b"", content_type="", metadata={}, error="API error"
    ))
    with patch("app.engines.workflow.nodes.generation_nodes.engine_manager") as mock_manager:
        mock_manager.get_image_engine.return_value = mock_engine
        node = TextToImageNode("img1")
        with pytest.raises(RuntimeError, match="API error"):
            await node.execute({"prompt": "test"})


@pytest.mark.asyncio
async def test_tts_execute_success():
    """测试 TTS 节点执行"""
    mock_engine = AsyncMock()
    mock_engine.synthesize = AsyncMock(return_value=GenerationResult(
        success=True, data="/uploads/audio/test.mp3",
        content_type="audio/mp3", metadata={}
    ))
    with patch("app.engines.workflow.nodes.generation_nodes.engine_manager") as mock_manager:
        mock_manager.get_tts_engine.return_value = mock_engine
        node = TTSNode("tts1", {"voice": "zh-CN-XiaoxiaoNeural"})
        result = await node.execute({"text": "你好"})
        assert result == {"audio": "/uploads/audio/test.mp3"}


@pytest.mark.asyncio
async def test_llm_chat_execute_success():
    """测试 LLM 节点执行"""
    mock_engine = AsyncMock()
    mock_engine.chat = AsyncMock(return_value=GenerationResult(
        success=True, data="Hello from LLM",
        content_type="text/plain", metadata={}
    ))
    with patch("app.engines.workflow.nodes.generation_nodes.engine_manager") as mock_manager:
        mock_manager.get_llm_engine.return_value = mock_engine
        node = LLMChatNode("llm1", {"model": "deepseek-chat"})
        result = await node.execute({"user_message": "hi", "system_prompt": "be nice"})
        assert result == {"response": "Hello from LLM"}

        # 验证 messages 构造
        call_kwargs = mock_engine.chat.call_args.kwargs
        assert call_kwargs["messages"][0]["role"] == "system"
        assert call_kwargs["messages"][1]["role"] == "user"


@pytest.mark.asyncio
async def test_video_compose_execute_success():
    """测试视频合成节点"""
    mock_engine = AsyncMock()
    mock_engine.compose = AsyncMock(return_value=GenerationResult(
        success=True, data="/uploads/video/test.mp4",
        content_type="video/mp4", metadata={}
    ))
    with patch("app.engines.workflow.nodes.generation_nodes.engine_manager") as mock_manager:
        mock_manager.get_video_engine.return_value = mock_engine
        node = VideoComposeNode("v1", {"fps": 30, "width": 1280, "height": 720})
        result = await node.execute({"frames": ["/uploads/1.png", "/uploads/2.png"]})
        assert result == {"video": "/uploads/video/test.mp4"}

        call_kwargs = mock_engine.compose.call_args.kwargs
        assert call_kwargs["fps"] == 30
        assert call_kwargs["resolution"] == (1280, 720)


@pytest.mark.asyncio
async def test_character_gen_execute_with_url():
    """测试角色生成节点 - URL 参考"""
    mock_engine = AsyncMock()
    mock_engine.generate_consistent = AsyncMock(return_value=GenerationResult(
        success=True, data="/uploads/images/char.png",
        content_type="image/png", metadata={}
    ))
    mock_http_response = MagicMock()
    mock_http_response.content = b"fake-image-bytes"
    mock_http_response.raise_for_status = MagicMock()

    with patch("app.engines.workflow.nodes.generation_nodes.engine_manager") as mock_manager, \
         patch("httpx.AsyncClient") as mock_http_client:
        mock_manager.get_character_engine.return_value = mock_engine
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_http_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_http_client.return_value = mock_client

        node = CharacterGenNode("c1", {"consistency_weight": 0.9})
        result = await node.execute({
            "prompt": "a beautiful girl",
            "reference_image": "https://example.com/char.png"
        })
        assert result == {"image": "/uploads/images/char.png"}
