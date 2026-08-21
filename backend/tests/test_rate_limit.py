"""Tests for rate limiting module."""
import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient


def test_get_limiter_returns_singleton():
    """get_limiter returns the same instance on repeated calls."""
    from app.core.rate_limit import get_limiter
    limiter1 = get_limiter()
    limiter2 = get_limiter()
    assert limiter1 is limiter2


def test_limiter_disabled_by_default_in_desktop_mode(monkeypatch):
    """In desktop mode (no Redis), limiter is disabled."""
    monkeypatch.setenv("CS_DESKTOP_MODE", "1")
    # Reload to pick up env
    import importlib
    import app.core.rate_limit
    importlib.reload(app.core.rate_limit)
    from app.core.rate_limit import is_rate_limiting_enabled
    # Desktop mode disables rate limiting
    assert is_rate_limiting_enabled() is False


def test_limiter_enabled_when_redis_configured(monkeypatch):
    """When REDIS_URL is set and not desktop mode, limiter is enabled."""
    monkeypatch.delenv("CS_DESKTOP_MODE", raising=False)
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    import importlib
    import app.core.rate_limit
    importlib.reload(app.core.rate_limit)
    from app.core.rate_limit import is_rate_limiting_enabled
    assert is_rate_limiting_enabled() is True


def test_rate_limit_decorator_skipped_in_desktop_mode(monkeypatch):
    """In desktop mode, rate_limit decorator is a no-op."""
    monkeypatch.setenv("CS_DESKTOP_MODE", "1")
    import importlib
    import app.core.rate_limit
    importlib.reload(app.core.rate_limit)
    from app.core.rate_limit import rate_limit

    call_count = 0

    @rate_limit(times=1, seconds=60)
    async def my_endpoint():
        nonlocal call_count
        call_count += 1
        return "ok"

    import asyncio
    # Should succeed multiple times despite limit
    asyncio.run(my_endpoint())
    asyncio.run(my_endpoint())
    asyncio.run(my_endpoint())
    assert call_count == 3


def test_rate_limit_decorator_with_redis_unavailable(monkeypatch):
    """Non-production may continue when the configured Redis is unavailable."""
    monkeypatch.delenv("CS_DESKTOP_MODE", raising=False)
    monkeypatch.setenv("REDIS_URL", "redis://nonexistent:6379/0")
    import importlib
    import app.core.rate_limit
    importlib.reload(app.core.rate_limit)
    from app.core.rate_limit import rate_limit
    from app.core.config import settings
    monkeypatch.setattr(settings, "app_env", "test")

    @rate_limit(times=1, seconds=60)
    async def my_endpoint(request):
        return "ok"

    class FakeRequest:
        client = type("Client", (), {"host": "127.0.0.1"})()
        headers = {}

    import asyncio
    result = asyncio.run(my_endpoint(request=FakeRequest()))
    assert result == "ok"


def test_get_client_ip_from_request():
    """get_client_ip extracts IP from request, respecting X-Forwarded-For."""
    from app.core.rate_limit import get_client_ip
    from unittest.mock import MagicMock

    request = MagicMock()
    request.headers = {"x-forwarded-for": "1.2.3.4, 5.6.7.8"}
    request.client.host = "127.0.0.1"
    ip = get_client_ip(request)
    assert ip == "1.2.3.4"


def test_get_client_ip_no_forwarded_header():
    """get_client_ip falls back to request.client.host."""
    from app.core.rate_limit import get_client_ip
    from unittest.mock import MagicMock

    request = MagicMock()
    request.headers = {}
    request.client.host = "192.168.1.1"
    ip = get_client_ip(request)
    assert ip == "192.168.1.1"


def test_get_client_ip_no_client():
    """get_client_ip returns 'unknown' when no client info."""
    from app.core.rate_limit import get_client_ip
    from unittest.mock import MagicMock

    request = MagicMock()
    request.headers = {}
    request.client = None
    ip = get_client_ip(request)
    assert ip == "unknown"


def test_plan_rate_limits():
    """Different plans have different rate limits."""
    from app.core.rate_limit import PLAN_RATE_LIMITS
    assert "free" in PLAN_RATE_LIMITS
    assert "pro" in PLAN_RATE_LIMITS
    assert "enterprise" in PLAN_RATE_LIMITS
    # Free plan has lower limits than pro
    assert PLAN_RATE_LIMITS["free"] <= PLAN_RATE_LIMITS["pro"]
    assert PLAN_RATE_LIMITS["pro"] <= PLAN_RATE_LIMITS["enterprise"]


def test_get_rate_limit_for_plan():
    """get_rate_limit_for_plan returns (times, seconds) tuple."""
    from app.core.rate_limit import get_rate_limit_for_plan
    times, seconds = get_rate_limit_for_plan("free")
    assert isinstance(times, int)
    assert isinstance(seconds, int)
    assert times > 0
    assert seconds > 0
