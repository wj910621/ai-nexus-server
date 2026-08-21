"""AI 引擎相关 Schema"""
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class Text2ImgRequest(BaseModel):
    """文生图请求"""
    prompt: str = Field(..., min_length=1, description="正向提示词")
    negative_prompt: str = Field(default="", description="负向提示词")
    width: int = Field(default=1024, ge=64, le=2048, description="图像宽度")
    height: int = Field(default=1024, ge=64, le=2048, description="图像高度")
    seed: Optional[int] = Field(default=None, description="随机种子")
    model: str = Field(default="flux", description="模型名称")


class GenerationResponse(BaseModel):
    """通用生成响应"""
    success: bool
    data: str = Field(default="", description="生成结果（URL 或文本）")
    content_type: str = Field(default="", description="内容类型")
    metadata: dict = Field(default_factory=dict, description="额外元信息")
    error: Optional[str] = Field(default=None, description="错误信息")


class TTSRequest(BaseModel):
    """语音合成请求"""
    text: str = Field(..., min_length=1, max_length=5000, description="待合成文本")
    voice: str = Field(default="zh-CN-XiaoxiaoNeural", description="声音 ID")
    rate: int = Field(default=0, ge=-100, le=100, description="语速")
    pitch: int = Field(default=0, ge=-100, le=100, description="音调")


class VoiceInfo(BaseModel):
    """声音信息"""
    name: str
    display_name: str = ""
    language: str = ""


class ChatMessage(BaseModel):
    """聊天消息"""
    role: Literal["user", "assistant", "system"]
    content: str


class ChatRequest(BaseModel):
    """LLM 对话请求"""
    messages: List[ChatMessage] = Field(..., min_length=1, description="消息列表")
    model: str = Field(default="deepseek-chat", description="模型名称")
    temperature: float = Field(default=0.7, ge=0, le=2, description="温度")
    max_tokens: int = Field(default=2000, ge=1, le=8192, description="最大 token 数")
    stream: bool = Field(default=False, description="是否流式输出")


class VideoComposeRequest(BaseModel):
    """视频合成请求"""
    frames: List[str] = Field(..., min_length=1, description="图像 URL 或路径列表")
    audio: Optional[str] = Field(default=None, description="音频路径或 URL")
    output_path: str = Field(default="output.mp4", description="输出路径")
    fps: int = Field(default=24, ge=1, le=60, description="帧率")
    resolution: List[int] = Field(
        default_factory=lambda: [1920, 1080],
        min_length=2,
        max_length=2,
        description="分辨率 [width, height]",
    )
    transition: str = Field(default="none", description="转场效果")


class ConsistentGenRequest(BaseModel):
    """角色一致性生成请求"""
    prompt: str = Field(..., min_length=1, description="提示词")
    reference_image: str = Field(..., min_length=1, description="参考图 URL 或 base64")
    consistency_weight: float = Field(
        default=0.8, ge=0, le=1, description="一致性权重"
    )
    character_description: Optional[str] = Field(default=None, description="角色描述")
    mood: Optional[str] = Field(default=None, description="情绪")
    width: int = Field(default=1024, ge=64, le=2048, description="图像宽度")
    height: int = Field(default=1024, ge=64, le=2048, description="图像高度")
    seed: Optional[int] = Field(default=None, description="随机种子")


class EngineInfo(BaseModel):
    """引擎信息"""
    name: str
    display_name: str
    initialized: bool
    extra: dict = Field(default_factory=dict, description="额外信息")


class EngineStatus(BaseModel):
    """引擎状态"""
    initialized: bool
    engine_count: int
    engine_types: List[str]
    init_errors: dict = Field(default_factory=dict, description="初始化错误")
