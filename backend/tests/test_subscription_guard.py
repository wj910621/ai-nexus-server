"""Tests for SubscriptionGuard."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta, UTC

import jwt

from app.engines.subscription_guard import (
    SubscriptionGuard,
    HardwareProfile,
    SubscriptionInfo,
)


@pytest.fixture
def guard():
    """SubscriptionGuard 实例（使用测试密钥）"""
    return SubscriptionGuard(
        jwt_secret="test-secret-key-for-subscription-tests-32-bytes",
        jwt_issuer="comicstudio-test",
        offline_grace_days=7,
    )


def test_verify_subscription_valid_token(guard):
    """有效 JWT token 返回 SubscriptionInfo"""
    payload = {
        "sub": "user-123",
        "iss": "comicstudio-test",
        "tier": "pro",
        "exp": int((datetime.now(UTC) + timedelta(days=30)).timestamp()),
        "iat": int(datetime.now(UTC).timestamp()),
    }
    token = jwt.encode(payload, "test-secret-key-for-subscription-tests-32-bytes", algorithm="HS256")
    info = guard.verify_subscription(token)
    assert info.user_id == "user-123"
    assert info.tier == "pro"
    assert info.is_expired is False


def test_verify_subscription_expired_within_grace(guard):
    """过期但仍在 7 天宽限期内 → is_expired=True，仍然返回 info"""
    expired_payload = {
        "sub": "user-456",
        "iss": "comicstudio-test",
        "tier": "pro",
        "exp": int((datetime.now(UTC) - timedelta(days=3)).timestamp()),  # 3 天前过期
        "iat": int(datetime.now(UTC).timestamp()) - 86400 * 30,
    }
    token = jwt.encode(expired_payload, "test-secret-key-for-subscription-tests-32-bytes", algorithm="HS256")
    info = guard.verify_subscription(token)
    assert info.user_id == "user-456"
    assert info.is_expired is True
    assert info.is_within_grace is True  # 3 < 7


def test_verify_subscription_expired_beyond_grace(guard):
    """过期超过 7 天宽限期 → 抛出 PermissionError"""
    expired_payload = {
        "sub": "user-789",
        "iss": "comicstudio-test",
        "tier": "pro",
        "exp": int((datetime.now(UTC) - timedelta(days=10)).timestamp()),  # 10 天前过期
        "iat": int(datetime.now(UTC).timestamp()) - 86400 * 30,
    }
    token = jwt.encode(expired_payload, "test-secret-key-for-subscription-tests-32-bytes", algorithm="HS256")
    with pytest.raises(PermissionError, match="订阅已过期"):
        guard.verify_subscription(token)


def test_recommend_hardware_profile(guard):
    """根据 vram/ram 推荐 HardwareProfile"""
    # 高配：16GB VRAM → high
    profile = guard.recommend_hardware_profile(vram_gb=16.0, ram_gb=32.0)
    assert profile == HardwareProfile.HIGH

    # 中配：8GB VRAM → mid
    profile = guard.recommend_hardware_profile(vram_gb=8.0, ram_gb=16.0)
    assert profile == HardwareProfile.MID

    # 低配：4GB VRAM → low
    profile = guard.recommend_hardware_profile(vram_gb=4.0, ram_gb=8.0)
    assert profile == HardwareProfile.LOW

    # 无 GPU 但 8GB+ RAM → cpu
    profile = guard.recommend_hardware_profile(vram_gb=0.0, ram_gb=8.0)
    assert profile == HardwareProfile.CPU


def test_get_model_download_list(guard):
    """按硬件配置返回推荐下载模型列表"""
    # HIGH profile 应包含 FLUX 和 Qwen2.5-14B
    models = guard.get_model_download_list(HardwareProfile.HIGH)
    names = [m["name"] for m in models]
    assert "FLUX.1-dev" in names
    assert any("Qwen2.5-14B" in n for n in names)

    # LOW profile 应包含更小的模型
    models = guard.get_model_download_list(HardwareProfile.LOW)
    names = [m["name"] for m in models]
    assert any("stable-diffusion" in n for n in names)
    assert any("Qwen2.5-1.5B" in n for n in names)

    # CPU profile 只推荐小模型
    models = guard.get_model_download_list(HardwareProfile.CPU)
    sizes = [m["size_mb"] for m in models]
    assert all(s < 5000 for s in sizes)  # CPU 模型 < 5GB
