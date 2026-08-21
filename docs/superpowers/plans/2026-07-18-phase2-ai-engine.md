# Phase 2: AI 引擎层 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建漫剧生成软件的 AI 引擎层，包括图像生成、角色一致性、TTS 配音、视频合成四大核心引擎，以"免费 API 优先 + 本地引擎可插拔"的混合架构实现零成本可运行。

**Architecture:** 采用 Provider 抽象模式，每个引擎定义统一接口，支持多个后端 Provider（免费 API / 本地模型 / 付费 API）。默认启用免费 API（Pollinations.ai / edge-tts / DeepSeek），保留本地模型接口供未来 GPU 环境使用。所有引擎通过统一的 EngineManager 管理，对外暴露异步 API。

**Tech Stack:**
- HTTP 客户端：httpx (异步)
- 图像处理：Pillow
- TTS：edge-tts (免费)
- 音频处理：pygame / pydub
- 视频合成：ffmpeg-python (subprocess)
- LLM：DeepSeek API (免费额度)
- 备选图像：Pollinations.ai (免费)、Stability AI (付费可选)
- 任务队列：Celery + Redis（异步执行长任务）

---

## 设计原则

### 1. Provider 抽象模式
每个引擎定义抽象基类，多个 Provider 实现同一接口，通过配置切换：

```python
class ImageGenProvider(ABC):
    @abstractmethod
    async def text2img(self, prompt: str, **opts) -> bytes: ...

class PollinationsProvider(ImageGenProvider): ...  # 免费 API
class SDXLLocalProvider(ImageGenProvider): ...     # 本地 GPU
class StabilityProvider(ImageGenProvider): ...     # 付费 API
```

### 2. 零成本默认
所有引擎默认使用免费 API，无需 GPU 即可运行：
- 图像生成：Pollinations.ai (无需 API Key)
- TTS：edge-tts (微软免费)
- LLM：DeepSeek (用户自带 Key，有免费额度)
- 视频合成：FFmpeg (本地)

### 3. 异步优先
所有引擎方法为 `async`，长任务通过 Celery 异步执行，避免阻塞 API。

### 4. 文件存储
生成的素材统一存储到 MinIO/S3，URL 返回给前端。

---

## File Structure

```
backend/app/
├── engines/                          # AI 引擎层
│   ├── __init__.py                   # 导出 EngineManager
│   ├── base.py                       # 引擎抽象基类
│   ├── manager.py                    # 引擎管理器（单例）
│   ├── image/
│   │   ├── __init__.py
│   │   ├── base.py                   # ImageGenProvider 抽象基类
│   │   ├── pollinations.py           # Pollinations.ai 免费Provider
│   │   ├── sdxl_local.py             # 本地 SDXL Provider（可选）
│   │   └── stability.py              # Stability AI 付费Provider（可选）
│   ├── character/
│   │   ├── __init__.py
│   │   ├── base.py                   # CharacterConsistencyProvider 抽象基类
│   │   ├── ip_adapter.py             # IP-Adapter 本地 Provider（可选）
│   │   └── reference.py              # 参考图引导 Provider（基于 img2img）
│   ├── tts/
│   │   ├── __init__.py
│   │   ├── base.py                   # TTSProvider 抽象基类
│   │   └── edge_tts.py               # edge-tts 免费 Provider
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── base.py                   # LLMProvider 抽象基类
│   │   └── deepseek.py               # DeepSeek Provider
│   └── video/
│       ├── __init__.py
│       ├── base.py                   # VideoComposerProvider 抽象基类
│       └── ffmpeg.py                 # FFmpeg 本地 Provider
├── core/
│   └── storage.py                    # MinIO/S3 文件存储抽象
├── services/
│   ├── ai_service.py                 # AI 服务编排层（调用各引擎）
│   └── ...（已有服务）
├── api/
│   ├── ai.py                         # AI 引擎 API 路由
│   └── ...（已有路由）
├── schemas/
│   ├── ai.py                         # AI 引擎相关 Schema
│   └── ...（已有 Schema）
└── tests/
    ├── test_engines_base.py
    ├── test_pollinations.py
    ├── test_edge_tts.py
    ├── test_deepseek.py
    ├── test_ffmpeg.py
    ├── test_storage.py
    └── test_ai_api.py
```

---

## Task 1: 引擎抽象基类与基础设施

**Files:**
- Create: `c:\漫剧软件项目\backend\app\engines\__init__.py`
- Create: `c:\漫剧软件项目\backend\app\engines\base.py`
- Create: `c:\漫剧软件项目\backend\app\core\storage.py`
- Create: `c:\漫剧软件项目\backend\tests\test_engines_base.py`

- [ ] **Step 1: 创建 `app/engines/base.py` - 引擎抽象基类**

```python
"""AI 引擎抽象基类 - 所有引擎必须实现统一接口"""
from abc import ABC, abstractmethod
from typing import Any, Optional
from pathlib import Path
from dataclasses import dataclass


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

    name: str = "base"
    display_name: str = "基础引擎"

    @abstractmethod
    async def initialize(self) -> None:
        """初始化引擎（加载模型、建立连接等）"""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """健康检查"""
        ...

    def get_info(self) -> dict:
        """获取引擎信息"""
        return {
            "name": self.name,
            "display_name": self.display_name,
            "initialized": getattr(self, "_initialized", False),
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
```

- [ ] **Step 2: 创建 `app/engines/__init__.py` - 模块导出**

```python
"""AI 引擎层 - 统一导出"""
from app.engines.base import (
    BaseEngine,
    ImageGenProvider,
    TTSProvider,
    LLMProvider,
    VideoComposerProvider,
    CharacterConsistencyProvider,
    GenerationResult,
)

__all__ = [
    "BaseEngine",
    "ImageGenProvider",
    "TTSProvider",
    "LLMProvider",
    "VideoComposerProvider",
    "CharacterConsistencyProvider",
    "GenerationResult",
]
```

- [ ] **Step 3: 创建 `app/core/storage.py` - 文件存储抽象**

```python
"""文件存储抽象 - MinIO/S3 兼容"""
from pathlib import Path
from typing import Optional
import os
import uuid
from datetime import datetime


class FileStorage:
    """本地文件存储（开发环境默认）

    生产环境可替换为 MinIO/S3 实现。
    """

    def __init__(self, base_dir: str = "uploads"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save(
        self,
        data: bytes,
        filename: Optional[str] = None,
        subdir: str = "",
        extension: str = "bin",
    ) -> str:
        """保存文件，返回相对路径（作为 URL）"""
        if not filename:
            filename = f"{uuid.uuid4().hex}.{extension}"

        # 按日期分目录
        date_dir = datetime.now().strftime("%Y%m%d")
        target_dir = self.base_dir / subdir / date_dir
        target_dir.mkdir(parents=True, exist_ok=True)

        file_path = target_dir / filename
        file_path.write_bytes(data)

        # 返回相对路径作为 URL
        return f"/uploads/{subdir}/{date_dir}/{filename}".replace("//", "/")

    def get_full_path(self, relative_path: str) -> Path:
        """根据相对路径获取完整路径"""
        # 移除开头的 /uploads/
        if relative_path.startswith("/uploads/"):
            relative_path = relative_path[len("/uploads/"):]
        elif relative_path.startswith("uploads/"):
            relative_path = relative_path[len("uploads/"):]

        return self.base_dir / relative_path

    def exists(self, relative_path: str) -> bool:
        """检查文件是否存在"""
        return self.get_full_path(relative_path).exists()

    def delete(self, relative_path: str) -> bool:
        """删除文件"""
        path = self.get_full_path(relative_path)
        if path.exists():
            path.unlink()
            return True
        return False


# 全局单例
storage = FileStorage()
```

- [ ] **Step 4: 创建 `tests/test_engines_base.py` - 抽象基类测试**

```python
"""测试引擎抽象基类"""
import pytest
from app.engines.base import (
    BaseEngine,
    ImageGenProvider,
    TTSProvider,
    LLMProvider,
    GenerationResult,
)
from app.core.storage import FileStorage


def test_generation_result_dataclass():
    """测试 GenerationResult 数据类"""
    result = GenerationResult(
        success=True,
        data=b"fake-image",
        content_type="image/png",
        metadata={"model": "test"},
    )
    assert result.success is True
    assert result.data == b"fake-image"
    assert result.content_type == "image/png"
    assert result.error is None


def test_generation_result_with_error():
    """测试 GenerationResult 错误情况"""
    result = GenerationResult(
        success=False,
        data=b"",
        content_type="",
        metadata={},
        error="生成失败",
    )
    assert result.success is False
    assert result.error == "生成失败"


def test_image_gen_provider_is_abstract():
    """测试 ImageGenProvider 不能直接实例化"""
    with pytest.raises(TypeError):
        ImageGenProvider()


def test_tts_provider_is_abstract():
    """测试 TTSProvider 不能直接实例化"""
    with pytest.raises(TypeError):
        TTSProvider()


def test_llm_provider_is_abstract():
    """测试 LLMProvider 不能直接实例化"""
    with pytest.raises(TypeError):
        LLMProvider()


def test_file_storage_save_and_read(tmp_path):
    """测试文件存储"""
    storage = FileStorage(base_dir=str(tmp_path))
    data = b"test content"
    url = storage.save(data, extension="txt")

    assert url.startswith("/uploads/")
    assert url.endswith(".txt")

    # 完整路径存在
    full_path = storage.get_full_path(url)
    assert full_path.exists()
    assert full_path.read_bytes() == data


def test_file_storage_exists_and_delete(tmp_path):
    """测试文件存储存在与删除"""
    storage = FileStorage(base_dir=str(tmp_path))
    url = storage.save(b"data", filename="test.txt")

    assert storage.exists(url) is True
    assert storage.delete(url) is True
    assert storage.exists(url) is False
```

