"""LlamaCppProvider - Intel XPU / CPU LLM Provider

Phase 8 P2: AMD/Intel GPU 支持

特性：
- 基于 llama-cpp-python，使用 GGUF 量化模型
- Intel XPU 走 Vulkan 后端（n_gpu_layers=-1 全卸载）
- CPU 模式 n_gpu_layers=0（纯 CPU 推理）
- 支持 chat 与流式生成
- llama_cpp 是可选依赖
"""
import logging
from typing import AsyncGenerator, Optional

from app.core.config import settings
from app.engines.base import GenerationResult, LLMProvider

logger = logging.getLogger(__name__)

# llama_cpp 是可选依赖
try:
    from llama_cpp import Llama
    _LLAMA_CPP_AVAILABLE = True
except ImportError:
    Llama = None  # type: ignore
    _LLAMA_CPP_AVAILABLE = False


class LlamaCppProvider(LLMProvider):
    """Llama.cpp LLM Provider (Intel XPU / CPU)"""

    name = "llama_cpp"
    display_name = "Llama.cpp (Intel/CPU)"
    capability = "chat"
    is_local = True
    supported_models = [
        "Qwen/Qwen2.5-7B-Instruct-GGUF",
        "Qwen/Qwen2.5-14B-Instruct-GGUF",
        "Qwen/Qwen2.5-1.5B-Instruct-GGUF",
    ]

    DEFAULT_MODEL = "Qwen/Qwen2.5-7B-Instruct-GGUF"

    def __init__(
        self,
        model_path: Optional[str] = None,
        n_gpu_layers: Optional[int] = None,
        n_ctx: int = 8192,
    ) -> None:
        # P2: 通过 DeviceManager 获取设备字符串
        from app.core.device_manager import DeviceManager
        dm = DeviceManager.get_instance()
        self.device_string = dm.get_device_string("llm")

        # Intel XPU → n_gpu_layers=-1（全卸载到 Vulkan）
        # CPU → n_gpu_layers=0（纯 CPU）
        if n_gpu_layers is not None:
            self._n_gpu_layers = n_gpu_layers
        elif self.device_string.startswith("xpu"):
            self._n_gpu_layers = -1
        else:
            self._n_gpu_layers = 0

        self.model_path = model_path or settings.llama_cpp_model_path or self.DEFAULT_MODEL
        self.n_ctx = n_ctx
        self._model = None
        self._initialized = False

    async def initialize(self) -> None:
        """初始化 llama.cpp 模型"""
        if not _LLAMA_CPP_AVAILABLE:
            self._init_error = "llama_cpp not installed (pip install llama-cpp-python)"
            logger.warning(f"[P2] {self._init_error}")
            return

        try:
            self._model = Llama(
                model_path=self.model_path,
                n_gpu_layers=self._n_gpu_layers,
                n_ctx=self.n_ctx,
                verbose=False,
            )
            self._initialized = True
            logger.info(
                f"[P2] LlamaCppProvider initialized: model={self.model_path}, "
                f"device={self.device_string}, n_gpu_layers={self._n_gpu_layers}"
            )
        except Exception as exc:
            self._init_error = f"initialize failed: {type(exc).__name__}: {exc}"
            logger.error(f"[P2] {self._init_error}")

    async def chat(
        self,
        messages: list[dict],
        model: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs,
    ) -> GenerationResult:
        """对话生成"""
        if not self._initialized or self._model is None:
            return GenerationResult(
                success=False, data="", content_type="text/plain",
                metadata={}, error="LlamaCppProvider 未初始化（模型未加载）",
            )

        try:
            response = self._model.create_chat_completion(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=False,
            )
            text = response["choices"][0]["message"]["content"]

            return GenerationResult(
                success=True, data=text, content_type="text/plain",
                metadata={
                    "provider": self.name,
                    "model": self.model_path,
                    "completion_tokens": response.get("usage", {}).get("completion_tokens", 0),
                },
            )
        except Exception as exc:
            return GenerationResult(
                success=False, data="", content_type="text/plain",
                metadata={}, error=f"{type(exc).__name__}: {exc}",
            )

    async def chat_stream(
        self,
        messages: list[dict],
        model: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """流式生成 - 逐 token yield"""
        if not self._initialized or self._model is None:
            raise RuntimeError("LlamaCppProvider 未初始化")

        # llama-cpp-python 的流式 API 返回同步 generator，包装为 async
        response = self._model.create_chat_completion(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        for chunk in response:
            delta = chunk["choices"][0].get("delta", {})
            content = delta.get("content", "")
            if content:
                yield content

    async def health_check(self) -> bool:
        try:
            if not self._initialized:
                await self.initialize()
            if not self._initialized:
                return False
            result = await self.chat(
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=5,
            )
            return result.success
        except Exception:
            return False

    def get_info(self) -> dict:
        info = super().get_info()
        info["model_path"] = self.model_path
        info["device_string"] = self.device_string
        info["n_gpu_layers"] = self._n_gpu_layers
        info["llama_cpp_available"] = _LLAMA_CPP_AVAILABLE
        return info


# 模块级注册 - 导入时自动触发
try:
    from app.engines.registry import provider_registry
    provider_registry.register("llm", "llama_cpp", LlamaCppProvider)
except Exception:
    pass
