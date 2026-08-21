"""AI 引擎包 - 自动注册所有 Provider

Task 25: 在导入 engines 包时触发所有 Provider 模块的自动注册。
每个 Provider 模块底部调用 ProviderRegistry.register()，
因此只需 import 即可完成注册。

P2 Task 12: 新增 llama_cpp Provider（Intel XPU / CPU LLM fallback）

注册清单：
- IMAGE: seedream / flux / kolors (3)
- VIDEO: seedance / kling / wan / hunyuan (4)
- LLM:   qwen_local / glm / doubao / llama_cpp (4)  # P2 新增 llama_cpp
- TTS:   volcano_tts / cosyvoice (2)
"""
from app.engines.base import (
    BaseEngine,
    CharacterConsistencyProvider,
    GenerationResult,
    ImageGenProvider,
    LLMProvider,
    TTSProvider,
    VideoComposerProvider,
)
from app.engines.character.soft_provider import SoftConsistencyProvider
from app.engines.image.pollinations import PollinationsProvider
from app.engines.llm.deepseek import DeepSeekProvider
from app.engines.manager import (
    EngineManager,
    engine_manager,
    get_engine_manager,
)
from app.engines.tts.edge_tts import EdgeTTSProvider
from app.engines.video.ffmpeg import FFmpegVideoComposer

# Task 25: 注册错误收集（模块级，便于调试）
_registration_errors: dict[str, str] = {}


def _ensure_providers_registered() -> bool:
    """Task 25: 触发所有 Provider 模块的导入与自动注册

    每个 Provider 模块在底部调用 ProviderRegistry.register()，
    因此导入即注册。对 ImportError 容错（重依赖未安装时跳过本地 Provider）。

    Returns:
        True 表示所有 Provider 模块均成功导入；False 表示部分失败（错误详情见 _registration_errors）。
    """
    _registration_errors.clear()

    # 待注册的 (engine_type, module_path, provider_label) 三元组清单
    _provider_modules: list[tuple[str, str, str]] = [
        # === IMAGE Providers ===
        ("image", "app.engines.image.seedream", "seedream"),
        ("image", "app.engines.image.flux", "flux"),
        ("image", "app.engines.image.kolors", "kolors"),
        # === VIDEO Providers ===
        ("video", "app.engines.video.seedance", "seedance"),
        ("video", "app.engines.video.kling", "kling"),
        ("video", "app.engines.video.wan", "wan"),
        ("video", "app.engines.video.hunyuan", "hunyuan"),
        # === LLM Providers ===
        ("llm", "app.engines.llm.qwen_local", "qwen-local"),
        ("llm", "app.engines.llm.glm", "glm"),
        ("llm", "app.engines.llm.doubao", "doubao"),
        ("llm", "app.engines.llm.jarvis_gateway", "jarvis-gateway"),
        ("llm", "app.engines.llm.llama_cpp", "llama_cpp"),  # P2 Task 12 新增
        # === TTS Providers ===
        ("tts", "app.engines.tts.volcano_tts", "volcano"),
        ("tts", "app.engines.tts.cosyvoice", "cosyvoice"),
    ]

    import importlib

    success_count = 0
    for engine_type, module_path, label in _provider_modules:
        try:
            importlib.import_module(module_path)
            success_count += 1
        except ImportError as exc:
            # 依赖未安装等可预期错误：记录并继续
            _registration_errors[f"{engine_type}:{label}"] = (
                f"ImportError: {exc}"
            )
        except Exception as exc:  # noqa: BLE001
            # 其他异常（如 Provider 注册时校验失败）：记录并继续
            _registration_errors[f"{engine_type}:{label}"] = (
                f"{type(exc).__name__}: {exc}"
            )

    return success_count == len(_provider_modules)


# 模块导入时自动触发注册（一次）
_ensure_providers_registered()


__all__ = [
    # 基类
    "BaseEngine",
    "ImageGenProvider",
    "TTSProvider",
    "LLMProvider",
    "VideoComposerProvider",
    "CharacterConsistencyProvider",
    "GenerationResult",
    # Manager
    "EngineManager",
    "engine_manager",
    "get_engine_manager",
    # 默认 Provider（向后兼容）
    "PollinationsProvider",
    "EdgeTTSProvider",
    "DeepSeekProvider",
    "FFmpegVideoComposer",
    "SoftConsistencyProvider",
    # Task 25: 自动注册辅助
    "_ensure_providers_registered",
    "_registration_errors",
]