- [ ] **Step 5: 运行测试验证**

Run: `cd backend && python -m pytest tests/test_engines_base.py -v`
Expected: 7 个测试全部通过

---

## Task 2: 图像生成引擎 - Pollinations.ai 免费 Provider

**Files:**
- Create: `c:\漫剧软件项目\backend\app\engines\image\__init__.py`
- Create: `c:\漫剧软件项目\backend\app\engines\image\base.py`
- Create: `c:\漫剧软件项目\backend\app\engines\image\pollinations.py`
- Create: `c:\漫剧软件项目\backend\tests\test_pollinations.py`

- [ ] **Step 1: 创建 `app/engines/image/base.py`**

```python
"""图像生成 Provider 抽象基类（已在 engines/base.py 定义，此处重导出）"""
from app.engines.base import ImageGenProvider, GenerationResult

__all__ = ["ImageGenProvider", "GenerationResult"]
```

- [ ] **Step 2: 创建 `app/engines/image/__init__.py`**

```python
"""图像生成引擎"""
from app.engines.image.base import ImageGenProvider, GenerationResult
from app.engines.image.pollinations import PollinationsProvider


def get_default_provider() -> ImageGenProvider:
    """获取默认图像生成 Provider"""
    return PollinationsProvider()


__all__ = ["ImageGenProvider", "GenerationResult", "PollinationsProvider", "get_default_provider"]
```

- [ ] **Step 3: 创建 `app/engines/image/pollinations.py` - Pollinations.ai 免费 Provider**

```python
"""Pollinations.ai 免费图像生成 Provider

文档：https://pollinations.ai
- 无需 API Key
- 支持 text2img
- 支持多种模型（flux, turbo 等）
- 限流：每分钟约 50 次
"""
import httpx
from typing import Optional
from app.engines.base import ImageGenProvider, GenerationResult
from app.core.storage import storage


class PollinationsProvider(ImageGenProvider):
    """Pollinations.ai 免费图像生成"""

    name = "pollinations"
    display_name = "Pollinations.ai (免费)"

    BASE_URL = "https://image.pollinations.ai/prompt"
    AVAILABLE_MODELS = ["flux", "turbo", "flux-realism", "flux-anime", "flux-3d"]

    def __init__(self, timeout: int = 60):
        self.timeout = timeout
        self._initialized = False
        self.client: Optional[httpx.AsyncClient] = None

    async def initialize(self) -> None:
        """初始化 HTTP 客户端"""
        self.client = httpx.AsyncClient(timeout=self.timeout)
        self._initialized = True

    async def health_check(self) -> bool:
        """健康检查 - 简单测试连接"""
        try:
            if not self.client:
                await self.initialize()
            # 简单测试：请求一个 1x1 图像
            resp = await self.client.get(
                f"{self.BASE_URL}/test",
                params={"width": 1, "height": 1, "nologo": "true"},
            )
            return resp.status_code == 200
        except Exception:
            return False

    async def text2img(
        self,
        prompt: str,
        negative_prompt: str = "",
        width: int = 1024,
        height: int = 1024,
        seed: Optional[int] = None,
        model: str = "flux",
        nologo: bool = True,
        enhance: bool = False,
        **kwargs,
    ) -> GenerationResult:
        """
        文生图

        Args:
            prompt: 正向提示词
            negative_prompt: 负向提示词（Pollinations 通过 prompt 前缀模拟）
            width: 宽度
            height: 高度
            seed: 随机种子
            model: 模型 (flux, turbo, flux-realism, flux-anime, flux-3d)
            nologo: 是否移除 logo
            enhance: 是否增强提示词
        """
        if not self.client:
            await self.initialize()

        import time
        start_time = time.time()

        # 构造完整 prompt（Pollinations 不支持 negative_prompt，通过前缀模拟）
        full_prompt = prompt
        if negative_prompt:
            full_prompt = f"{prompt}. Avoid: {negative_prompt}"

        params = {
            "width": width,
            "height": height,
            "model": model,
            "nologo": "true" if nologo else "false",
            "enhance": "true" if enhance else "false",
        }
        if seed is not None:
            params["seed"] = seed

        try:
            # URL 编码 prompt
            from urllib.parse import quote
            url = f"{self.BASE_URL}/{quote(full_prompt)}"

            resp = await self.client.get(url, params=params)
            resp.raise_for_status()

            image_bytes = resp.content
            elapsed = time.time() - start_time

            # 保存到存储
            url_path = storage.save(image_bytes, extension="png", subdir="images")

            return GenerationResult(
                success=True,
                data=url_path,
                content_type="image/png",
                metadata={
                    "provider": self.name,
                    "model": model,
                    "width": width,
                    "height": height,
                    "seed": seed,
                    "elapsed_seconds": round(elapsed, 2),
                },
            )
        except httpx.HTTPStatusError as e:
            return GenerationResult(
                success=False,
                data=b"",
                content_type="",
                metadata={},
                error=f"HTTP {e.response.status_code}: {e.response.text[:200]}",
            )
        except Exception as e:
            return GenerationResult(
                success=False,
                data=b"",
                content_type="",
                metadata={},
                error=f"{type(e).__name__}: {str(e)}",
            )

    def get_info(self) -> dict:
        """获取引擎信息"""
        info = super().get_info()
        info["available_models"] = self.AVAILABLE_MODELS
        info["default_model"] = "flux"
        return info
```

- [ ] **Step 4: 创建 `tests/test_pollinations.py` - Provider 测试（不依赖网络）**

```python
"""测试 Pollinations Provider（使用 mock，不依赖真实网络）"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.engines.image.pollinations import PollinationsProvider
from app.engines.base import GenerationResult


@pytest.fixture
def provider():
    """Provider 实例"""
    return PollinationsProvider()


def test_provider_init(provider):
    """测试初始化"""
    assert provider.name == "pollinations"
    assert provider.display_name == "Pollinations.ai (免费)"
    assert provider._initialized is False
    assert provider.client is None


def test_provider_available_models(provider):
    """测试可用模型列表"""
    assert "flux" in provider.AVAILABLE_MODELS
    assert "turbo" in provider.AVAILABLE_MODELS


@pytest.mark.asyncio
async def test_provider_initialize(provider):
    """测试初始化"""
    await provider.initialize()
    assert provider._initialized is True
    assert provider.client is not None
    await provider.client.aclose()


@pytest.mark.asyncio
async def test_text2img_success(provider):
    """测试文生图成功（mock 网络）"""
    fake_image = b"fake-png-bytes"

    # mock httpx 客户端
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = fake_image
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    provider.client = mock_client
    provider._initialized = True

    result = await provider.text2img(
        prompt="a cute cat",
        width=512,
        height=512,
        model="flux",
    )

    assert result.success is True
    assert result.content_type == "image/png"
    assert result.metadata["provider"] == "pollinations"
    assert result.metadata["model"] == "flux"
    assert "/uploads/images/" in result.data
    assert result.error is None

    # 验证调用了正确的 URL
    mock_client.get.assert_called_once()
    call_args = mock_client.get.call_args
    assert "image.pollinations.ai" in call_args[0][0]
    assert "cute%20cat" in call_args[0][0] or "cute%20cat" in str(call_args)


@pytest.mark.asyncio
async def test_text2img_with_negative_prompt(provider):
    """测试带负面提示词的文生图"""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = b"fake"
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    provider.client = mock_client

    result = await provider.text2img(
        prompt="beautiful landscape",
        negative_prompt="blurry, low quality",
    )

    assert result.success is True
    call_url = mock_client.get.call_args[0][0]
    assert "blurry" in call_url or "low%20quality" in call_url


@pytest.mark.asyncio
async def test_text2img_http_error(provider):
    """测试 HTTP 错误"""
    import httpx

    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"
    mock_response.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError("500", request=MagicMock(), response=mock_response)
    )

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    provider.client = mock_client

    result = await provider.text2img(prompt="test")

    assert result.success is False
    assert "500" in result.error


@pytest.mark.asyncio
async def test_health_check(provider):
    """测试健康检查"""
    mock_response = MagicMock()
    mock_response.status_code = 200

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    provider.client = mock_client

    healthy = await provider.health_check()
    assert healthy is True


def test_get_info(provider):
    """测试获取引擎信息"""
    info = provider.get_info()
    assert info["name"] == "pollinations"
    assert "available_models" in info
    assert info["default_model"] == "flux"
```

- [ ] **Step 5: 运行测试**

Run: `cd backend && python -m pytest tests/test_pollinations.py -v`
Expected: 7 个测试全部通过

---

## Task 3: TTS 语音合成引擎 - edge-tts 免费 Provider

**Files:**
- Create: `c:\漫剧软件项目\backend\app\engines\tts\__init__.py`
- Create: `c:\漫剧软件项目\backend\app\engines\tts\base.py`
- Create: `c:\漫剧软件项目\backend\app\engines\tts\edge_tts.py`
- Create: `c:\漫剧软件项目\backend\tests\test_edge_tts.py`

- [ ] **Step 1: 创建 `app/engines/tts/base.py`**

```python
"""TTS Provider 抽象基类（重导出）"""
from app.engines.base import TTSProvider, GenerationResult

__all__ = ["TTSProvider", "GenerationResult"]
```

- [ ] **Step 2: 创建 `app/engines/tts/__init__.py`**

```python
"""TTS 语音合成引擎"""
from app.engines.tts.base import TTSProvider, GenerationResult
from app.engines.tts.edge_tts import EdgeTTSProvider


def get_default_provider() -> TTSProvider:
    """获取默认 TTS Provider"""
    return EdgeTTSProvider()


__all__ = ["TTSProvider", "GenerationResult", "EdgeTTSProvider", "get_default_provider"]
```

