"""Tests for QuotaGuard."""
import pytest
from datetime import datetime
from app.engines.quota_guard import QuotaGuard, QuotaInfo


@pytest.fixture
def guard():
    """内存模式 QuotaGuard"""
    return QuotaGuard(backend="memory")


@pytest.mark.asyncio
async def test_check_quota_within_limit(guard):
    """配额内返回 True"""
    result = await guard.check(user_id=1, engine_type="llm", subscription_tier="free")
    assert result is True


@pytest.mark.asyncio
async def test_consume_increments_usage(guard):
    """consume 后使用量增加"""
    await guard.consume(user_id=1, engine_type="llm", amount=1)
    info = await guard.get_info(user_id=1, engine_type="llm", subscription_tier="free")
    assert info.daily_used == 1


@pytest.mark.asyncio
async def test_check_quota_exceeded(guard):
    """超出配额返回 False"""
    # Free 用户 LLM daily=10
    for _ in range(10):
        await guard.consume(user_id=1, engine_type="llm", amount=1)
    result = await guard.check(user_id=1, engine_type="llm", subscription_tier="free")
    assert result is False


@pytest.mark.asyncio
async def test_enterprise_unlimited(guard):
    """Enterprise 用户不限配额"""
    for _ in range(100):
        await guard.consume(user_id=1, engine_type="llm", amount=1)
    result = await guard.check(user_id=1, engine_type="llm", subscription_tier="enterprise")
    assert result is True


@pytest.mark.asyncio
async def test_free_video_not_allowed(guard):
    """Free 用户不能使用视频"""
    result = await guard.check(user_id=1, engine_type="video", subscription_tier="free")
    assert result is False


@pytest.mark.asyncio
async def test_get_info_returns_correct_limits(guard):
    """get_info 返回正确的配额信息"""
    await guard.consume(user_id=1, engine_type="llm", amount=3)
    info = await guard.get_info(user_id=1, engine_type="llm", subscription_tier="free")
    assert info.daily_limit == 10
    assert info.daily_used == 3
    assert info.monthly_limit == 200
    assert info.monthly_used == 3
    assert isinstance(info.reset_at, datetime)
