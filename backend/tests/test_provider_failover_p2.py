"""P2 Tests for ProviderFailover failure_reason field & differentiated cooldown."""
import asyncio


def test_failover_has_failure_reason_default_empty():
    """ProviderFailover 应有 failure_reason 字段，默认空"""
    from app.engines.provider_failover import ProviderFailover
    f = ProviderFailover()
    assert hasattr(f, "failure_reason")
    assert f.failure_reason == ""


def test_record_failure_with_reason():
    """record_failure 可接受 reason 参数"""
    from app.engines.provider_failover import ProviderFailover
    f = ProviderFailover(threshold=1)
    import asyncio

    async def run():
        await f.record_failure(reason="oom")

    asyncio.run(run())
    assert f.failure_reason == "oom"


def test_record_success_clears_failure_reason():
    """record_success 清除 failure_reason"""
    from app.engines.provider_failover import ProviderFailover
    f = ProviderFailover(threshold=1)
    import asyncio

    async def run():
        await f.record_failure(reason="oom")
        await f.record_success()

    asyncio.run(run())
    assert f.failure_reason == ""


def test_cooldown_by_reason_oom():
    """reason=oom 时 reset_seconds 应为 300（5min）"""
    from app.engines.provider_failover import ProviderFailover
    f = ProviderFailover()
    import asyncio

    async def run():
        await f.record_failure(reason="oom")

    asyncio.run(run())
    assert f.reset_seconds == 300  # 5min for OOM


def test_cooldown_by_reason_unsupported():
    """reason=unsupported 时 reset_seconds 应为很大（永久）"""
    from app.engines.provider_failover import ProviderFailover
    f = ProviderFailover()
    import asyncio

    async def run():
        await f.record_failure(reason="unsupported")

    asyncio.run(run())
    assert f.reset_seconds >= 86400  # 1 day+


def test_cooldown_by_reason_timeout():
    """reason=timeout 时 reset_seconds 应为 60（1min）"""
    from app.engines.provider_failover import ProviderFailover
    f = ProviderFailover()
    import asyncio

    async def run():
        await f.record_failure(reason="timeout")

    asyncio.run(run())
    assert f.reset_seconds == 60


def test_cooldown_by_reason_dependency():
    """reason=dependency 时 reset_seconds 应为很大（永久）"""
    from app.engines.provider_failover import ProviderFailover
    f = ProviderFailover()
    import asyncio

    async def run():
        await f.record_failure(reason="dependency")

    asyncio.run(run())
    assert f.reset_seconds >= 86400


def test_cooldown_by_reason_unknown():
    """reason='' (unknown) 时 reset_seconds 应为 30"""
    from app.engines.provider_failover import ProviderFailover
    f = ProviderFailover()
    import asyncio

    async def run():
        await f.record_failure()

    asyncio.run(run())
    assert f.reset_seconds == 30
