"""
rate_limiter.py 的 pytest 测试（升级自 test_rate_limiter.py 脚本式测试）
"""

import sys
import os
import time
import threading

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ""))

from rate_limiter import SlidingWindowLimiter, check_rate_limit, get_client_id


# ---------------------------------------------------------------------------
# SlidingWindowLimiter 测试
# ---------------------------------------------------------------------------

class TestSlidingWindowLimiterIsAllowed:
    """SlidingWindowLimiter.is_allowed 方法"""

    def test_respects_max_requests_plus_burst(self):
        """max_requests + burst 为总上限，超出后应被限流"""
        limiter = SlidingWindowLimiter(max_requests=3, burst=1)
        key = "test_limit"
        total = 3 + 1  # max_requests + burst = 4

        results = []
        for _ in range(total + 1):
            allowed, info = limiter.is_allowed(key)
            results.append(allowed)

        # 前 4 次允许，第 5 次被限流
        assert all(results[:total])
        assert results[total] is False

    def test_empty_key_always_allowed(self):
        """空 key 始终允许通过"""
        limiter = SlidingWindowLimiter(max_requests=1, burst=0)
        # 反复调用空 key
        for _ in range(100):
            allowed, info = limiter.is_allowed("")
            assert allowed is True

    def test_returns_correct_remaining_count(self):
        """remaining 应正确递减"""
        limiter = SlidingWindowLimiter(max_requests=5, burst=2)
        key = "test_remaining"
        limit_total = 5 + 2

        for i in range(limit_total):
            allowed, info = limiter.is_allowed(key)
            assert allowed is True
            expected_remaining = limit_total - (i + 1)
            assert info["remaining"] == expected_remaining

    def test_returns_correct_reset_at(self):
        """reset_at 应为下一窗口的起始时间"""
        limiter = SlidingWindowLimiter(max_requests=5, window_seconds=60, burst=1)
        key = "test_reset"
        allowed, info = limiter.is_allowed(key)
        assert allowed is True

        # reset_at 应该在未来
        assert info["reset_at"] > time.time()
        # reset_at 应该是 window_seconds 的整数倍
        assert info["reset_at"] % 60 == 0

    def test_info_limit_equals_max_plus_burst(self):
        """info['limit'] 应等于 max_requests + burst"""
        limiter = SlidingWindowLimiter(max_requests=10, burst=5)
        key = "test_info_limit"
        allowed, info = limiter.is_allowed(key)
        assert info["limit"] == 15


class TestSlidingWindowLimiterGetInfo:
    """SlidingWindowLimiter.get_info 方法"""

    def test_get_info_does_not_increment_count(self):
        """get_info 只查询不增加计数"""
        limiter = SlidingWindowLimiter(max_requests=3, burst=1)
        key = "test_getinfo"

        # 先调用一次 is_allowed
        limiter.is_allowed(key)

        # 多次调用 get_info 不应增加计数
        for _ in range(10):
            info = limiter.get_info(key)

        # 再次 is_allowed 应仍被允许（因为 get_info 不计数）
        allowed, info = limiter.is_allowed(key)
        assert allowed is True

    def test_get_info_reflects_current_state(self):
        """get_info 返回的 remaining 应与 is_allowed 一致"""
        limiter = SlidingWindowLimiter(max_requests=5, burst=2)
        key = "test_getinfo_state"

        limiter.is_allowed(key)
        limiter.is_allowed(key)

        info = limiter.get_info(key)
        assert info["remaining"] == 5  # 7 - 2 = 5


class TestSlidingWindowLimiterThreadSafety:
    """SlidingWindowLimiter 线程安全"""

    def test_concurrent_is_allowed_does_not_exceed_limit(self):
        """并发调用 is_allowed 不应超过限流上限"""
        max_req = 50
        burst = 5
        limiter = SlidingWindowLimiter(max_requests=max_req, burst=burst)
        key = "concurrent_key"
        total_limit = max_req + burst

        allowed_count = 0
        lock = threading.Lock()

        def try_request():
            nonlocal allowed_count
            allowed, _ = limiter.is_allowed(key)
            if allowed:
                with lock:
                    allowed_count += 1

        threads = []
        # 发起比上限更多的请求
        for _ in range(total_limit + 20):
            t = threading.Thread(target=try_request)
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 允许通过的次数不应超过 total_limit
        assert allowed_count <= total_limit


