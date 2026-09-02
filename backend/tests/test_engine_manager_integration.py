"""EngineManager 与 ProviderRegistry/ProviderRouter/QuotaGuard/SubscriptionGuard 集成测试

Task 24: 验证多 Provider 注册、智能路由、配额检查、本地跳过配额的端到端行为。
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.engines.base import BaseEngine, GenerationResult
from app.engines.manager import EngineManager


class FakeProvider(BaseEngine):
    """测试用假 Provider"""

    def __init__(
        self,
        name: str,
        is_local: bool = False,
        subscription_required: str = "free",
    ) -> None:
        self.name = name
        self.display_name = name
        self.is_local = is_local
        self.subscription_required = subscription_required
        self._initialized = False

    async def initialize(self) -> None:
        self._initialized = True

    async def generate(self, prompt: str, **kwargs):
        return GenerationResult(
            success=True,
            data=f"{self.name}:{prompt}".encode(),
            content_type="text/plain",
            metadata={},
        )

    def get_info(self) -> dict:
        return {"name": self.name, "is_local": self.is_local}

    async def health_check(self) -> bool:
        return True


@pytest.fixture
def fake_providers():
    """构造 4 个测试 Provider"""
    return {
        "deepseek": FakeProvider("deepseek", is_local=False, subscription_required="free"),
        "qwen-local": FakeProvider("qwen-local", is_local=True, subscription_required="pro"),
        "seedream": FakeProvider("seedream", is_local=False, subscription_required="pro"),
        "edge": FakeProvider("edge", is_local=False, subscription_required="free"),
    }


@pytest.fixture
def manager_with_registry(fake_providers):
    """构造已注入 Provider 的 EngineManager（绕过 initialize）"""
    mgr = EngineManager()
    # 注入已实例化的 Provider（模拟 initialize 后的状态）
    mgr._engines = dict(fake_providers)
    mgr._instantiated_providers = dict(fake_providers)
    mgr._router = MagicMock()
    mgr._quota_guard = MagicMock()
    mgr._subscription_guard = MagicMock()
    # 默认 async 方法（成功路径），各测试可按需覆盖
    mgr._quota_guard.check = AsyncMock(return_value=True)
    mgr._quota_guard.consume = AsyncMock()
    mgr._subscription_guard.verify = AsyncMock(return_value=True)
    return mgr


@pytest.mark.asyncio
async def test_get_engine_uses_router_to_select_provider(manager_with_registry, fake_providers):
    """get_engine 应通过 ProviderRouter.select() 选择 Provider"""
    # 路由器返回 deepseek
    manager_with_registry._router.select = AsyncMock(return_value=fake_providers["deepseek"])
    engine = await manager_with_registry.get_engine_routed(
        engine_type="llm",
        user_id=1,
        subscription_tier="free",
        user_preference="",
    )
    assert engine is fake_providers["deepseek"]
    manager_with_registry._router.select.assert_awaited_once()


@pytest.mark.asyncio
async def test_quota_check_skipped_for_local_provider(manager_with_registry, fake_providers):
    """本地 Provider 跳过 QuotaGuard.check"""
    manager_with_registry._router.select = AsyncMock(return_value=fake_providers["qwen-local"])
    manager_with_registry._quota_guard.check = AsyncMock(return_value=True)
    await manager_with_registry.get_engine_routed(
        engine_type="llm",
        user_id=1,
        subscription_tier="pro",
        force_local=True,
    )
    # 本地 Provider 不应调用 quota_check
    manager_with_registry._quota_guard.check.assert_not_awaited()


@pytest.mark.asyncio
async def test_quota_check_called_for_api_provider(manager_with_registry, fake_providers):
    """API Provider 必须通过 QuotaGuard.check"""
    manager_with_registry._router.select = AsyncMock(return_value=fake_providers["deepseek"])
    manager_with_registry._quota_guard.check = AsyncMock(return_value=True)
    await manager_with_registry.get_engine_routed(
        engine_type="llm",
        user_id=1,
        subscription_tier="free",
    )
    manager_with_registry._quota_guard.check.assert_awaited_once()
    # 验证传入参数
    call_args = manager_with_registry._quota_guard.check.call_args
    assert call_args.kwargs["user_id"] == 1
    assert call_args.kwargs["engine_type"] == "llm"


@pytest.mark.asyncio
async def test_get_engine_returns_none_when_quota_exhausted(manager_with_registry, fake_providers):
    """配额耗尽时返回 None"""
    manager_with_registry._router.select = AsyncMock(return_value=fake_providers["deepseek"])
    manager_with_registry._quota_guard.check = AsyncMock(return_value=False)
    result = await manager_with_registry.get_engine_routed(
        engine_type="llm",
        user_id=1,
        subscription_tier="free",
    )
    assert result is None


@pytest.mark.asyncio
async def test_consume_quota_after_generation(manager_with_registry, fake_providers):
    """generation 完成后调用 QuotaGuard.consume"""
    manager_with_registry._router.select = AsyncMock(return_value=fake_providers["deepseek"])
    manager_with_registry._quota_guard.check = AsyncMock(return_value=True)
    manager_with_registry._quota_guard.consume = AsyncMock()
    engine = await manager_with_registry.get_engine_routed(
        engine_type="llm",
        user_id=1,
        subscription_tier="free",
    )
    assert engine is not None
    # 模拟调用 generate 并消费配额
    await engine.generate("hello")
    await manager_with_registry.consume_quota(
        user_id=1,
        engine_type="llm",
        amount=10,
        is_local=False,
    )
    manager_with_registry._quota_guard.consume.assert_awaited_once()
    call_args = manager_with_registry._quota_guard.consume.call_args
    assert call_args.kwargs["amount"] == 10


@pytest.mark.asyncio
async def test_subscription_guard_blocks_local_for_free_user(manager_with_registry, fake_providers):
    """Free 用户使用本地 Provider 时被订阅层级校验拦截"""
    manager_with_registry._router.select = AsyncMock(return_value=fake_providers["qwen-local"])
    result = await manager_with_registry.get_engine_routed(
        engine_type="llm",
        user_id=1,
        subscription_tier="free",
        force_local=True,
    )
    # qwen-local 要求 pro 层级，Free 用户应被拦截
    assert result is None


@pytest.mark.asyncio
async def test_subscription_guard_allows_local_for_pro_user(manager_with_registry, fake_providers):
    """Pro 用户使用本地 Provider 时放行"""
    manager_with_registry._router.select = AsyncMock(return_value=fake_providers["qwen-local"])
    result = await manager_with_registry.get_engine_routed(
        engine_type="llm",
        user_id=1,
        subscription_tier="pro",
        force_local=True,
    )
    assert result is fake_providers["qwen-local"]
