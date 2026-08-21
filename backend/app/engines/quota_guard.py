"""配额管理 + 限流

P1: 多 Provider 抽象层

按订阅层级 + 引擎类型限制调用次数。
- 语义缓存命中不扣额度
- 本地推理不扣额度（is_local=True）
- Enterprise 不限（-1）
- 数据存储在 Redis（生产）或内存（开发）
"""
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class QuotaInfo:
    """用户配额信息"""
    user_id: int
    engine_type: str
    daily_limit: int
    daily_used: int
    monthly_limit: int
    monthly_used: int
    reset_at: datetime


class QuotaGuard:
    """配额管理 + 限流"""

    # 默认配额（按订阅层级 + 引擎类型）
    # -1 表示不限
    LIMITS: dict[str, dict[str, dict[str, int]]] = {
        "free": {
            "image": {"daily": 5, "monthly": 100},
            "video": {"daily": 0, "monthly": 0},
            "llm": {"daily": 10, "monthly": 200},
            "tts": {"daily": 10, "monthly": 200},
        },
        "pro": {
            "image": {"daily": 50, "monthly": 1000},
            "video": {"daily": 10, "monthly": 200},
            "llm": {"daily": 100, "monthly": 2000},
            "tts": {"daily": 100, "monthly": 2000},
        },
        "enterprise": {
            "image": {"daily": -1, "monthly": -1},
            "video": {"daily": -1, "monthly": -1},
            "llm": {"daily": -1, "monthly": -1},
            "tts": {"daily": -1, "monthly": -1},
        },
    }

    def __init__(self, backend: str = "memory", redis_url: str = ""):
        """初始化配额管理器

        Args:
            backend: "memory" 或 "redis"
            redis_url: Redis 连接 URL（backend="redis" 时使用）
        """
        self._backend = backend
        self._redis_url = redis_url
        # 内存存储: {(user_id, engine_type, date_str): {"count": int}}
        self._memory_store: dict[tuple, dict[str, int]] = {}
        self._redis = None  # 懒加载

    async def check(
        self,
        user_id: int,
        engine_type: str,
        subscription_tier: str,
    ) -> bool:
        """检查配额是否充足"""
        limits = self._get_limits(subscription_tier, engine_type)
        if limits is None:
            return False  # 未知层级/引擎类型

        daily_limit = limits["daily"]
        monthly_limit = limits["monthly"]

        # Enterprise 不限
        if daily_limit == -1 and monthly_limit == -1:
            return True

        # Free video = 0
        if daily_limit == 0:
            return False

        usage = await self._get_usage(user_id, engine_type)
        if daily_limit != -1 and usage["daily"] >= daily_limit:
            return False
        if monthly_limit != -1 and usage["monthly"] >= monthly_limit:
            return False
        return True

    async def consume(
        self,
        user_id: int,
        engine_type: str,
        amount: int = 1,
    ) -> None:
        """消耗配额"""
        await self._increment_usage(user_id, engine_type, amount)

    async def get_info(
        self,
        user_id: int,
        engine_type: str,
        subscription_tier: str,
    ) -> QuotaInfo:
        """获取配额信息（Dashboard 展示）"""
        limits = self._get_limits(subscription_tier, engine_type) or {"daily": 0, "monthly": 0}
        usage = await self._get_usage(user_id, engine_type)
        # 重置时间：明天 00:00
        now = datetime.now(UTC).replace(tzinfo=None)
        reset_at = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        return QuotaInfo(
            user_id=user_id,
            engine_type=engine_type,
            daily_limit=limits["daily"],
            daily_used=usage["daily"],
            monthly_limit=limits["monthly"],
            monthly_used=usage["monthly"],
            reset_at=reset_at,
        )

    def _get_limits(
        self,
        subscription_tier: str,
        engine_type: str,
    ) -> Optional[dict[str, int]]:
        """获取配额限制"""
        return self.LIMITS.get(subscription_tier, {}).get(engine_type)

    async def _get_usage(self, user_id: int, engine_type: str) -> dict[str, int]:
        """获取当前使用量"""
        if self._backend == "memory":
            now = datetime.now(UTC).replace(tzinfo=None)
            daily_key = (user_id, engine_type, now.strftime("%Y-%m-%d"))
            monthly_key = (user_id, engine_type, now.strftime("%Y-%m"))
            daily = self._memory_store.get(daily_key, {}).get("count", 0)
            monthly = self._memory_store.get(monthly_key, {}).get("count", 0)
            return {"daily": daily, "monthly": monthly}
        # Redis 模式略（生产环境用，开发用 memory）
        return {"daily": 0, "monthly": 0}

    async def _increment_usage(
        self,
        user_id: int,
        engine_type: str,
        amount: int,
    ) -> None:
        """增加使用量"""
        if self._backend == "memory":
            now = datetime.now(UTC).replace(tzinfo=None)
            daily_key = (user_id, engine_type, now.strftime("%Y-%m-%d"))
            monthly_key = (user_id, engine_type, now.strftime("%Y-%m"))
            if daily_key not in self._memory_store:
                self._memory_store[daily_key] = {"count": 0}
            if monthly_key not in self._memory_store:
                self._memory_store[monthly_key] = {"count": 0}
            self._memory_store[daily_key]["count"] += amount
            self._memory_store[monthly_key]["count"] += amount
