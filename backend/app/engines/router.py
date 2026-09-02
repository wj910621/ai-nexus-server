"""智能路由器 - 按 4 维度选择 Provider

P1: 多 Provider 抽象层

决策维度:
1. 用户订阅层级 (free/pro/enterprise)
2. 用户偏好 (首启向导/设置中选择)
3. Provider 可用性 (熔断器状态)
4. 本地推理模式 (force_local)
"""
from dataclasses import dataclass
from typing import Optional

from app.engines.base import BaseEngine
from app.engines.provider_failover import ProviderFailover


@dataclass
class RouteContext:
    """路由上下文"""
    user_id: int
    subscription_tier: str       # "free" / "pro" / "enterprise"
    engine_type: str             # "image" / "video" / "llm" / "tts"
    user_preference: str = ""    # 用户偏好的 provider 名
    force_local: bool = False    # 本地推理模式下强制本地


class ProviderRouter:
    """智能路由器 - 按订阅层级 + 用户偏好 + 可用性选择 Provider"""

    # 默认优先级（按订阅层级 + 引擎类型）
    # 商业化瘦身（2026-09-02）：provider 名与 ProviderRegistry 注册名严格对齐。
    # 下线：image/kolors、llm/glm、llm/doubao、tts/volcano_tts、video 全部 4 个。
    PRIORITY: dict[str, dict[str, list[str]]] = {
        "free": {
            "image": ["pollinations"],
            "video": [],
            "llm": ["deepseek"],
            "tts": ["edge_tts"],
        },
        "pro": {
            "image": ["seedream", "pollinations"],
            "video": [],
            "llm": ["deepseek", "jarvis-gateway"],
            "tts": ["edge_tts", "cosyvoice"],
        },
        "enterprise": {
            "image": ["seedream", "pollinations"],
            "video": [],
            "llm": ["deepseek", "jarvis-gateway"],
            "tts": ["edge_tts", "cosyvoice"],
        },
    }

    # 订阅层级优先级（数字越大权限越高）
    TIER_ORDER: dict[str, int] = {"free": 0, "pro": 1, "enterprise": 2}

    def __init__(self, failovers: dict[str, ProviderFailover]):
        """初始化路由器

        Args:
            failovers: 熔断器字典，key 格式为 "{engine_type}:{provider_name}"
        """
        self._failovers = failovers

    async def select(
        self,
        ctx: RouteContext,
        instantiated: dict[str, BaseEngine],
    ) -> Optional[BaseEngine]:
        """选择最优 Provider

        Args:
            ctx: 路由上下文
            instantiated: 已实例化的 Provider 池 (provider_name -> instance)

        Returns:
            选中的 Provider 实例，无可用时返回 None
        """
        candidates = self._get_candidates(ctx)
        for provider_name in candidates:
            provider = instantiated.get(provider_name)
            if provider is None:
                continue
            if not self._is_available(ctx.engine_type, provider_name):
                continue
            if not self._subscription_ok(provider, ctx.subscription_tier):
                continue
            if ctx.force_local and not provider.is_local:
                continue
            return provider
        return None

    def _get_candidates(self, ctx: RouteContext) -> list[str]:
        """获取候选 Provider 列表（用户偏好优先）"""
        tier_list = self.PRIORITY.get(ctx.subscription_tier, {}).get(ctx.engine_type, [])
        if ctx.user_preference and ctx.user_preference in tier_list:
            # 用户偏好放第一位，其余作为 fallback
            return [ctx.user_preference] + [p for p in tier_list if p != ctx.user_preference]
        return tier_list

    def _is_available(self, engine_type: str, provider_name: str) -> bool:
        """检查熔断器是否允许调用"""
        failover = self._failovers.get(f"{engine_type}:{provider_name}")
        if failover is None:
            return True
        return failover.can_call()

    def _subscription_ok(self, provider: BaseEngine, tier: str) -> bool:
        """检查用户订阅是否满足 Provider 要求"""
        required = provider.subscription_required
        user_level = self.TIER_ORDER.get(tier, 0)
        required_level = self.TIER_ORDER.get(required, 0)
        return user_level >= required_level
