"""本地 LLM - llama.cpp (CPU + GPU fallback)

Task 15: Local AI Inference (Desktop)

使用 llama.cpp (llama-cpp-python) 加载 GGUF 量化模型。
支持 CPU 和 GPU (CUDA Metal) 推理。

llama_cpp 是可选依赖（仅桌面构建安装）。
"""
import logging
from typing import AsyncGenerator

from app.engines.base import GenerationResult, LLMProvider
from app.engines.model_manager import model_manager

logger = logging.getLogger(__name__)


class LocalLLMProvider(LLMProvider):
    """本地 LLM Provider

    使用 llama.cpp (llama-cpp-python) 加载 GGUF 量化模型。
    支持 CPU 和 GPU (CUDA Metal) 推理。
    """

    name = "local-llm"
    display_name = "Local LLM (llama.cpp)"

    def __init__(self, model_name: str = "qwen2.5-7b") -> None:
        self.model_name = model_name
        self._llm = None
        self._initialized = False

    async def initialize(self) -> None:
        self._initialized = True

    def _ensure_loaded(self) -> None:
        if self._llm is not None:
            return
        from llama_cpp import Llama

        model_path = model_manager.get_model_path(self.model_name)
        if model_path is None:
            raise RuntimeError(f"Model {self.model_name} not downloaded")

        # Detect GPU
        n_gpu_layers = 0
        try:
            import torch
            if torch.cuda.is_available():
                n_gpu_layers = 35  # Offload most layers to GPU
        except ImportError:
            pass

        self._llm = Llama(
            model_path=model_path,
            n_ctx=4096,
            n_gpu_layers=n_gpu_layers,
            verbose=False,
        )

    async def chat(
        self,
        messages: list[dict],
        model: str = "qwen2.5-7b",
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs,
    ) -> GenerationResult:
        """Synchronous chat (llama.cpp is blocking).

        Note: ``messages`` follows OpenAI format (list of {role, content} dicts).
        We flatten them into a single prompt for llama.cpp.
        """
        try:
            self._ensure_loaded()
        except Exception as exc:
            return GenerationResult(
                success=False,
                data="",
                content_type="text/plain",
                metadata={"provider": self.name},
                error=f"{type(exc).__name__}: {exc}",
            )

        if model and model != self.model_name:
            self.model_name = model
            self._llm = None
            try:
                self._ensure_loaded()
            except Exception as exc:
                return GenerationResult(
                    success=False,
                    data="",
                    content_type="text/plain",
                    metadata={"provider": self.name},
                    error=f"{type(exc).__name__}: {exc}",
                )

        # Flatten messages to a prompt
        prompt_parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            prompt_parts.append(f"{role}: {content}")
        prompt = "\n".join(prompt_parts)

        output = self._llm(
            prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            echo=False,
        )
        text = output["choices"][0]["text"]
        return GenerationResult(
            success=True,
            data=text,
            content_type="text/plain",
            metadata={
                "provider": self.name,
                "model": self.model_name,
                "is_local": True,
                "prompt_tokens": output.get("usage", {}).get("prompt_tokens", 0),
                "completion_tokens": output.get("usage", {}).get("completion_tokens", 0),
            },
        )

    async def chat_stream(
        self,
        messages: list[dict],
        model: str = "qwen2.5-7b",
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """Stream chat tokens."""
        self._ensure_loaded()
        # Flatten messages to a prompt
        prompt_parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            prompt_parts.append(f"{role}: {content}")
        prompt = "\n".join(prompt_parts)

        for chunk in self._llm(
            prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=True,
        ):
            text = chunk["choices"][0].get("text", "")
            if text:
                yield text

    async def health_check(self) -> bool:
        """Healthy when llama_cpp is importable."""
        try:
            from llama_cpp import Llama  # noqa: F401
            return True
        except ImportError:
            return False

    def get_info(self) -> dict:
        info = super().get_info()
        info["model"] = self.model_name
        info["is_local"] = True
        info["available_models"] = ["qwen2.5-7b", "qwen2.5-3b", "llama-3-8b"]
        return info