- [ ] **Step 3: 创建 `app/engines/tts/edge_tts.py` - edge-tts 免费 Provider**

```python
"""edge-tts 免费 TTS Provider

基于微软 Edge 浏览器的 TTS 服务，免费且高质量。
- 无需 API Key
- 支持多种语言和声音
- 支持 SSML
- 限流：无明确限制
"""
import io
import asyncio
from typing import Optional
from app.engines.base import TTSProvider, GenerationResult
from app.core.storage import storage


class EdgeTTSProvider(TTSProvider):
    """edge-tts 免费 TTS"""

    name = "edge_tts"
    display_name = "Edge TTS (免费)"

    # 常用中文声音
    POPULAR_VOICES = {
        "zh-CN-XiaoxiaoNeural": "晓晓（女，温柔）",
        "zh-CN-YunxiNeural": "云希（男，年轻）",
        "zh-CN-YunyangNeural": "云扬（男，新闻）",
        "zh-CN-XiaoyiNeural": "晓伊（女，活泼）",
        "zh-CN-YunjianNeural": "云健（男，运动）",
        "zh-CN-XiaohanNeural": "晓涵（女，温暖）",
        "en-US-JennyNeural": "Jenny (Female, US)",
        "en-US-GuyNeural": "Guy (Male, US)",
    }

    def __init__(self):
        self._initialized = False
        self._tts = None

    async def initialize(self) -> None:
        """初始化（延迟导入 edge_tts）"""
        try:
            import edge_tts
            self._tts = edge_tts
            self._initialized = True
        except ImportError as e:
            raise RuntimeError(
                "edge-tts 未安装，请运行: pip install edge-tts"
            ) from e

    async def health_check(self) -> bool:
        """健康检查"""
        try:
            if not self._initialized:
                await self.initialize()
            return True
        except Exception:
            return False

    async def synthesize(
        self,
        text: str,
        voice: str = "zh-CN-XiaoxiaoNeural",
        rate: int = 0,
        pitch: int = 0,
        volume: int = 0,
        **kwargs,
    ) -> GenerationResult:
        """
        文本转语音

        Args:
            text: 要合成的文本
            voice: 声音名称（见 POPULAR_VOICES）
            rate: 语速调整 (-50 到 +100)
            pitch: 音调调整 (-50 到 +50)
            volume: 音量调整 (-50 到 +50)

        Returns:
            GenerationResult: data 为音频文件 URL
        """
        import time
        start_time = time.time()

        if not self._initialized:
            await self.initialize()

        try:
            # 构造 SSML 速率/音调/音量字符串
            rate_str = f"+{rate}%" if rate >= 0 else f"{rate}%"
            pitch_str = f"+{pitch}Hz" if pitch >= 0 else f"{pitch}Hz"
            volume_str = f"+{volume}%" if volume >= 0 else f"{volume}%"

            # 创建 Communicate 对象
            communicate = self._tts.Communicate(
                text=text,
                voice=voice,
                rate=rate_str,
                pitch=pitch_str,
                volume=volume_str,
            )

            # 合成到内存
            audio_buffer = io.BytesIO()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_buffer.write(chunk["data"])

            audio_bytes = audio_buffer.getvalue()
            elapsed = time.time() - start_time

            if not audio_bytes:
                return GenerationResult(
                    success=False,
                    data=b"",
                    content_type="",
                    metadata={},
                    error="合成结果为空",
                )

            # 保存到存储
            url = storage.save(audio_bytes, extension="mp3", subdir="audio")

            return GenerationResult(
                success=True,
                data=url,
                content_type="audio/mp3",
                metadata={
                    "provider": self.name,
                    "voice": voice,
                    "text_length": len(text),
                    "audio_size": len(audio_bytes),
                    "elapsed_seconds": round(elapsed, 2),
                },
            )
        except Exception as e:
            return GenerationResult(
                success=False,
                data=b"",
                content_type="",
                metadata={},
                error=f"{type(e).__name__}: {str(e)}",
            )

    async def list_voices(self, language: Optional[str] = None) -> list[dict]:
        """列出可用声音"""
        if not self._initialized:
            await self.initialize()

        voices = await self._tts.list_voices()
        result = []
        for v in voices:
            if language and not v["Locale"].lower().startswith(language.lower()):
                continue
            result.append({
                "name": v["ShortName"],
                "locale": v["Locale"],
                "gender": v["Gender"],
                "friendly_name": v.get("FriendlyName", v["ShortName"]),
            })
        return result

    def get_info(self) -> dict:
        """获取引擎信息"""
        info = super().get_info()
        info["popular_voices"] = self.POPULAR_VOICES
        info["default_voice"] = "zh-CN-XiaoxiaoNeural"
        return info
```

- [ ] **Step 4: 创建 `tests/test_edge_tts.py` - TTS 测试（mock）**

```python
"""测试 Edge TTS Provider（使用 mock）"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.engines.tts.edge_tts import EdgeTTSProvider


@pytest.fixture
def provider():
    return EdgeTTSProvider()


def test_provider_init(provider):
    """测试初始化"""
    assert provider.name == "edge_tts"
    assert provider._initialized is False


def test_popular_voices(provider):
    """测试常用声音列表"""
    assert "zh-CN-XiaoxiaoNeural" in provider.POPULAR_VOICES
    assert "en-US-JennyNeural" in provider.POPULAR_VOICES


@pytest.mark.asyncio
async def test_initialize_success(provider):
    """测试初始化成功"""
    with patch("edge_tts", create=True) as mock_edge:
        await provider.initialize()
        assert provider._initialized is True


@pytest.mark.asyncio
async def test_synthesize_success(provider):
    """测试合成成功（mock）"""
    # 准备 mock
    fake_chunks = [
        {"type": "audio", "data": b"\xff\xfb MP3 header"},
        {"type": "audio", "data": b"audio data"},
    ]

    mock_communicate = MagicMock()
    mock_communicate.stream = AsyncMock(return_value=async_iterator(fake_chunks))

    mock_edge_tts = MagicMock()
    mock_edge_tts.Communicate = MagicMock(return_value=mock_communicate)

    provider._tts = mock_edge_tts
    provider._initialized = True

    result = await provider.synthesize(
        text="你好世界",
        voice="zh-CN-XiaoxiaoNeural",
    )

    assert result.success is True
    assert result.content_type == "audio/mp3"
    assert "/uploads/audio/" in result.data
    assert result.metadata["voice"] == "zh-CN-XiaoxiaoNeural"
    assert result.metadata["text_length"] == 4


@pytest.mark.asyncio
async def test_synthesize_empty_result(provider):
    """测试空结果"""
    mock_communicate = MagicMock()
    mock_communicate.stream = AsyncMock(return_value=async_iterator([]))

    mock_edge_tts = MagicMock()
    mock_edge_tts.Communicate = MagicMock(return_value=mock_communicate)

    provider._tts = mock_edge_tts
    provider._initialized = True

    result = await provider.synthesize(text="test")
    assert result.success is False
    assert "为空" in result.error


@pytest.mark.asyncio
async def test_synthesize_with_options(provider):
    """测试带选项的合成"""
    mock_communicate = MagicMock()
    mock_communicate.stream = AsyncMock(
        return_value=async_iterator([{"type": "audio", "data": b"audio"}])
    )

    mock_edge_tts = MagicMock()
    mock_edge_tts.Communicate = MagicMock(return_value=mock_communicate)

    provider._tts = mock_edge_tts
    provider._initialized = True

    result = await provider.synthesize(
        text="test",
        voice="en-US-JennyNeural",
        rate=20,
        pitch=-10,
    )

    assert result.success is True
    # 验证 Communicate 被调用时传入了正确的参数
    mock_edge_tts.Communicate.assert_called_once()
    call_kwargs = mock_edge_tts.Communicate.call_args.kwargs
    assert call_kwargs["voice"] == "en-US-JennyNeural"
    assert "+20%" in call_kwargs["rate"]
    assert "-10Hz" in call_kwargs["pitch"]


def test_get_info(provider):
    """测试获取信息"""
    info = provider.get_info()
    assert info["name"] == "edge_tts"
    assert "popular_voices" in info
    assert info["default_voice"] == "zh-CN-XiaoxiaoNeural"


# 辅助函数：将列表转换为异步迭代器
async def async_iterator(items):
    for item in items:
        yield item
```

- [ ] **Step 5: 运行测试**

Run: `cd backend && python -m pytest tests/test_edge_tts.py -v`
Expected: 6 个测试全部通过

---

## Task 4: LLM 大语言模型引擎 - DeepSeek Provider

**Files:**
- Create: `c:\漫剧软件项目\backend\app\engines\llm\__init__.py`
- Create: `c:\漫剧软件项目\backend\app\engines\llm\base.py`
- Create: `c:\漫剧软件项目\backend\app\engines\llm\deepseek.py`
- Create: `c:\漫剧软件项目\backend\tests\test_deepseek.py`

- [ ] **Step 1: 创建 `app/engines/llm/base.py`**

```python
"""LLM Provider 抽象基类（重导出）"""
from app.engines.base import LLMProvider, GenerationResult

__all__ = ["LLMProvider", "GenerationResult"]
```

- [ ] **Step 2: 创建 `app/engines/llm/__init__.py`**

```python
"""LLM 大语言模型引擎"""
from app.engines.llm.base import LLMProvider, GenerationResult
from app.engines.llm.deepseek import DeepSeekProvider


def get_default_provider() -> LLMProvider:
    """获取默认 LLM Provider"""
    return DeepSeekProvider()


__all__ = ["LLMProvider", "GenerationResult", "DeepSeekProvider", "get_default_provider"]
```

- [ ] **Step 3: 创建 `app/engines/llm/deepseek.py` - DeepSeek Provider**

