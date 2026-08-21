"""Tests for ProviderRouter."""
import pytest
from app.engines.router import ProviderRouter, RouteContext
from app.engines.base import BaseEngine, ImageGenProvider
from app.engines.provider_failover import ProviderFailover, CircuitState


class _ProProvider(ImageGenProvider):
    name = "pro-provider"
    is_local = False
    subscription_required = "pro"

    async def initialize(self):
        pass

    async def health_check(self):
        return True

    async def text2img(self, *args, **kwargs):
        from app.engines.base import GenerationResult
        return GenerationResult(success=True, data=b"", content_type="image/png", metadata={})


class _FreeProvider(ImageGenProvider):
    name = "free-provider"
    is_local = False
    subscription_required = "free"

    async def initialize(self):
        pass

    async def health_check(self):
        return True

    async def text2img(self, *args, **kwargs):
        from app.engines.base import GenerationResult
        return GenerationResult(success=True, data=b"", content_type="image/png", metadata={})


class _LocalProvider(_ProProvider):
    name = "local-provider"
    is_local = True


@pytest.fixture
def failovers():
    return {
        "image:pro-provider": ProviderFailover(threshold=5, reset_seconds=60),
        "image:free-provider": ProviderFailover(threshold=5, reset_seconds=60),
        "image:local-provider": ProviderFailover(threshold=5, reset_seconds=60),
    }


@pytest.fixture
def instantiated():
    return {
        "pro-provider": _ProProvider(),
        "free-provider": _FreeProvider(),
        "local-provider": _LocalProvider(),
    }


@pytest.fixture
def router(failovers):
    return ProviderRouter(failovers)


@pytest.mark.asyncio
async def test_select_pro_user_prefers_pro_provider(router, instantiated):
    """Pro 用户应优先选择 Pro Provider"""
    # 临时覆盖 PRIORITY 配置
    ProviderRouter.PRIORITY["pro"]["image"] = ["pro-provider", "free-provider"]
    ctx = RouteContext(
        user_id=1,
        subscription_tier="pro",
        engine_type="image",
    )
    selected = await router.select(ctx, instantiated)
    assert selected.name == "pro-provider"


@pytest.mark.asyncio
async def test_select_free_user_falls_back_to_free_provider(router, instantiated):
    """Free 用户不能使用 Pro Provider，应 fallback 到 Free Provider"""
    ProviderRouter.PRIORITY["free"]["image"] = ["pro-provider", "free-provider"]
    ctx = RouteContext(
        user_id=1,
        subscription_tier="free",
        engine_type="image",
    )
    selected = await router.select(ctx, instantiated)
    assert selected.name == "free-provider"


@pytest.mark.asyncio
async def test_user_preference_takes_priority(router, instantiated):
    """用户偏好优先于默认优先级"""
    ProviderRouter.PRIORITY["pro"]["image"] = ["pro-provider", "free-provider"]
    ctx = RouteContext(
        user_id=1,
        subscription_tier="pro",
        engine_type="image",
        user_preference="free-provider",
    )
    selected = await router.select(ctx, instantiated)
    assert selected.name == "free-provider"


@pytest.mark.asyncio
async def test_force_local_skips_cloud(router, instantiated):
    """force_local=True 跳过云端 Provider"""
    ProviderRouter.PRIORITY["pro"]["image"] = ["pro-provider", "local-provider"]
    ctx = RouteContext(
        user_id=1,
        subscription_tier="pro",
        engine_type="image",
        force_local=True,
    )
    selected = await router.select(ctx, instantiated)
    assert selected.name == "local-provider"
    assert selected.is_local is True


@pytest.mark.asyncio
async def test_circuit_open_skips_provider(router, instantiated, failovers):
    """熔断器 OPEN 时跳过该 Provider"""
    ProviderRouter.PRIORITY["pro"]["image"] = ["pro-provider", "free-provider"]
    # 强制打开熔断器
    failovers["image:pro-provider"].state = CircuitState.OPEN
    failovers["image:pro-provider"].last_failure_time = 9999999999  # 远未来，不会自动 HALF_OPEN
    ctx = RouteContext(
        user_id=1,
        subscription_tier="pro",
        engine_type="image",
    )
    selected = await router.select(ctx, instantiated)
    assert selected.name == "free-provider"


@pytest.mark.asyncio
async def test_all_providers_unavailable_returns_none(router, instantiated, failovers):
    """所有 Provider 都不可用时返回 None"""
    ProviderRouter.PRIORITY["pro"]["image"] = ["pro-provider", "free-provider"]
    for fb in failovers.values():
        fb.state = CircuitState.OPEN
        fb.last_failure_time = 9999999999
    ctx = RouteContext(
        user_id=1,
        subscription_tier="pro",
        engine_type="image",
    )
    selected = await router.select(ctx, instantiated)
    assert selected is None


@pytest.mark.asyncio
async def test_unknown_subscription_tier_returns_none(router, instantiated):
    """未知订阅层级返回 None"""
    ProviderRouter.PRIORITY["unknown"] = {"image": ["pro-provider"]}
    ctx = RouteContext(
        user_id=1,
        subscription_tier="unknown",
        engine_type="image",
    )
    selected = await router.select(ctx, instantiated)
    assert selected is None


@pytest.mark.asyncio
async def test_provider_not_instantiated_skipped(router):
    """未实例化的 Provider 被跳过"""
    ProviderRouter.PRIORITY["pro"]["image"] = ["pro-provider"]
    ctx = RouteContext(
        user_id=1,
        subscription_tier="pro",
        engine_type="image",
    )
    # instantiated 为空
    selected = await router.select(ctx, {})
    assert selected is None


@pytest.mark.asyncio
async def test_enterprise_tier_uses_pro_providers(router, instantiated):
    """Enterprise 层级应能访问 Pro Provider"""
    ProviderRouter.PRIORITY["enterprise"]["image"] = ["pro-provider"]
    ctx = RouteContext(
        user_id=1,
        subscription_tier="enterprise",
        engine_type="image",
    )
    selected = await router.select(ctx, instantiated)
    assert selected.name == "pro-provider"


@pytest.mark.asyncio
async def test_user_preference_not_in_priority_ignored(router, instantiated):
    """用户偏好不在优先级列表中时被忽略，使用默认顺序"""
    ProviderRouter.PRIORITY["pro"]["image"] = ["pro-provider"]
    ctx = RouteContext(
        user_id=1,
        subscription_tier="pro",
        engine_type="image",
        user_preference="nonexistent-provider",
    )
    selected = await router.select(ctx, instantiated)
    assert selected.name == "pro-provider"
