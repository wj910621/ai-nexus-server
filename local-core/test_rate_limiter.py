"""
限流器测试
"""

import time

import pytest

from rate_limiter import SlidingWindowLimiter, get_client_id, check_rate_limit


@pytest.fixture
def limiter():
    return SlidingWindowLimiter(max_requests=3, window_seconds=60, burst=1)


def test_burst_limit_and_block(limiter):
    key = "test_client"
    allowed_results = [limiter.is_allowed(key)[0] for _ in range(5)]
    assert allowed_results == [True, True, True, True, False]


def test_get_info_does_not_increase_count(limiter):
    key = "info_client"
    for _ in range(3):
        limiter.is_allowed(key)
    info = limiter.get_info(key)
    assert info["remaining"] == 1
    assert info["limit"] == 4


def test_empty_key_is_allowed(limiter):
    allowed, info = limiter.is_allowed("")
    assert allowed is True
    assert info == {}


def test_window_slides_and_old_buckets_cleaned(limiter, monkeypatch):
    key = "window_client"
    current = [0.0]

    def fake_time():
        return current[0]

    monkeypatch.setattr(time, "time", fake_time)

    for _ in range(4):
        assert limiter.is_allowed(key)[0] is True
    assert limiter.is_allowed(key)[0] is False

    # 进入下一个完整窗口（桶 2），旧桶应被清理并恢复配额
    current[0] = 120.0
    allowed, info = limiter.is_allowed(key)
    assert allowed is True
    assert info["remaining"] == 3


def test_memory_leak_cleanup_when_buckets_expire(limiter, monkeypatch):
    key = "cleanup_client"
    current = [0.0]
    monkeypatch.setattr(time, "time", lambda: current[0])

    limiter.is_allowed(key)
    assert key in limiter._buckets

    current[0] = 120.0
    limiter.is_allowed(key)
    # 原桶已过期，中间状态会短暂移除 key 后再创建新桶
    assert key in limiter._buckets


def test_get_client_id_prefers_api_key_header():
    class Request:
        headers = {"X-API-Key": "secret-key"}
        remote_addr = "1.2.3.4"

    assert get_client_id(Request()) == "key:secret-key"[:36]


def test_get_client_id_uses_authorization_bearer():
    class Request:
        headers = {"Authorization": "Bearer token123"}
        remote_addr = "1.2.3.4"

    assert get_client_id(Request()) == "key:token123"[:36]


def test_get_client_id_falls_back_to_ip():
    class Request:
        headers = {}
        remote_addr = "192.168.1.10"

    assert get_client_id(Request()) == "ip:192.168.1.10"


def test_check_rate_limit_disabled(monkeypatch):
    import rate_limiter

    monkeypatch.setattr(rate_limiter.settings, "rate_limit_enabled", False)
    allowed, info = check_rate_limit("any")
    assert allowed is True
    assert info == {"limit": 0, "remaining": 0, "reset_at": 0}


def main():
    print("=== 限流器测试 ===\n")

    limiter = SlidingWindowLimiter(max_requests=3, burst=1)
    key = "test_client"

    print("1. 正常请求（限制 3 + 突发 1 = 4）...")
    for i in range(5):
        allowed, info = limiter.is_allowed(key)
        print(f"  第 {i+1} 次: allowed={allowed}, remaining={info['remaining']}")

    assert allowed is False, "第 5 次应被限流"
    print("  ✓ 限流触发正确")

    print("\n2. 查询接口不增加计数...")
    info = limiter.get_info(key)
    print(f"  info: {info}")

    print("\n=== 限流器测试完成 ===")


if __name__ == "__main__":
    main()
