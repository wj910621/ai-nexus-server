"""Qwen2.5 本地 LLM Provider (vLLM)

Task 12 (Phase 8 P1) — Spec Section 8.5

特性：
- 使用 vLLM AsyncLLMEngine 高吞吐推理
- OpenAI 兼容的 chat 接口（messages + chat_template）
- 支持流式 token 生成（async generator）
- 模型常驻显存，热启动 < 1s
- vllm 是可选依赖
"""
import logging
from typing import AsyncGenerator, Optional

from app.core.config import settings
from app.engines.base import GenerationResult, LLMProvider

logger = logging.getLogger(__name__)

# vllm 是可选依赖
try:
    from transformers import AutoTokenizer
    from vllm import AsyncEngineArgs, AsyncLLMEngine, SamplingParams
    _VLLM_AVAILABLE = True
except ImportError:
    # vllm 未安装时提供占位类，使模块可导入且 SamplingParams(...) 不会抛 TypeError
    # 实际推理在 _engine 为 None 时会先返回错误
    class _UnavailablePlaceholder:
        """vllm/transformers 未安装时的占位类，接受任意参数构造"""

        def __init__(self, *args, **kwargs) -> None:
            pass

    AsyncLLMEngine = _UnavailablePlaceholder  # type: ignore
    AsyncEngineArgs = _UnavailablePlaceholder  # type: ignore
    SamplingParams = _UnavailablePlaceholder  # type: ignore
    AutoTokenizer = _UnavailablePlaceholder  # type: ignore
    _VLLM_AVAILABLE = False


class QwenLocalProvider(LLMProvider):
    """Qwen2.5 本地 LLM Provider (vLLM)"""

    name = "qwen_local"
    display_name = "Qwen2.5 本地 (vLLM)"
    capability = "chat"
    is_local = True
    supported_models = [
        "Qwen/Qwen2.5-7B-Instruct",
        "Qwen/Qwen2.5-14B-Instruct",
        "Qwen/Qwen2.5-1.5B-Instruct",
    ]

    DEFAULT_MODEL = "Qwen/Qwen2.5-7B-Instruct"

    def __init__(
        self,
        model_id: Optional[str] = None,
        device: str = "",
        gpu_memory_utilization: float = 0.85,
        max_model_len: int = 8192,
    ) -> None:
        self.model_id = model_id or settings.local_llm_model or self.DEFAULT_MODEL
        # P2: 通过 DeviceManager 获取 device + LLM 引擎适配
        from app.core.device_manager import DeviceManager
        dm = DeviceManager.get_instance()
        self.device = device or dm.get_device_string("llm")
        self.engine_hint = dm.recommend_llm_engine()
        # P2: 若 DeviceManager 推荐 llama_cpp（Intel/CPU），此 Provider 不可用
        self._available = (self.engine_hint == "vllm")
        self.gpu_memory_utilization = gpu_memory_utilization
        self.max_model_len = max_model_len
        self._engine = None
        self._tokenizer = None
        self._initialized = False

    async def initialize(self) -> None:
        """初始化 vLLM 引擎"""
        # P2: 若被 DeviceManager 标记为不可用，跳过初始化
        if not getattr(self, "_available", True):
            self._init_error = "engine_hint=llama_cpp, use LlamaCppProvider instead"
            logger.info(f"[P2] QwenLocalProvider skipped: {self._init_error}")
            return

        if not _VLLM_AVAILABLE:
            logger.warning("vllm 未安装，QwenLocalProvider 不可用")
            self._init_error = "vllm not installed"
            return

        self._tokenizer = AutoTokenizer.from_pretrained(self.model_id, trust_remote_code=True)
        engine_args = AsyncEngineArgs(
            model=self.model_id,
            tokenizer=self.model_id,
            trust_remote_code=True,
            dtype="auto",
            gpu_memory_utilization=self.gpu_memory_utilization,
            max_model_len=self.max_model_len,
        )
        self._engine = AsyncLLMEngine.from_engine_args(engine_args)
        self._initialized = True
        logger.info(f"QwenLocalProvider initialized: {self.model_id}")

    async def chat(
        self,
        messages: list[dict],
        model: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs,
    ) -> GenerationResult:
        """对话生成"""
        if not self._initialized or self._engine is None:
            return GenerationResult(
                success=False, data="", content_type="text/plain",
                metadata={}, error="QwenLocalProvider 未初始化（vLLM 引擎未加载）",
            )

        try:
            # 应用 chat template
            input_ids = self._tokenizer.apply_chat_template(
                messages,
                tokenize=True,
                add_generation_prompt=True,
            )

            sampling_params = SamplingParams(
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=kwargs.get("top_p", 0.9),
            )

            # vLLM 异步生成
            request_id = f"req-{hash(tuple(input_ids)) & 0xFFFFFFFF}"
            output = await self._engine.generate(
                prompt=None,
                sampling_params=sampling_params,
                request_id=request_id,
                prompt_token_ids=input_ids,
            )

            text = output.outputs[0].text

            return GenerationResult(
                success=True, data=text, content_type="text/plain",
                metadata={
                    "provider": self.name,
                    "model": self.model_id,
                    "completion_tokens": len(output.outputs[0].token_ids),
                    "finish_reason": output.outputs[0].finish_reason,
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
        if not self._initialized or self._engine is None:
            raise RuntimeError("QwenLocalProvider 未初始化")

        input_ids = self._tokenizer.apply_chat_template(
            messages, tokenize=True, add_generation_prompt=True,
        )
        sampling_params = SamplingParams(
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=kwargs.get("top_p", 0.9),
        )

        request_id = f"stream-{hash(tuple(input_ids)) & 0xFFFFFFFF}"
        async for output in self._engine.generate(
            prompt=None,
            sampling_params=sampling_params,
            request_id=request_id,
            prompt_token_ids=input_ids,
            stream=True,
        ):
            for o in output.outputs:
                if o.text:
                    yield o.text

    async def health_check(self) -> bool:
        # P2: 若被 DeviceManager 标记为不可用，直接返回 False
        if not getattr(self, "_available", True):
            return False
        try:
            if not self._initialized:
                await self.initialize()
            result = await self.chat(
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=5,
            )
            return result.success
        except Exception:
            return False

    def get_info(self) -> dict:
        info = super().get_info()
        info["model_id"] = self.model_id
        info["vllm_available"] = _VLLM_AVAILABLE
        info["engine_hint"] = getattr(self, "engine_hint", "vllm")  # P2
        info["available"] = getattr(self, "_available", True)  # P2
        return info


# 模块级注册 - 导入时自动触发
try:
    from app.engines.registry import provider_registry
    provider_registry.register("llm", "qwen_local", QwenLocalProvider)
except Exception:
    pass
