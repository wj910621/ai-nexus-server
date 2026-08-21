"""AI 引擎抽象基类 - 所有引擎必须实现统一接口"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class GenerationResult:
    """生成结果统一数据结构"""
    success: bool
    data: bytes | str  # bytes: 图像/音频；str: URL/文本
    content_type: str  # image/png, audio/mp3, text/plain
    metadata: dict  # 额外信息（耗时、模型、种子等）
    error: Optional[str] = None


class BaseEngine(ABC):
    """引擎抽象基类"""

    # P2: 初始化失败原因（None 表示未失败）
    _init_error: Optional[str] = None

    name: str = "base"
    display_name: str = "基础引擎"

    # P1 新增属性（子类可覆盖）
    is_local: bool = False           # True=本地推理, False=云端 API
    requires_api_key: bool = True    # True=需要 API Key, False=本地无需
    subscription_required: str = "free"  # "free" / "pro" / "enterprise"
    capability: dict = {}            # 如 {"max_resolution": 1024, "supports_stream": True}
    supported_models: list[str] = []  # 支持的模型列表
    health_check_url: str = ""       # API 健康检查端点（本地为空）

    @abstractmethod
    async def initialize(self) -> None:
        """初始化引擎（加载模型、建立连接等）"""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """健康检查"""
        ...

    def get_info(self) -> dict:
        """获取引擎信息（P1 扩展）"""
        return {
            "name": self.name,
            "display_name": self.display_name,
            "initialized": getattr(self, "_initialized", False),
            "is_local": self.is_local,
            "requires_api_key": self.requires_api_key,
            "subscription_required": self.subscription_required,
            "capability": self.capability,
            "supported_models": self.supported_models,
        }


class ImageGenProvider(BaseEngine):
    """图像生成 Provider 抽象基类"""

    @abstractmethod
    async def text2img(
        self,
        prompt: str,
        negative_prompt: str = "",
        width: int = 1024,
        height: int = 1024,
        seed: Optional[int] = None,
        **kwargs,
    ) -> GenerationResult:
        """文生图"""
        ...

    async def img2img(
        self,
        init_image: bytes,
        prompt: str,
        strength: float = 0.6,
        **kwargs,
    ) -> GenerationResult:
        """图生图（可选实现）"""
        raise NotImplementedError(f"{self.name} 不支持图生图")


class TTSProvider(BaseEngine):
    """TTS 语音合成 Provider 抽象基类"""

    @abstractmethod
    async def synthesize(
        self,
        text: str,
        voice: str = "zh-CN-XiaoxiaoNeural",
        rate: int = 0,
        pitch: int = 0,
        **kwargs,
    ) -> GenerationResult:
        """文本转语音"""
        ...


class LLMProvider(BaseEngine):
    """LLM 大语言模型 Provider 抽象基类"""

    @abstractmethod
    async def chat(
        self,
        messages: list[dict],
        model: str = "deepseek-chat",
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs,
    ) -> GenerationResult:
        """对话生成"""
        ...


class VideoComposerProvider(BaseEngine):
    """视频合成 Provider 抽象基类"""

    @abstractmethod
    async def compose(
        self,
        frames: list[str],  # 图像路径或 URL 列表
        audio: Optional[str] = None,
        output_path: str = "output.mp4",
        fps: int = 24,
        resolution: tuple[int, int] = (1920, 1080),
        **kwargs,
    ) -> GenerationResult:
        """合成视频"""
        ...


class CharacterConsistencyProvider(BaseEngine):
    """角色一致性 Provider 抽象基类"""

    @abstractmethod
    async def extract_features(self, image: bytes) -> list[float]:
        """提取角色特征向量"""
        ...

    @abstractmethod
    async def generate_consistent(
        self,
        prompt: str,
        reference_image: bytes,
        consistency_weight: float = 0.8,
        **kwargs,
    ) -> GenerationResult:
        """基于参考图生成一致性角色"""
        ...