```python
"""DeepSeek LLM Provider

基于 DeepSeek API，兼容 OpenAI 接口格式。
- 需要用户提供 API Key
- 支持多种模型（deepseek-chat, deepseek-reasoner）
- 有免费额度
"""
import httpx
from typing import Optional
from app.engines.base import LLMProvider, GenerationResult
from app.core.config import settings


class DeepSeekProvider(LLMProvider):
    """DeepSeek LLM"""

    name = "deepseek"
    display_name = "DeepSeek Chat"

    BASE_URL = "https://api.deepseek.com/v1"
    AVAILABLE_MODELS = ["deepseek-chat", "deepseek-reasoner"]

    def __init__(self, api_key: Optional[str] = None, timeout: int = 60):
        self.api_key = api_key or settings.deepseek_api_key
        self.timeout = timeout
        self._initialized = False
        self.client: Optional[httpx.AsyncClient] = None

    async def initialize(self) -> None:
        """初始化 HTTP 客户端"""
        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        self.client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers=headers,
            timeout=self.timeout,
        )
        self._initialized = True

    async def health_check(self) -> bool:
        """健康检查（简化：仅检查 client 是否建立）"""
        if not self.client:
            await self.initialize()
        return self.client is not None

    async def chat(
        self,
        messages: list[dict],
        model: str = "deepseek-chat",
        temperature: float = 0.7,
        max_tokens: int = 2000,
        stream: bool = False,
        **kwargs,
    ) -> GenerationResult:
        """
        对话生成

        Args:
            messages: 消息列表 [{"role": "system|user|assistant", "content": "..."}]
            model: 模型名称
            temperature: 温度 (0-2)
            max_tokens: 最大生成 token 数
            stream: 是否流式（暂不实现，返回完整响应）

        Returns:
            GenerationResult: data 为生成的文本
        """
        import time
        start_time = time.time()

        if not self.client:
            await self.initialize()

        if not self.api_key:
            return GenerationResult(
                success=False,
                data="",
                content_type="text/plain",
                metadata={},
                error="未配置 DEEPSEEK_API_KEY，请在 .env 中设置",
            )

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
            **kwargs,
        }

        try:
            resp = await self.client.post("/chat/completions", json=payload)
            resp.raise_for_status()
            data = resp.json()
            elapsed = time.time() - start_time

            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})

            return GenerationResult(
                success=True,
                data=content,
                content_type="text/plain",
                metadata={
                    "provider": self.name,
                    "model": model,
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                    "total_tokens": usage.get("total_tokens", 0),
                    "elapsed_seconds": round(elapsed, 2),
                },
            )
        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP {e.response.status_code}"
            try:
                error_data = e.response.json()
                error_msg += f": {error_data.get('error', {}).get('message', '')}"
            except Exception:
                error_msg += f": {e.response.text[:200]}"

            return GenerationResult(
                success=False,
                data="",
                content_type="text/plain",
                metadata={},
                error=error_msg,
            )
        except Exception as e:
            return GenerationResult(
                success=False,
                data="",
                content_type="text/plain",
                metadata={},
                error=f"{type(e).__name__}: {str(e)}",
            )

    async def generate_script(
        self,
        theme: str,
        style: str = "anime",
        num_scenes: int = 5,
        **kwargs,
    ) -> GenerationResult:
        """生成漫剧剧本（封装的便捷方法）"""
        system_prompt = """你是一位专业的漫剧编剧，擅长创作引人入胜的短剧剧本。
请根据用户提供的主题，生成结构完整的漫剧剧本。

输出 JSON 格式：
{
  "title": "剧本标题",
  "description": "剧本简介",
  "genre": "类型",
  "scenes": [
    {
      "scene_number": 1,
      "title": "场景标题",
      "location": "场景地点",
      "time_of_day": "时间（日/夜/黄昏）",
      "description": "场景描述",
      "mood": "氛围",
      "dialogues": [
        {
          "character": "角色名",
          "content": "对话内容",
          "emotion": "情感"
        }
      ]
    }
  ]
}"""

        user_prompt = f"""主题：{theme}
风格：{style}
场景数：{num_scenes}

请生成一个完整的漫剧剧本。"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        return await self.chat(messages, **kwargs)

    def get_info(self) -> dict:
        info = super().get_info()
        info["available_models"] = self.AVAILABLE_MODELS
        info["default_model"] = "deepseek-chat"
        info["api_key_configured"] = bool(self.api_key)
        return info
```

- [ ] **Step 4: 创建 `tests/test_deepseek.py`**

```python
"""测试 DeepSeek Provider（mock）"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.engines.llm.deepseek import DeepSeekProvider
from app.engines.base import GenerationResult


@pytest.fixture
def provider():
    return DeepSeekProvider(api_key="test-key")


def test_provider_init(provider):
    assert provider.name == "deepseek"
    assert provider.api_key == "test-key"
    assert provider._initialized is False


def test_available_models(provider):
    assert "deepseek-chat" in provider.AVAILABLE_MODELS
    assert "deepseek-reasoner" in provider.AVAILABLE_MODELS


@pytest.mark.asyncio
async def test_initialize(provider):
    await provider.initialize()
    assert provider._initialized is True
    assert provider.client is not None
    await provider.client.aclose()


@pytest.mark.asyncio
async def test_chat_success(provider):
    """测试对话成功"""
    fake_response = {
        "choices": [
            {"message": {"content": "你好，我是 AI 助手"}}
        ],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 8,
            "total_tokens": 18,
        },
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json = MagicMock(return_value=fake_response)
    mock_resp.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_resp)
    provider.client = mock_client
    provider._initialized = True

    result = await provider.chat(
        messages=[{"role": "user", "content": "你好"}],
        model="deepseek-chat",
    )

    assert result.success is True
    assert result.data == "你好，我是 AI 助手"
    assert result.metadata["model"] == "deepseek-chat"
    assert result.metadata["total_tokens"] == 18


@pytest.mark.asyncio
async def test_chat_no_api_key():
    """测试无 API Key"""
    provider = DeepSeekProvider(api_key="")
    result = await provider.chat(messages=[{"role": "user", "content": "hi"}])

    assert result.success is False
    assert "DEEPSEEK_API_KEY" in result.error


@pytest.mark.asyncio
async def test_chat_http_error(provider):
    """测试 HTTP 错误"""
    import httpx

    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_resp.text = "Unauthorized"
    mock_resp.json = MagicMock(side_effect=ValueError("not json"))
    mock_resp.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError("401", request=MagicMock(), response=mock_resp)
    )

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_resp)
    provider.client = mock_client
    provider._initialized = True

    result = await provider.chat(messages=[{"role": "user", "content": "hi"}])

    assert result.success is False
    assert "401" in result.error


@pytest.mark.asyncio
async def test_generate_script(provider):
    """测试剧本生成"""
    fake_response = {
        "choices": [
            {"message": {"content": '{"title":"测试剧本","scenes":[]}'}}
        ],
        "usage": {"total_tokens": 100},
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json = MagicMock(return_value=fake_response)
    mock_resp.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_resp)
    provider.client = mock_client
    provider._initialized = True

    result = await provider.generate_script(theme="校园恋爱", num_scenes=3)

    assert result.success is True
    assert "title" in result.data

    # 验证调用参数
    mock_client.post.assert_called_once()
    payload = mock_client.post.call_args.kwargs["json"]
    assert payload["messages"][0]["role"] == "system"
    assert "校园恋爱" in payload["messages"][1]["content"]


def test_get_info(provider):
    info = provider.get_info()
    assert info["name"] == "deepseek"
    assert info["api_key_configured"] is True
    assert info["default_model"] == "deepseek-chat"
```

- [ ] **Step 5: 运行测试**

Run: `cd backend && python -m pytest tests/test_deepseek.py -v`
Expected: 7 个测试全部通过

---

## Task 5: 视频合成引擎 - FFmpeg Provider

**Files:**
- Create: `c:\漫剧软件项目\backend\app\engines\video\__init__.py`
- Create: `c:\漫剧软件项目\backend\app\engines\video\base.py`
- Create: `c:\漫剧软件项目\backend\app\engines\video\ffmpeg.py`
- Create: `c:\漫剧软件项目\backend\tests\test_ffmpeg.py`

- [ ] **Step 1: 创建 `app/engines/video/base.py`**

```python
"""Video Composer Provider 抽象基类（重导出）"""
from app.engines.base import VideoComposerProvider, GenerationResult

__all__ = ["VideoComposerProvider", "GenerationResult"]
```

- [ ] **Step 2: 创建 `app/engines/video/__init__.py`**

```python
"""视频合成引擎"""
from app.engines.video.base import VideoComposerProvider, GenerationResult
from app.engines.video.ffmpeg import FFmpegProvider


def get_default_provider() -> VideoComposerProvider:
    return FFmpegProvider()


__all__ = ["VideoComposerProvider", "GenerationResult", "FFmpegProvider", "get_default_provider"]
```

- [ ] **Step 3: 创建 `app/engines/video/ffmpeg.py` - FFmpeg Provider**

