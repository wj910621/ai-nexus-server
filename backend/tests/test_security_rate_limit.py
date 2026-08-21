"""A3: 限流落地测试 - Phase 8 P7"""
import asyncio
import pytest
from unittest.mock import MagicMock

from fastapi import HTTPException

import app.core.rate_limit as rate_limit_module
from app.core.rate_limit import rate_limit, is_rate_limiting_enabled


def test_rate_limit_args_preserved():
    """装饰器应保留 functools.wraps 元信息"""
    @rate_limit(times=5, seconds=30)
    async def my_endpoint():
        """doc"""
        return "ok"
    assert my_endpoint.__name__ == "my_endpoint"
    assert my_endpoint.__doc__ == "doc"


async def test_rate_limit_disabled_in_desktop(monkeypatch):
    """桌面模式下 rate_limit 应为 no-op"""
    monkeypatch.setenv("CS_DESKTOP_MODE", "1")
    assert is_rate_limiting_enabled() is False

    called = {"n": 0}

    @rate_limit(times=5, seconds=60)
    async def ep():
        called["n"] += 1
        return "ok"

    result = await ep()
    assert result == "ok"
    assert called["n"] == 1


async def test_rate_limit_fallback_when_redis_unavailable(monkeypatch):
    """非生产环境 Redis 不可用时允许开发请求继续。"""
    # 非 desktop 模式 + rate_limit_enabled + 有效 redis_url
    monkeypatch.delenv("CS_DESKTOP_MODE", raising=False)
    from app.core.config import settings
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "rate_limit_redis_url", "")
    monkeypatch.setattr(settings, "redis_url", "redis://localhost:6379/0")

    monkeypatch.setattr(settings, "app_env", "test")
    monkeypatch.setattr(rate_limit_module, "_redis_client", None)
    called = {"n": 0}

    @rate_limit(times=5, seconds=60)
    async def ep(request):
        called["n"] += 1
        return "ok"

    class FakeRequest:
        client = MagicMock(host="127.0.0.1")
        headers = {}

    result = await ep(request=FakeRequest())
    assert result == "ok"
    assert called["n"] == 1


async def test_rate_limit_decorator_calls_limiter(monkeypatch):
    """启用限流 + Redis 可用时，应原子记录请求。"""
    monkeypatch.delenv("CS_DESKTOP_MODE", raising=False)
    from app.core.config import settings
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "rate_limit_redis_url", "")
    monkeypatch.setattr(settings, "redis_url", "redis://localhost:6379/0")

    calls = []

    class FakePipeline:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return False

        def incr(self, key):
            calls.append(("incr", key))
            return self

        def expire(self, key, ttl):
            calls.append(("expire", key, ttl))
            return self

        async def execute(self):
            return [1, True]

    class FakeRedis:
        def pipeline(self, transaction=True):
            assert transaction is True
            return FakePipeline()

    monkeypatch.setattr(rate_limit_module, "_redis_client", FakeRedis())

    # 构造一个 fake request
    class FakeRequest:
        client = MagicMock(host="127.0.0.1")
        headers = {}

    @rate_limit(times=5, seconds=60)
    async def ep(request):
        return "ok"

    result = await ep(request=FakeRequest())
    assert result == "ok"
    assert any(call[0] == "incr" for call in calls)


def test_login_endpoint_has_rate_limit():
    """登录端点应使用 @rate_limit 装饰器"""
    import inspect
    from app.api import auth
    # login 是 router 注册的端点，检查源码或 wrapper 属性
    src = inspect.getsource(auth.login)
    # 至少源码应包含 rate_limit 调用
    assert "rate_limit" in src


async def test_rate_limit_no_request_fails_closed(monkeypatch):
    """启用限流但端点缺少 Request 时必须拒绝，而不是绕过。"""
    monkeypatch.delenv("CS_DESKTOP_MODE", raising=False)
    from app.core.config import settings
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "rate_limit_redis_url", "")
    monkeypatch.setattr(settings, "redis_url", "redis://localhost:6379/0")

    @rate_limit(times=5, seconds=60)
    async def ep():
        return "should-not-run"

    with pytest.raises(HTTPException) as exc:
        await ep()
    assert exc.value.status_code == 500


async def test_rate_limit_redis_failure_is_503_in_production(monkeypatch):
    monkeypatch.delenv("CS_DESKTOP_MODE", raising=False)
    from app.core.config import settings
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "rate_limit_redis_url", "")
    monkeypatch.setattr(settings, "redis_url", "redis://localhost:6379/0")
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(rate_limit_module, "_redis_client", None)

    class FakeRequest:
        client = MagicMock(host="127.0.0.1")
        headers = {}

    @rate_limit(times=5, seconds=60)
    async def ep(request):
        return "should-not-run"

    with pytest.raises(HTTPException) as exc:
        await ep(request=FakeRequest())
    assert exc.value.status_code == 503