# ---------------------------------------------------------------------------
# check_rate_limit 函数测试
# ---------------------------------------------------------------------------

class TestCheckRateLimit:
    """check_rate_limit 函数"""

    def test_returns_true_when_rate_limit_disabled(self, monkeypatch):
        """rate_limit_enabled=False 时始终放行"""
        import config
        monkeypatch.setattr(config.settings, "rate_limit_enabled", False)
        # 重置全局 limiter 以避免缓存
        monkeypatch.setattr("rate_limiter._limiter", None)

        allowed, info = check_rate_limit("some_client")
        assert allowed is True
        assert info == {"limit": 0, "remaining": 0, "reset_at": 0}

    def test_returns_limiter_result_when_enabled(self, monkeypatch):
        """rate_limit_enabled=True 时委托给 limiter"""
        import config
        monkeypatch.setattr(config.settings, "rate_limit_enabled", True)
        monkeypatch.setattr(config.settings, "rate_limit_requests_per_minute", 5)
        monkeypatch.setattr(config.settings, "rate_limit_burst", 1)
        # 重置全局 limiter，让 get_limiter() 使用新的 settings 值重建
        monkeypatch.setattr("rate_limiter._limiter", None)

        # 连续请求直到被限流 (max_requests=5, burst=1, total=6)
        key = "test_enabled_client"
        results = []
        for _ in range(8):
            allowed, info = check_rate_limit(key)
            results.append(allowed)

        # 应该有被限流的记录
        assert not all(results), "应有限流发生"

    def test_uses_settings_values(self, monkeypatch):
        """应使用 settings 中的限流参数"""
        import config
        monkeypatch.setattr(config.settings, "rate_limit_enabled", True)
        monkeypatch.setattr(config.settings, "rate_limit_requests_per_minute", 2)
        monkeypatch.setattr(config.settings, "rate_limit_burst", 0)
        monkeypatch.setattr("rate_limiter._limiter", None)

        key = "test_settings_client"
        allowed1, info1 = check_rate_limit(key)
        allowed2, info2 = check_rate_limit(key)
        allowed3, info3 = check_rate_limit(key)

        assert allowed1 is True
        assert allowed2 is True
        assert allowed3 is False  # max_requests=2, burst=0, 第3次被限


# ---------------------------------------------------------------------------
# get_client_id 函数测试
# ---------------------------------------------------------------------------

class TestGetClientId:
    """get_client_id 函数"""

    def test_prefers_api_key_header(self):
        """X-API-Key 优先级最高"""
        req = _MockRequest(
            headers={"X-API-Key": "test-key-123"},
            remote_addr="1.2.3.4"
        )
        result = get_client_id(req)
        assert result == "key:test-key-123"

    def test_uses_authorization_header_without_bearer(self):
        """Authorization: Bearer xxx 取 xxx 部分"""
        req = _MockRequest(
            headers={"Authorization": "Bearer my-token-abc"},
            remote_addr="5.6.7.8"
        )
        result = get_client_id(req)
        assert result == "key:my-token-abc"

    def test_api_key_truncated_to_32_chars(self):
        """API Key 截取前 32 字符"""
        long_key = "a" * 64
        req = _MockRequest(
            headers={"X-API-Key": long_key},
            remote_addr="9.10.11.12"
        )
        result = get_client_id(req)
        assert result == f"key:{'a' * 32}"
        assert len(result.split(":")[1]) == 32

    def test_falls_back_to_remote_addr(self):
        """无 API Key 时使用 remote_addr"""
        req = _MockRequest(headers={}, remote_addr="192.168.1.1")
        result = get_client_id(req)
        assert result == "ip:192.168.1.1"

    def test_unknown_when_no_remote_addr(self):
        """无 remote_addr 时使用 'unknown'"""
        req = _MockRequest(headers={}, remote_addr=None)
        result = get_client_id(req)
        assert result == "ip:unknown"

    def test_api_key_overrides_ip(self):
        """API Key 优先于 IP"""
        req = _MockRequest(
            headers={"X-API-Key": "my-key"},
            remote_addr="10.0.0.1"
        )
        result = get_client_id(req)
        assert result.startswith("key:")


# ---------------------------------------------------------------------------
# 辅助类
# ---------------------------------------------------------------------------

class _MockRequest:
    """模拟请求对象"""

    def __init__(self, headers=None, remote_addr=None):
        self.headers = headers or {}
        self.remote_addr = remote_addr