```python
"""FFmpeg 视频合成 Provider

基于 FFmpeg 命令行工具，本地执行。
- 需要 FFmpeg 已安装并加入 PATH
- 支持图像序列合成视频
- 支持添加背景音乐
- 支持转场效果
"""
import asyncio
import tempfile
from pathlib import Path
from typing import Optional
from app.engines.base import VideoComposerProvider, GenerationResult
from app.core.storage import storage


class FFmpegProvider(VideoComposerProvider):
    """FFmpeg 视频合成"""

    name = "ffmpeg"
    display_name = "FFmpeg (本地)"

    def __init__(self):
        self._initialized = False
        self._ffmpeg_path = "ffmpeg"

    async def initialize(self) -> None:
        """初始化（检测 FFmpeg 是否可用）"""
        try:
            proc = await asyncio.create_subprocess_exec(
                self._ffmpeg_path, "-version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.wait()
            self._initialized = proc.returncode == 0
            if not self._initialized:
                raise RuntimeError("FFmpeg 返回非零退出码")
        except FileNotFoundError:
            raise RuntimeError(
                "FFmpeg 未安装或不在 PATH 中。请安装 FFmpeg: https://ffmpeg.org/download.html"
            )

    async def health_check(self) -> bool:
        """健康检查"""
        try:
            if not self._initialized:
                await self.initialize()
            return True
        except Exception:
            return False

    async def compose(
        self,
        frames: list[str],
        audio: Optional[str] = None,
        output_path: str = "output.mp4",
        fps: int = 24,
        resolution: tuple[int, int] = (1920, 1080),
        duration_per_frame: float = 2.0,
        transition: str = "none",
        **kwargs,
    ) -> GenerationResult:
        """
        合成视频

        Args:
            frames: 图像路径或 URL 列表
            audio: 背景音乐路径或 URL（可选）
            output_path: 输出文件名
            fps: 帧率
            resolution: 分辨率 (width, height)
            duration_per_frame: 每帧持续时间（秒）
            transition: 转场效果（none, fade, dissolve）

        Returns:
            GenerationResult: data 为视频文件 URL
        """
        import time
        start_time = time.time()

        if not self._initialized:
            await self.initialize()

        if not frames:
            return GenerationResult(
                success=False,
                data="",
                content_type="",
                metadata={},
                error="帧列表为空",
            )

        try:
            # 下载远程图像（如果是 URL）
            local_frames = await self._prepare_frames(frames)

            # 创建临时目录
            with tempfile.TemporaryDirectory() as tmp_dir:
                tmp_path = Path(tmp_dir)

                # 创建 concat 文件
                concat_file = tmp_path / "concat.txt"
                concat_content = []
                for i, frame_path in enumerate(local_frames):
                    # 计算每帧持续时间
                    duration = duration_per_frame
                    concat_content.append(f"file '{frame_path}'")
                    concat_content.append(f"duration {duration}")
                    # 最后一帧需要重复一次（FFmpeg 要求）
                    if i == len(local_frames) - 1:
                        concat_content.append(f"file '{frame_path}'")

                concat_file.write_text("\n".join(concat_content))

                # 输出文件
                output_file = tmp_path / "output.mp4"

                # 构造 FFmpeg 命令
                cmd = [
                    self._ffmpeg_path,
                    "-y",  # 覆盖输出
                    "-f", "concat",
                    "-safe", "0",
                    "-i", str(concat_file),
                    "-vf",
                    f"scale={resolution[0]}:{resolution[1]}:force_original_aspect_ratio=decrease,"
                    f"pad={resolution[0]}:{resolution[1]}:(ow-iw)/2:(oh-ih)/2",
                    "-r", str(fps),
                    "-c:v", "libx264",
                    "-pix_fmt", "yuv420p",
                    "-preset", "fast",
                    "-crf", "23",
                ]

                # 添加音频
                if audio:
                    local_audio = await self._download_if_url(audio, tmp_path / "audio")
                    cmd.extend(["-i", str(local_audio), "-c:a", "aac", "-b:a", "128k"])
                    # 音频短于视频时循环，长于视频时截断
                    cmd.extend(["-shortest"])

                cmd.append(str(output_file))

                # 执行 FFmpeg
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await proc.communicate()

                if proc.returncode != 0:
                    return GenerationResult(
                        success=False,
                        data="",
                        content_type="",
                        metadata={},
                        error=f"FFmpeg 错误: {stderr.decode()[:500]}",
                    )

                # 读取输出文件
                video_bytes = output_file.read_bytes()
                elapsed = time.time() - start_time

                # 保存到存储
                url = storage.save(video_bytes, extension="mp4", subdir="videos")

                return GenerationResult(
                    success=True,
                    data=url,
                    content_type="video/mp4",
                    metadata={
                        "provider": self.name,
                        "frame_count": len(frames),
                        "fps": fps,
                        "resolution": f"{resolution[0]}x{resolution[1]}",
                        "duration_seconds": len(frames) * duration_per_frame,
                        "video_size": len(video_bytes),
                        "has_audio": audio is not None,
                        "elapsed_seconds": round(elapsed, 2),
                    },
                )
        except Exception as e:
            return GenerationResult(
                success=False,
                data="",
                content_type="",
                metadata={},
                error=f"{type(e).__name__}: {str(e)}",
            )

    async def _prepare_frames(self, frames: list[str]) -> list[str]:
        """准备本地帧路径（下载远程图像）"""
        local_paths = []
        for i, frame in enumerate(frames):
            if frame.startswith(("http://", "https://")):
                # 下载远程图像
                local_path = await self._download_if_url(
                    frame, Path(tempfile.gettempdir()) / f"frame_{i:06d}.png"
                )
                local_paths.append(str(local_path))
            else:
                # 本地路径
                local_paths.append(str(storage.get_full_path(frame)))
        return local_paths

    async def _download_if_url(self, url_or_path: str, target_path: Path) -> Path:
        """如果是 URL 则下载，否则返回本地路径"""
        if url_or_path.startswith(("http://", "https://")):
            import httpx
            async with httpx.AsyncClient() as client:
                resp = await client.get(url_or_path)
                resp.raise_for_status()
                target_path.write_bytes(resp.content)
            return target_path
        else:
            # 本地路径，直接返回
            return storage.get_full_path(url_or_path)

    def get_info(self) -> dict:
        info = super().get_info()
        info["ffmpeg_path"] = self._ffmpeg_path
        return info
```

- [ ] **Step 4: 创建 `tests/test_ffmpeg.py` - FFmpeg 测试（mock subprocess）**

```python
"""测试 FFmpeg Provider（mock subprocess，不依赖真实 FFmpeg）"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.engines.video.ffmpeg import FFmpegProvider


@pytest.fixture
def provider():
    return FFmpegProvider()


def test_provider_init(provider):
    assert provider.name == "ffmpeg"
    assert provider._initialized is False
    assert provider._ffmpeg_path == "ffmpeg"


@pytest.mark.asyncio
async def test_initialize_success(provider):
    """测试初始化成功"""
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.wait = AsyncMock(return_value=0)

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        await provider.initialize()
        assert provider._initialized is True


@pytest.mark.asyncio
async def test_initialize_not_found(provider):
    """测试 FFmpeg 未安装"""
    with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError()):
        with pytest.raises(RuntimeError, match="未安装"):
            await provider.initialize()


@pytest.mark.asyncio
async def test_compose_empty_frames(provider):
    """测试空帧列表"""
    provider._initialized = True
    result = await provider.compose(frames=[])
    assert result.success is False
    assert "为空" in result.error


@pytest.mark.asyncio
async def test_compose_success(provider):
    """测试合成成功（mock subprocess + 临时文件）"""
    provider._initialized = True

    # mock _prepare_frames 返回本地路径
    provider._prepare_frames = AsyncMock(return_value=["/tmp/frame1.png"])

    # mock subprocess
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.communicate = AsyncMock(return_value=(b"stdout", b"stderr"))

    # mock output 文件存在
    def mock_write_bytes(data):
        pass

    # mock 临时目录与文件
    mock_output_file = MagicMock()
    mock_output_file.read_bytes = MagicMock(return_value=b"fake-video")

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        with patch("tempfile.TemporaryDirectory") as mock_tmp:
            # 模拟临时目录上下文
            mock_tmp_instance = MagicMock()
            mock_tmp_instance.__enter__ = MagicMock(return_value=Path("/tmp/test"))
            mock_tmp_instance.__exit__ = MagicMock(return_value=False)
            mock_tmp.return_value = mock_tmp_instance

            with patch("pathlib.Path.write_text"):
                with patch("pathlib.Path.read_bytes", return_value=b"fake-video"):
                    result = await provider.compose(
                        frames=["frame1.png"],
                        fps=24,
                        resolution=(1280, 720),
                        duration_per_frame=2.0,
                    )

    assert result.success is True
    assert result.content_type == "video/mp4"
    assert result.metadata["frame_count"] == 1
    assert result.metadata["fps"] == 24
    assert result.metadata["duration_seconds"] == 2.0


@pytest.mark.asyncio
async def test_compose_ffmpeg_error(provider):
    """测试 FFmpeg 执行错误"""
    provider._initialized = True
    provider._prepare_frames = AsyncMock(return_value=["/tmp/frame1.png"])

    mock_proc = MagicMock()
    mock_proc.returncode = 1
    mock_proc.communicate = AsyncMock(
        return_value=(b"", b"FFmpeg error: invalid codec")
    )

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        with patch("tempfile.TemporaryDirectory"):
            with patch("pathlib.Path.write_text"):
                result = await provider.compose(frames=["frame1.png"])

    assert result.success is False
    assert "FFmpeg 错误" in result.error


def test_get_info(provider):
    info = provider.get_info()
    assert info["name"] == "ffmpeg"
    assert info["ffmpeg_path"] == "ffmpeg"
```

- [ ] **Step 5: 运行测试**

Run: `cd backend && python -m pytest tests/test_ffmpeg.py -v`
Expected: 6 个测试全部通过

---

## Task 6: 角色一致性引擎 - 参考图引导 Provider

**Files:**
- Create: `c:\漫剧软件项目\backend\app\engines\character\__init__.py`
- Create: `c:\漫剧软件项目\backend\app\engines\character\base.py`
- Create: `c:\漫剧软件项目\backend\app\engines\character\reference.py`
- Create: `c:\漫剧软件项目\backend\tests\test_character_engine.py`

- [ ] **Step 1: 创建 `app/engines/character/base.py`**

