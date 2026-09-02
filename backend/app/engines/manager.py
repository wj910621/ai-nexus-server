"""引擎管理器 - 统一管理所有 AI 引擎

职责：
1. 统一初始化所有引擎
2. 统一健康检查
3. 统一信息查询
4. 支持运行时切换 Provider（如 image 从 pollinations 切换到其他）
5. 提供全局访问点
6. 多 Provider 智能路由（Task 24）：基于订阅/偏好/可用性选择
7. 配额管理与本地推理订阅鉴权
"""
from typing import Optional

from app.core.cache_decorator import cached
from app.core.config import settings
from app.engines.base import BaseEngine
from app.engines.character import (
    get_default_provider as get_default_character_provider,
)
from app.engines.image import get_default_provider as get_default_image_provider
from app.engines.llm import get_default_provider as get_default_llm_provider
from app.engines.provider_failover import ProviderFailover
from app.engines.tts import get_default_provider as get_default_tts_provider
from app.engines.video import get_default_provider as get_default_video_provider


class EngineManager:
    """引擎管理器 - 统一管理 5 个 AI 引擎

    支持的引擎类型：image / tts / llm / video / character
    单个引擎初始化失败不会影响其他引擎，错误记录到 _init_errors。

    Task 24 扩展：
    - _instantiated_providers: 已实例化的所有 Provider（多 Provider 实例）
    - _router: ProviderRouter 智能路由器
    - _quota_guard: QuotaGuard 配额守卫
    - _subscription_guard: SubscriptionGuard 本地推理订阅鉴权
    """

    ENGINE_TYPES = ["image", "tts", "llm", "video", "character"]

    def __init__(self) -> None:
        self._engines: dict[str, BaseEngine] = {}
        self._init_errors: dict[str, str] = {}
        self._initialized: bool = False
        self._failovers: dict[str, ProviderFailover] = {
            engine_type: ProviderFailover(
                threshold=settings.failover_circuit_threshold,
                reset_seconds=settings.failover_circuit_reset_seconds,
            )
            for engine_type in self.ENGINE_TYPES
        }
        # Task 24: 多 Provider 路由相关
        self._instantiated_providers: dict[str, BaseEngine] = {}
        self._router = None  # ProviderRouter，延迟初始化
        self._quota_guard = None  # QuotaGuard，延迟初始化
        self._subscription_guard = None  # SubscriptionGuard，延迟初始化

    def get_failover(self, engine_type: str) -> ProviderFailover:
        """Get the circuit breaker for an engine type."""
        return self._failovers.get(engine_type, ProviderFailover())

    async def initialize(self) -> None:
        """初始化所有引擎

        单个引擎初始化失败不会中断其他引擎，错误记录到 _init_errors。
        Task 24: 同时初始化 ProviderRegistry/ProviderRouter/QuotaGuard/SubscriptionGuard
        """
        # Task 24: 初始化路由相关组件
        await self._init_routing_components()

        for engine_type in self.ENGINE_TYPES:
            await self.initialize_one(engine_type)
        self._initialized = True
        await self._invalidate_status_cache()

    async def _init_routing_components(self) -> None:
        """Task 24: 初始化 ProviderRegistry/ProviderRouter/QuotaGuard/SubscriptionGuard

        - 触发 Provider 模块自动注册（导入 engines/__init__.py）
        - 构造 ProviderRouter（注入 failovers）
        - 构造 QuotaGuard 与 SubscriptionGuard
        - 实例化所有可用 Provider（API Key 已配置的）
        """
        try:
            # 触发 Provider 自动注册（函数可能不存在，跳过即可；
            # Provider 通过 @register 装饰器在模块导入时自动注册）
            try:
                from app.engines import _ensure_providers_registered  # noqa: F401
            except ImportError:
                pass

            from app.engines.quota_guard import QuotaGuard
            from app.engines.router import ProviderRouter
            from app.engines.subscription_guard import SubscriptionGuard

            # 构造路由器（按 provider_name 维度的 failover 字典）
            per_provider_failovers = self._build_per_provider_failovers()
            self._router = ProviderRouter(per_provider_failovers)
            self._quota_guard = QuotaGuard()
            # SubscriptionGuard 需要 jwt_secret/jwt_issuer（来自 settings）
            jwt_secret = settings.subscription_jwt_secret or settings.jwt_secret_key
            self._subscription_guard = SubscriptionGuard(
                jwt_secret=jwt_secret,
                jwt_issuer=settings.subscription_jwt_issuer,
            )

            # 实例化所有已注册 Provider
            await self._instantiate_all_providers()
        except Exception as exc:
            # 路由组件初始化失败不影响单 Provider 回退路径
            self._init_errors["routing"] = f"{type(exc).__name__}: {exc}"

    def _build_per_provider_failovers(self) -> dict:
        """构造每个 Provider 独立的熔断器字典"""
        from app.engines.provider_failover import ProviderFailover

        failovers: dict[str, ProviderFailover] = {}
        try:
            from app.engines.registry import ProviderRegistry
            all_providers = ProviderRegistry.list_all()
            for engine_type, names in all_providers.items():
                for name in names:
                    key = f"{engine_type}:{name}"
                    failovers[key] = ProviderFailover(
                        threshold=settings.failover_circuit_threshold,
                        reset_seconds=settings.failover_circuit_reset_seconds,
                    )
        except Exception:
            pass
        return failovers

    async def _instantiate_all_providers(self) -> None:
        """实例化所有已注册 Provider 并注入 _instantiated_providers

        单个 Provider 实例化失败不阻塞其他 Provider。
        """
        try:
            from app.engines.registry import ProviderRegistry
        except ImportError:
            return

        all_providers = ProviderRegistry.list_all()
        for engine_type, names in all_providers.items():
            for name in names:
                try:
                    provider_cls = ProviderRegistry.get(engine_type, name)
                    provider = provider_cls()
                    await provider.initialize()
                    self._instantiated_providers[name] = provider
                except Exception as exc:
                    self._init_errors[f"{engine_type}:{name}"] = (
                        f"instantiate failed: {type(exc).__name__}: {exc}"
                    )

    async def initialize_one(self, engine_type: str) -> None:
        """初始化单个引擎

        - 如果已存在实例则跳过
        - 桌面模式 (settings.local_inference_enabled): 优先尝试本地 Provider
          (diffusers/onnx/llama_cpp/piper), 失败则回退到远程 API
        - 否则直接创建默认 Provider 并调用其 initialize()
        - 异常被捕获并记录到 _init_errors
        """
        if engine_type not in self.ENGINE_TYPES:
            raise ValueError(f"未知的引擎类型: {engine_type}")

        if engine_type in self._engines:
            return

        # 桌面模式: 优先尝试本地 Provider (Task 15)
        if settings.local_inference_enabled:
            local_engine = await self._try_create_local_engine(engine_type)
            if local_engine is not None:
                self._engines[engine_type] = local_engine
                self._init_errors.pop(engine_type, None)
                await self._invalidate_status_cache()
                return

        # Fall back to default (remote API) provider
        try:
            engine = self._create_default_engine(engine_type)
            await engine.initialize()
            self._engines[engine_type] = engine
            # 初始化成功后清除历史错误记录
            self._init_errors.pop(engine_type, None)
        except Exception as exc:
            self._init_errors[engine_type] = f"{type(exc).__name__}: {exc}"
        await self._invalidate_status_cache()

    async def _try_create_local_engine(self, engine_type: str):
        """尝试创建本地 Provider；成功返回 engine，否则返回 None.

        桌面模式 (Task 15) 下被 initialize_one 调用。如果本地 Provider
        创建失败（依赖未安装 / 模型未下载 / GPU 不可用），返回 None 让
        调用方回退到远程 API。
        """
        try:
            from app.core.local_runtime import local_runtime_detector
        except ImportError:
            return None

        try:
            if engine_type == "image":
                provider_name = local_runtime_detector.recommend_image_provider()
                if provider_name == "diffusers":
                    from app.engines.image.local_diffusers import LocalDiffusersProvider
                    engine = LocalDiffusersProvider()
                    await engine.initialize()
                    return engine
                elif provider_name == "onnx":
                    from app.engines.image.local_onnx import LocalOnnxProvider
                    engine = LocalOnnxProvider()
                    await engine.initialize()
                    return engine
            elif engine_type == "llm":
                provider_name = local_runtime_detector.recommend_llm_provider()
                if provider_name == "llama_cpp":
                    from app.engines.llm.local_llm import LocalLLMProvider
                    engine = LocalLLMProvider()
                    await engine.initialize()
                    return engine
            elif engine_type == "tts":
                provider_name = local_runtime_detector.recommend_tts_provider()
                if provider_name == "piper":
                    from app.engines.tts.local_tts import LocalTTSProvider
                    engine = LocalTTSProvider()
                    await engine.initialize()
                    return engine
        except Exception as exc:
            self._init_errors[engine_type] = f"Local provider failed: {type(exc).__name__}: {exc}"
            return None
        return None

    def _create_default_engine(self, engine_type: str) -> BaseEngine:
        """根据引擎类型创建默认 Provider 实例"""
        if engine_type == "image":
            return get_default_image_provider()
        if engine_type == "tts":
            return get_default_tts_provider()
        if engine_type == "llm":
            return get_default_llm_provider()
        if engine_type == "video":
            return get_default_video_provider()
        if engine_type == "character":
            return get_default_character_provider()
        raise ValueError(f"未知的引擎类型: {engine_type}")

    def get_engine(self, engine_type: str) -> Optional[BaseEngine]:
        """获取引擎实例，不存在返回 None"""
        return self._engines.get(engine_type)

    async def get_engine_routed(
        self,
        engine_type: str,
        user_id: int,
        subscription_tier: str,
        user_preference: str = "",
        force_local: bool = False,
    ) -> Optional[BaseEngine]:
        """Task 24: 智能路由 + 配额检查 + 订阅验证

        P2 Task 14: 新增 LLM 引擎适配过滤
        - DeviceManager.recommend_llm_engine() 决定 vllm vs llama_cpp
        - Intel/CPU 环境下跳过 qwen_local（vLLM 不支持），优先 llama_cpp
        - 若候选清单中没有匹配的本地 Provider，自然降级到 API Provider

        流程：
        1. LLM 引擎适配过滤（仅对 engine_type=="llm" 生效）
        2. ProviderRouter.select() 选择 Provider
        3. 本地 Provider → SubscriptionGuard.verify()
        4. API Provider → QuotaGuard.check()
        5. 任一失败返回 None
        """
        if self._router is None or self._quota_guard is None:
            # 路由组件未初始化，回退到单 Provider 模式
            return self.get_engine(engine_type)

        from app.engines.router import RouteContext

        # P2 Task 14: LLM 引擎适配过滤
        # 在不修改 Router 内部 PRIORITY 表的前提下，从已实例化清单中
        # 移除与 DeviceManager 推荐引擎不匹配的本地 LLM Provider
        filtered_providers = self._instantiated_providers
        if engine_type == "llm":
            filtered_providers = self._filter_llm_providers_by_engine(
                self._instantiated_providers
            )

        ctx = RouteContext(
            user_id=user_id,
            subscription_tier=subscription_tier,
            engine_type=engine_type,
            user_preference=user_preference,
            force_local=force_local,
        )
        provider = await self._router.select(ctx, filtered_providers)
        if provider is None:
            return None

        # 本地 Provider → 订阅层级校验（复用 Router.TIER_ORDER 层级表；
        # 原代码调用不存在的 SubscriptionGuard.verify() 已修复）
        if provider.is_local:
            from app.engines.router import ProviderRouter

            required = getattr(provider, "subscription_required", "free")
            user_level = ProviderRouter.TIER_ORDER.get(subscription_tier, 0)
            required_level = ProviderRouter.TIER_ORDER.get(required, 0)
            if user_level < required_level:
                return None
            return provider

        # API Provider → 配额检查（商业化瘦身 2026-09-02：补 subscription_tier 参数）
        ok = await self._quota_guard.check(
            user_id=user_id,
            engine_type=engine_type,
            subscription_tier=subscription_tier,
        )
        if not ok:
            return None
        return provider

    def _filter_llm_providers_by_engine(
        self,
        providers: dict,
    ) -> dict:
        """P2 Task 14: 根据 DeviceManager 推荐的 LLM 引擎过滤候选 Provider

        - vllm → 保留 qwen_local（移除 llama_cpp）
        - llama_cpp → 保留 llama_cpp（移除 qwen_local）
        - 任何情况下保留所有 API Provider

        商业化瘦身（2026-09-02）修复：_instantiated_providers 是
        ``provider_name -> instance`` 的**扁平** dict，原先按
        ``providers.get("llm", {})`` 嵌套取值永远为空（bug）。
        现改为遍历扁平 dict，仅对本地 LLM 按推荐引擎过滤。

        若 DeviceManager 未初始化或不可用，原样返回（不破坏现有行为）。
        """
        try:
            from app.core.device_manager import DeviceManager
            dm = DeviceManager.get_instance()
            recommended = dm.recommend_llm_engine()
        except Exception:
            # DeviceManager 不可用 → 不做过滤
            return providers

        filtered: dict = {}
        for name, prov in providers.items():
            is_local = getattr(prov, "is_local", False)
            if not is_local:
                # API Provider 全部保留
                filtered[name] = prov
                continue

            # 仅过滤本地 LLM（qwen_local / llama_cpp）
            if name not in ("qwen_local", "qwen-local", "llama_cpp"):
                filtered[name] = prov
                continue

            if recommended == "llama_cpp":
                if name == "llama_cpp":
                    filtered[name] = prov
            else:  # vllm
                if name == "qwen_local" or name == "qwen-local":
                    filtered[name] = prov

        return filtered

    async def consume_quota(
        self,
        user_id: int,
        engine_type: str,
        amount: int = 1,
        is_local: bool = False,
    ) -> None:
        """Task 24: 消费配额（本地 Provider 跳过）

        商业化瘦身（2026-09-02）：参数名与 QuotaGuard.consume 对齐（amount），
        默认 1 次调用；LLM 场景由调用方按 token 数折算后传入。
        """
        if is_local:
            return
        if self._quota_guard is None:
            return
        await self._quota_guard.consume(
            user_id=user_id,
            engine_type=engine_type,
            amount=amount,
        )

    def get_image_engine(self) -> Optional[BaseEngine]:
        """获取图像生成引擎"""
        return self._engines.get("image")

    def get_tts_engine(self) -> Optional[BaseEngine]:
        """获取 TTS 语音合成引擎"""
        return self._engines.get("tts")

    def get_llm_engine(self) -> Optional[BaseEngine]:
        """获取 LLM 大语言模型引擎"""
        return self._engines.get("llm")

    def get_video_engine(self) -> Optional[BaseEngine]:
        """获取视频合成引擎"""
        return self._engines.get("video")

    def get_character_engine(self) -> Optional[BaseEngine]:
        """获取角色一致性引擎"""
        return self._engines.get("character")

    async def set_engine(self, engine_type: str, engine: BaseEngine) -> None:
        """运行时切换 Provider

        - 调用新 engine 的 initialize()
        - 替换 self._engines[engine_type]
        """
        if engine_type not in self.ENGINE_TYPES:
            raise ValueError(f"未知的引擎类型: {engine_type}")

        await engine.initialize()
        self._engines[engine_type] = engine
        # 切换成功后清除该类型的历史错误记录
        self._init_errors.pop(engine_type, None)
        await self._invalidate_status_cache()
        await self._invalidate_info_cache()

    async def _invalidate_status_cache(self) -> None:
        """Invalidate the cached engines:status entry (after state changes)."""
        try:
            from app.core.cache import get_cache_service
            cache = await get_cache_service()
            await cache.invalidate_pattern("engines:status")
        except Exception:
            pass

    async def _invalidate_info_cache(self) -> None:
        """Invalidate the cached engines:all_info entry (after engine swap)."""
        try:
            from app.core.cache import get_cache_service
            cache = await get_cache_service()
            await cache.invalidate_pattern("engines:all_info")
        except Exception:
            pass

    async def health_check_all(self) -> dict[str, bool]:
        """对所有引擎执行健康检查，返回 {engine_type: bool} 字典

        未初始化或抛异常的引擎视为不健康 (False)。
        """
        results: dict[str, bool] = {}
        for engine_type in self.ENGINE_TYPES:
            results[engine_type] = await self.health_check_one(engine_type)
        return results

    async def health_check_one(self, engine_type: str) -> bool:
        """单引擎健康检查，未初始化或异常返回 False"""
        engine = self._engines.get(engine_type)
        if engine is None:
            return False
        try:
            return bool(await engine.health_check())
        except Exception:
            return False

    @cached(ttl=60, key=lambda self: "engines:all_info")
    async def get_all_info(self) -> dict[str, dict]:
        """返回所有引擎的 get_info() 字典（cached 60s）

        未初始化的引擎类型不会出现在结果中。
        """
        return {
            engine_type: engine.get_info()
            for engine_type, engine in self._engines.items()
        }

    def get_init_errors(self) -> dict[str, str]:
        """返回初始化错误字典 {engine_type: error_message}"""
        return dict(self._init_errors)

    @cached(ttl=30, key=lambda self: "engines:status")
    async def get_status(self) -> dict:
        """返回整体状态摘要（cached 30s）"""
        return {
            "initialized": self._initialized,
            "engine_count": len(self._engines),
            "engine_types": list(self._engines.keys()),
            "init_errors": dict(self._init_errors),
        }


# 模块级单例
engine_manager = EngineManager()


async def get_engine_manager() -> EngineManager:
    """异步获取引擎管理器（如果未初始化则自动初始化）

    便于 FastAPI 依赖注入使用。
    """
    if not engine_manager._initialized:
        await engine_manager.initialize()
    return engine_manager