```python
"""Character Consistency Provider 抽象基类（重导出）"""
from app.engines.base import CharacterConsistencyProvider, GenerationResult

__all__ = ["CharacterConsistencyProvider", "GenerationResult"]
```

- [ ] **Step 2: 创建 `app/engines/character/__init__.py`**

```python
"""角色一致性引擎"""
from app.engines.character.base import CharacterConsistencyProvider, GenerationResult
from app.engines.character.reference import ReferenceBasedProvider


def get_default_provider() -> CharacterConsistencyProvider:
    return ReferenceBasedProvider()


__all__ = ["CharacterConsistencyProvider", "GenerationResult", "ReferenceBasedProvider", "get_default_provider"]
```

- [ ] **Step 3: 创建 `app/engines/character/reference.py` - 参考图引导 Provider**

```python
"""参考图引导角色一致性 Provider

零成本方案：基于 Pollinations.ai 的图像生成 + LLM 提示词增强。
- 通过 LLM 提取参考图的角色特征描述
- 将特征描述融入生成 prompt
- 实现软一致性（不依赖 LoRA / IP-Adapter）

未来可扩展：
- IPAdapterProvider：本地 IP-Adapter（需 GPU）
- LoRAProvider：角色专属 LoRA 微调
"""
import base64
import httpx
from typing import Optional
from app.engines.base import CharacterConsistencyProvider, GenerationResult
from app.engines.image.pollinations import PollinationsProvider
from app.engines.llm.deepseek import DeepSeekProvider
from app.core.storage import storage


class ReferenceBasedProvider(CharacterConsistencyProvider):
    """参考图引导的角色一致性"""

    name = "reference_based"
    display_name = "参考图引导（免费）"

    def __init__(
        self,
        image_provider: Optional[PollinationsProvider] = None,
        llm_provider: Optional[DeepSeekProvider] = None,
    ):
        self.image_provider = image_provider or PollinationsProvider()
        self.llm_provider = llm_provider or DeepSeekProvider()
        self._initialized = False

    async def initialize(self) -> None:
        """初始化子 Provider"""
        await self.image_provider.initialize()
        # LLM provider 可能需要 API key，延迟初始化
        self._initialized = True

    async def health_check(self) -> bool:
        """健康检查"""
        try:
            if not self._initialized:
                await self.initialize()
            return await self.image_provider.health_check()
        except Exception:
            return False

    async def extract_features(self, image: bytes) -> list[float]:
        """提取特征向量（简化版：返回哈希作为伪特征）

        完整实现需要 CLIP 模型，此处提供降级方案。
        """
        import hashlib
        hash_obj = hashlib.sha256(image).hexdigest()
        # 将哈希转为 512 维伪特征向量（仅占位）
        return [float(int(hash_obj[i:i+2], 16) / 255) for i in range(0, 512, 2)][:512]

    async def describe_character(self, image: bytes) -> str:
        """使用 LLM 描述角色特征（如果 LLM 支持图像输入）

        当前 DeepSeek 不支持图像输入，返回默认描述。
        未来可替换为支持视觉的模型。
        """
        # 降级方案：返回通用角色描述模板
        return "anime style character, consistent appearance, detailed features"

    async def generate_consistent(
        self,
        prompt: str,
        reference_image: bytes,
        consistency_weight: float = 0.8,
        width: int = 1024,
        height: int = 1024,
        **kwargs,
    ) -> GenerationResult:
        """
        基于参考图生成一致性角色

        策略：
        1. 从参考图提取角色特征描述
        2. 将特征描述融入生成 prompt
        3. 使用相同 seed 保持风格一致

        Args:
            prompt: 生成提示词
            reference_image: 参考图（bytes）
            consistency_weight: 一致性权重 (0-1)
        """
        import time
        start_time = time.time()

        if not self._initialized:
            await self.initialize()

        try:
            # 1. 提取角色描述
            character_desc = await self.describe_character(reference_image)

            # 2. 融合 prompt
            # 一致性权重越高，角色描述越突出
            if consistency_weight > 0.5:
                enhanced_prompt = f"{character_desc}, {prompt}, same character, consistent appearance"
            else:
                enhanced_prompt = f"{prompt}, {character_desc}"

            # 3. 生成图像
            result = await self.image_provider.text2img(
                prompt=enhanced_prompt,
                width=width,
                height=height,
                **kwargs,
            )

            if not result.success:
                return result

            # 补充元数据
            elapsed = time.time() - start_time
            result.metadata.update({
                "provider": self.name,
                "consistency_weight": consistency_weight,
                "character_desc_length": len(character_desc),
                "elapsed_seconds": round(elapsed, 2),
            })

            return result

        except Exception as e:
            return GenerationResult(
                success=False,
                data=b"",
                content_type="",
                metadata={},
                error=f"{type(e).__name__}: {str(e)}",
            )

    def get_info(self) -> dict:
        info = super().get_info()
        info["strategy"] = "reference_guided"
        info["note"] = "软一致性方案，未来可扩展为 IP-Adapter / LoRA"
        return info
```

- [ ] **Step 4: 创建 `tests/test_character_engine.py`**

```python
"""测试角色一致性引擎"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.engines.character.reference import ReferenceBasedProvider
from app.engines.base import GenerationResult


@pytest.fixture
def provider():
    return ReferenceBasedProvider()


def test_provider_init(provider):
    assert provider.name == "reference_based"
    assert provider._initialized is False


def test_get_info(provider):
    info = provider.get_info()
    assert info["strategy"] == "reference_guided"


@pytest.mark.asyncio
async def test_extract_features(provider):
    """测试特征提取"""
    fake_image = b"fake image bytes"
    features = await provider.extract_features(fake_image)

    assert isinstance(features, list)
    assert len(features) == 256  # 512/2
    assert all(0 <= f <= 1 for f in features)


@pytest.mark.asyncio
async def test_describe_character(provider):
    """测试角色描述（降级方案）"""
    desc = await provider.describe_character(b"image")
    assert isinstance(desc, str)
    assert "character" in desc.lower()


@pytest.mark.asyncio
async def test_generate_consistent_success(provider):
    """测试一致性生成成功"""
    # mock image provider
    fake_result = GenerationResult(
        success=True,
        data="/uploads/images/test.png",
        content_type="image/png",
        metadata={"model": "flux"},
    )
    provider.image_provider.text2img = AsyncMock(return_value=fake_result)
    provider.image_provider.initialize = AsyncMock()
    provider._initialized = True

    result = await provider.generate_consistent(
        prompt="a girl in school uniform",
        reference_image=b"ref image",
        consistency_weight=0.8,
    )

    assert result.success is True
    assert result.metadata["provider"] == "reference_based"
    assert result.metadata["consistency_weight"] == 0.8

    # 验证 prompt 被增强
    call_kwargs = provider.image_provider.text2img.call_args.kwargs
    assert "consistent appearance" in call_kwargs["prompt"]


@pytest.mark.asyncio
async def test_generate_consistent_low_weight(provider):
    """测试低一致性权重"""
    fake_result = GenerationResult(
        success=True,
        data="/uploads/test.png",
        content_type="image/png",
        metadata={},
    )
    provider.image_provider.text2img = AsyncMock(return_value=fake_result)
    provider._initialized = True

    await provider.generate_consistent(
        prompt="test",
        reference_image=b"ref",
        consistency_weight=0.3,
    )

    call_kwargs = provider.image_provider.text2img.call_args.kwargs
    # 低权重时不应包含 "same character"
    assert "same character" not in call_kwargs["prompt"]


@pytest.mark.asyncio
async def test_generate_consistent_image_error(provider):
    """测试图像生成失败"""
    fake_result = GenerationResult(
        success=False,
        data=b"",
        content_type="",
        metadata={},
        error="网络错误",
    )
    provider.image_provider.text2img = AsyncMock(return_value=fake_result)
    provider._initialized = True

    result = await provider.generate_consistent(
        prompt="test",
        reference_image=b"ref",
    )

    assert result.success is False
    assert result.error == "网络错误"


@pytest.mark.asyncio
async def test_health_check(provider):
    """测试健康检查"""
    provider.image_provider.initialize = AsyncMock()
    provider.image_provider.health_check = AsyncMock(return_value=True)

    healthy = await provider.health_check()
    assert healthy is True
```

- [ ] **Step 5: 运行测试**

Run: `cd backend && python -m pytest tests/test_character_engine.py -v`
Expected: 7 个测试全部通过

---

## Task 7: 引擎管理器 EngineManager

**Files:**
- Create: `c:\漫剧软件项目\backend\app\engines\manager.py`
- Modify: `c:\漫剧软件项目\backend\app\engines\__init__.py`
- Create: `c:\漫剧软件项目\backend\tests\test_engine_manager.py`

- [ ] **Step 1: 创建 `app/engines/manager.py` - 引擎管理器**

```python
"""引擎管理器 - 统一管理所有 AI 引擎"""
from typing import Optional
from app.engines.base import (
    ImageGenProvider,
    TTSProvider,
    LLMProvider,
    VideoComposerProvider,
    CharacterConsistencyProvider,
)
from app.engines.image.pollinations import PollinationsProvider
from app.engines.tts.edge_tts import EdgeTTSProvider
from app.engines.llm.deepseek import DeepSeekProvider
from app.engines.video.ffmpeg import FFmpegProvider
from app.engines.character.reference import ReferenceBasedProvider


class EngineManager:
    """AI 引擎管理器（单例）

    统一管理所有引擎的初始化、健康检查、信息查询。
    """

    def __init__(self):
        self._image_provider: Optional[ImageGenProvider] = None
        self._tts_provider: Optional[TTSProvider] = None
        self._llm_provider: Optional[LLMProvider] = None
        self._video_provider: Optional[VideoComposerProvider] = None
        self._character_provider: Optional[CharacterConsistencyProvider] = None
        self._initialized = False

    async def initialize_all(self) -> None:
        """初始化所有引擎"""
        # 图像引擎（必选）
        self._image_provider = PollinationsProvider()
        await self._image_provider.initialize()

        # TTS 引擎（必选）
        self._tts_provider = EdgeTTSProvider()
        # edge_tts 延迟初始化，不在此处报错

        # LLM 引擎（可选，需 API Key）
        self._llm_provider = DeepSeekProvider()

        # 视频引擎（可选，需 FFmpeg）
        self._video_provider = FFmpegProvider()

        # 角色一致性引擎
        self._character_provider = ReferenceBasedProvider(
            image_provider=self._image_provider,
            llm_provider=self._llm_provider,
        )

        self._initialized = True

    @property
    def image(self) -> ImageGenProvider:
        if not self._image_provider:
            raise RuntimeError("图像引擎未初始化，请先调用 initialize_all()")
        return self._image_provider

    @property
    def tts(self) -> TTSProvider:
        if not self._tts_provider:
            raise RuntimeError("TTS 引擎未初始化")
        return self._tts_provider

    @property
    def llm(self) -> LLMProvider:
        if not self._llm_provider:
            raise RuntimeError("LLM 引擎未初始化")
        return self._llm_provider

    @property
    def video(self) -> VideoComposerProvider:
        if not self._video_provider:
            raise RuntimeError("视频引擎未初始化")
        return self._video_provider

    @property
    def character(self) -> CharacterConsistencyProvider:
        if not self._character_provider:
            raise RuntimeError("角色一致性引擎未初始化")
        return self._character_provider

    async def health_check_all(self) -> dict:
        """所有引擎健康检查"""
        results = {}
        for name, provider in [
            ("image", self._image_provider),
            ("tts", self._tts_provider),
            ("llm", self._llm_provider),
            ("video", self._video_provider),
            ("character", self._character_provider),
        ]:
            if provider is None:
                results[name] = {"healthy": False, "error": "未初始化"}
            else:
                try:
                    healthy = await provider.health_check()
                    results[name] = {"healthy": healthy, "info": provider.get_info()}
                except Exception as e:
                    results[name] = {"healthy": False, "error": str(e)}
        return results

    def get_all_info(self) -> dict:
        """获取所有引擎信息"""
        info = {}
        for name, provider in [
            ("image", self._image_provider),
            ("tts", self._tts_provider),
            ("llm", self._llm_provider),
            ("video", self._video_provider),
            ("character", self._character_provider),
        ]:
            if provider:
                info[name] = provider.get_info()
            else:
                info[name] = None
        return info


# 全局单例
engine_manager = EngineManager()
```

- [ ] **Step 2: 更新 `app/engines/__init__.py` 导出 EngineManager**

```python
"""AI 引擎层 - 统一导出"""
from app.engines.base import (
    BaseEngine,
    ImageGenProvider,
    TTSProvider,
    LLMProvider,
    VideoComposerProvider,
    CharacterConsistencyProvider,
    GenerationResult,
)
from app.engines.manager import EngineManager, engine_manager

__all__ = [
    "BaseEngine",
    "ImageGenProvider",
    "TTSProvider",
    "LLMProvider",
    "VideoComposerProvider",
    "CharacterConsistencyProvider",
    "GenerationResult",
    "EngineManager",
    "engine_manager",
]
```

- [ ] **Step 3: 创建 `tests/test_engine_manager.py`**

```python
"""测试引擎管理器"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.engines.manager import EngineManager
from app.engines.base import GenerationResult


@pytest.fixture
def manager():
    return EngineManager()


def test_manager_init(manager):
    """测试初始化"""
    assert manager._initialized is False
    assert manager._image_provider is None


def test_access_before_init_raises(manager):
    """测试未初始化时访问抛出异常"""
    with pytest.raises(RuntimeError, match="未初始化"):
        _ = manager.image


@pytest.mark.asyncio
async def test_initialize_all(manager):
    """测试初始化所有引擎"""
    with patch("app.engines.manager.EdgeTTSProvider"):
        with patch("app.engines.manager.PollinationsProvider") as mock_img:
            mock_instance = MagicMock()
            mock_instance.initialize = AsyncMock()
            mock_img.return_value = mock_instance

            await manager.initialize_all()

            assert manager._initialized is True
            assert manager._image_provider is not None
            assert manager._tts_provider is not None
            assert manager._llm_provider is not None
            assert manager._video_provider is not None
            assert manager._character_provider is not None


@pytest.mark.asyncio
async def test_health_check_all(manager):
    """测试所有健康检查"""
    # 设置 mock providers
    manager._image_provider = MagicMock()
    manager._image_provider.health_check = AsyncMock(return_value=True)
    manager._image_provider.get_info = MagicMock(return_value={"name": "image"})

    manager._tts_provider = MagicMock()
    manager._tts_provider.health_check = AsyncMock(return_value=True)
    manager._tts_provider.get_info = MagicMock(return_value={"name": "tts"})

    manager._llm_provider = MagicMock()
    manager._llm_provider.health_check = AsyncMock(return_value=False)
    manager._llm_provider.get_info = MagicMock(return_value={"name": "llm"})

    manager._video_provider = None
    manager._character_provider = None

    results = await manager.health_check_all()

    assert results["image"]["healthy"] is True
    assert results["tts"]["healthy"] is True
    assert results["llm"]["healthy"] is False
    assert results["video"]["healthy"] is False
    assert "未初始化" in results["video"]["error"]


def test_get_all_info(manager):
    """测试获取所有信息"""
    manager._image_provider = MagicMock()
    manager._image_provider.get_info = MagicMock(return_value={"name": "pollinations"})

    manager._tts_provider = None

    info = manager.get_all_info()
    assert info["image"]["name"] == "pollinations"
    assert info["tts"] is None


# import patch at top
from unittest.mock import patch
```

- [ ] **Step 4: 运行测试**

Run: `cd backend && python -m pytest tests/test_engine_manager.py -v`
Expected: 5 个测试全部通过

---

## Task 8: AI Schemas 与 API 路由

**Files:**
- Create: `c:\漫剧软件项目\backend\app\schemas\ai.py`
- Create: `c:\漫剧软件项目\backend\app\api\ai.py`
- Modify: `c:\漫剧软件项目\backend\app\api\router.py` - 添加 AI 路由
- Modify: `c:\漫剧软件项目\backend\app\main.py` - lifespan 初始化引擎
- Create: `c:\漫剧软件项目\backend\tests\test_ai_api.py`

- [ ] **Step 1: 创建 `app/schemas/ai.py` - AI 请求/响应 Schema**

```python
"""AI 引擎相关 Schema"""
from pydantic import BaseModel, Field
from typing import Optional, Any


class Text2ImgRequest(BaseModel):
    """文生图请求"""
    prompt: str = Field(..., description="正向提示词", min_length=1, max_length=2000)
    negative_prompt: str = Field("", description="负面提示词", max_length=1000)
    width: int = Field(1024, ge=64, le=2048, description="宽度")
    height: int = Field(1024, ge=64, le=2048, description="高度")
    seed: Optional[int] = Field(None, ge=0, le=2**32-1, description="随机种子")
    model: str = Field("flux", description="模型名称")


class TTSRequest(BaseModel):
    """TTS 请求"""
    text: str = Field(..., description="要合成的文本", min_length=1, max_length=5000)
    voice: str = Field("zh-CN-XiaoxiaoNeural", description="声音名称")
    rate: int = Field(0, ge=-50, le=100, description="语速调整")
    pitch: int = Field(0, ge=-50, le=50, description="音调调整")
    volume: int = Field(0, ge=-50, le=50, description="音量调整")


class ChatRequest(BaseModel):
    """LLM 对话请求"""
    messages: list[dict] = Field(..., description="消息列表")
    model: str = Field("deepseek-chat", description="模型")
    temperature: float = Field(0.7, ge=0, le=2)
    max_tokens: int = Field(2000, ge=1, le=8192)


class ScriptGenerateRequest(BaseModel):
    """剧本生成请求"""
    theme: str = Field(..., description="主题", min_length=1)
    style: str = Field("anime", description="风格")
    num_scenes: int = Field(5, ge=1, le=20, description="场景数")


class VideoComposeRequest(BaseModel):
    """视频合成请求"""
    frames: list[str] = Field(..., description="帧图像 URL 列表", min_items=1)
    audio: Optional[str] = Field(None, description="背景音乐 URL")
    fps: int = Field(24, ge=1, le=60)
    resolution: tuple[int, int] = Field((1920, 1080), description="分辨率")
    duration_per_frame: float = Field(2.0, ge=0.1, le=60)


class CharacterConsistencyRequest(BaseModel):
    """角色一致性生成请求"""
    prompt: str = Field(..., description="生成提示词")
    reference_image: str = Field(..., description="参考图 URL 或 base64")
    consistency_weight: float = Field(0.8, ge=0, le=1)


class EngineInfoResponse(BaseModel):
    """引擎信息响应"""
    name: str
    display_name: str
    initialized: bool
    available_models: Optional[list[str]] = None
    default_model: Optional[str] = None
    extra: dict = Field(default_factory=dict)
```

- [ ] **Step 2: 创建 `app/api/ai.py` - AI API 路由**

```python
"""AI 引擎 API 路由"""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse
from pathlib import Path

from app.api.deps import get_current_user
from app.core.response import ApiResponse
from app.schemas.ai import (
    Text2ImgRequest,
    TTSRequest,
    ChatRequest,
    ScriptGenerateRequest,
    VideoComposeRequest,
    CharacterConsistencyRequest,
)
from app.engines import engine_manager
from app.core.storage import storage

router = APIRouter(prefix="/api/ai", tags=["AI 引擎"])


@router.get("/engines", response_model=ApiResponse[dict])
async def list_engines(current_user=Depends(get_current_user)):
    """列出所有引擎信息"""
    info = engine_manager.get_all_info()
    return ApiResponse(data=info)


@router.get("/health", response_model=ApiResponse[dict])
async def engines_health(current_user=Depends(get_current_user)):
    """所有引擎健康检查"""
    results = await engine_manager.health_check_all()
    return ApiResponse(data=results)


@router.post("/text2img", response_model=ApiResponse[dict])
async def text_to_image(
    req: Text2ImgRequest,
    current_user=Depends(get_current_user),
):
    """文生图"""
    result = await engine_manager.image.text2img(
        prompt=req.prompt,
        negative_prompt=req.negative_prompt,
        width=req.width,
        height=req.height,
        seed=req.seed,
        model=req.model,
    )
    if not result.success:
        raise HTTPException(status_code=500, detail=result.error)
    return ApiResponse(data={
        "url": result.data,
        "metadata": result.metadata,
    })


@router.post("/tts", response_model=ApiResponse[dict])
async def text_to_speech(
    req: TTSRequest,
    current_user=Depends(get_current_user),
):
    """文本转语音"""
    result = await engine_manager.tts.synthesize(
        text=req.text,
        voice=req.voice,
        rate=req.rate,
        pitch=req.pitch,
        volume=req.volume,
    )
    if not result.success:
        raise HTTPException(status_code=500, detail=result.error)
    return ApiResponse(data={
        "url": result.data,
        "metadata": result.metadata,
    })


@router.post("/chat", response_model=ApiResponse[dict])
async def llm_chat(
    req: ChatRequest,
    current_user=Depends(get_current_user),
):
    """LLM 对话"""
    result = await engine_manager.llm.chat(
        messages=req.messages,
        model=req.model,
        temperature=req.temperature,
        max_tokens=req.max_tokens,
    )
    if not result.success:
        raise HTTPException(status_code=500, detail=result.error)
    return ApiResponse(data={
        "content": result.data,
        "metadata": result.metadata,
    })


@router.post("/generate-script", response_model=ApiResponse[dict])
async def generate_script(
    req: ScriptGenerateRequest,
    current_user=Depends(get_current_user),
):
    """生成漫剧剧本"""
    result = await engine_manager.llm.generate_script(
        theme=req.theme,
        style=req.style,
        num_scenes=req.num_scenes,
    )
    if not result.success:
        raise HTTPException(status_code=500, detail=result.error)
    return ApiResponse(data={
        "content": result.data,
        "metadata": result.metadata,
    })


@router.post("/compose-video", response_model=ApiResponse[dict])
async def compose_video(
    req: VideoComposeRequest,
    current_user=Depends(get_current_user),
):
    """合成视频"""
    result = await engine_manager.video.compose(
        frames=req.frames,
        audio=req.audio,
        fps=req.fps,
        resolution=req.resolution,
        duration_per_frame=req.duration_per_frame,
    )
    if not result.success:
        raise HTTPException(status_code=500, detail=result.error)
    return ApiResponse(data={
        "url": result.data,
        "metadata": result.metadata,
    })


@router.post("/character-consistency", response_model=ApiResponse[dict])
async def character_consistency(
    req: CharacterConsistencyRequest,
    current_user=Depends(get_current_user),
):
    """角色一致性生成"""
    # 解析参考图
    import base64
    import httpx

    if req.reference_image.startswith("http"):
        async with httpx.AsyncClient() as client:
            resp = await client.get(req.reference_image)
            resp.raise_for_status()
            ref_bytes = resp.content
    elif req.reference_image.startswith("data:"):
        # base64 data URL
        b64_data = req.reference_image.split(",", 1)[1]
        ref_bytes = base64.b64decode(b64_data)
    else:
        # 直接 base64
        ref_bytes = base64.b64decode(req.reference_image)

    result = await engine_manager.character.generate_consistent(
        prompt=req.prompt,
        reference_image=ref_bytes,
        consistency_weight=req.consistency_weight,
    )
    if not result.success:
        raise HTTPException(status_code=500, detail=result.error)
    return ApiResponse(data={
        "url": result.data,
        "metadata": result.metadata,
    })


@router.get("/files/{path:path}")
async def serve_file(path: str):
    """提供上传文件访问"""
    full_path = storage.get_full_path(f"/uploads/{path}")
    if not full_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")

    # 根据扩展名设置 content type
    ext = full_path.suffix.lower()
    content_types = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".mp3": "audio/mp3",
        ".wav": "audio/wav",
        ".mp4": "video/mp4",
    }
    media_type = content_types.get(ext, "application/octet-stream")

    return FileResponse(str(full_path), media_type=media_type)
```

- [ ] **Step 3: 修改 `app/api/router.py` 添加 AI 路由**

读取现有 `app/api/router.py`，在末尾添加 AI 路由的 include_router。

- [ ] **Step 4: 修改 `app/main.py` 在 lifespan 初始化引擎**

在 main.py 的 lifespan 函数中添加 `await engine_manager.initialize_all()`。

- [ ] **Step 5: 创建 `tests/test_ai_api.py` - API 测试**

```python
"""测试 AI API 路由"""
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock, patch
from app.engines.base import GenerationResult


@pytest.mark.asyncio
async def test_list_engines_unauthorized():
    """测试未授权访问"""
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/ai/engines")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_text2img_request_validation():
    """测试请求校验"""
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 缺少 prompt
        response = await client.post("/api/ai/text2img", json={})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_tts_request_validation():
    """测试 TTS 请求校验"""
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 缺少 text
        response = await client.post("/api/ai/tts", json={})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_chat_request_validation():
    """测试 chat 请求校验"""
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 缺少 messages
        response = await client.post("/api/ai/chat", json={})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_file_not_found():
    """测试访问不存在的文件"""
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/ai/files/nonexistent.png")
    assert response.status_code == 404
```

- [ ] **Step 6: 运行测试**

Run: `cd backend && python -m pytest tests/test_ai_api.py -v`
Expected: 5 个测试全部通过

---

## Task 9: 安装新依赖与集成测试

**Files:**
- Modify: `c:\漫剧软件项目\backend\requirements.txt`
- Create: `c:\漫剧软件项目\backend\tests\test_phase2_integration.py`

- [ ] **Step 1: 更新 `requirements.txt` 添加新依赖**

在现有 requirements.txt 末尾追加：
```
# Phase 2 - AI 引擎层
edge-tts>=6.1.9
Pillow>=10.2.0
httpx>=0.26.0
```

（httpx 已存在则跳过）

- [ ] **Step 2: 安装新依赖**

Run: `cd backend && python -m pip install --target .deps edge-tts Pillow --quiet`

- [ ] **Step 3: 创建 `tests/test_phase2_integration.py` - 集成测试**

```python
"""Phase 2 集成测试 - 验证 AI 引擎层完整集成"""
import pytest
from httpx import AsyncClient, ASGITransport


@pytest.mark.asyncio
async def test_ai_routes_registered():
    """测试所有 AI 路由已注册"""
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/openapi.json")
    assert response.status_code == 200

    paths = response.json()["paths"]
    expected_ai_paths = [
        "/api/ai/engines",
        "/api/ai/health",
        "/api/ai/text2img",
        "/api/ai/tts",
        "/api/ai/chat",
        "/api/ai/generate-script",
        "/api/ai/compose-video",
        "/api/ai/character-consistency",
    ]
    for path in expected_ai_paths:
        assert path in paths, f"缺少 AI 路由: {path}"


@pytest.mark.asyncio
async def test_all_phase1_still_works():
    """验证 Phase 1 功能仍然正常"""
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 健康检查
        response = await client.get("/health")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_engine_manager_singleton():
    """测试引擎管理器单例"""
    from app.engines import engine_manager
    assert engine_manager is not None
    assert hasattr(engine_manager, "initialize_all")
    assert hasattr(engine_manager, "health_check_all")


def test_all_engines_importable():
    """测试所有引擎可导入"""
    from app.engines.image.pollinations import PollinationsProvider
    from app.engines.tts.edge_tts import EdgeTTSProvider
    from app.engines.llm.deepseek import DeepSeekProvider
    from app.engines.video.ffmpeg import FFmpegProvider
    from app.engines.character.reference import ReferenceBasedProvider

    # 都可实例化
    assert PollinationsProvider()
    assert EdgeTTSProvider()
    assert DeepSeekProvider(api_key="test")
    assert FFmpegProvider()
    assert ReferenceBasedProvider()


def test_storage_singleton():
    """测试文件存储单例"""
    from app.core.storage import storage
    assert storage is not None
    assert hasattr(storage, "save")
    assert hasattr(storage, "get_full_path")
```

- [ ] **Step 4: 运行完整测试套件**

Run: `cd backend && python -m pytest tests/ -v --tb=short`
Expected: 所有测试通过（Phase 1 + Phase 2）

---

## 完成检查清单

- [ ] 引擎抽象基类与基础设施测试通过
- [ ] Pollinations.ai 图像生成 Provider 可用
- [ ] edge-tts TTS Provider 可用
- [ ] DeepSeek LLM Provider 可用
- [ ] FFmpeg 视频合成 Provider 可用
- [ ] 角色一致性 Provider 可用
- [ ] EngineManager 单例正常工作
- [ ] AI API 路由全部注册
- [ ] 所有测试通过
- [ ] 前端可调用 AI API（后续 Task）

---

## 后续阶段

完成 Phase 2 后：
- **Phase 3**: 工作流引擎 - DAG 调度、节点执行、模板系统
- **Phase 4**: 前端集成 - React Flow 节点连接到真实 AI 引擎
- **Phase 5**: 桌面端 - Electron 打包
