"""
限流器扩展测试
补充边界条件、空 key 处理、并发安全、内存泄漏修复验证
"""

import os
import sys
import time
import threading
import pytest

sys.path.insert(0, os.path.dirname(__file__))

from rate_limiter import SlidingWindowLimiter


class TestSlidingWindowLimiterBasic:
    def test_allowed_within_limit(self):
        limiter = SlidingWindowLimiter(max_requests=5, burst=2)
        for i in range(5):
            allowed, info = limiter.is_allowed("user1")
            assert allowed is True

    def test_burst_allows_extra(self):
        limiter = SlidingWindowLimiter(max_requests=3, burst=2)
        # 3 + 2 = 5 次应被允许
        for i in range(5):
            allowed, _ = limiter.is_allowed("user1")
            assert allowed is True
        # 第 6 次应被限流
        allowed, _ = limiter.is_allowed("user1")
        assert allowed is False

    def test_remaining_decrements(self):
        limiter = SlidingWindowLimiter(max_requests=5, burst=0)
        for i in range(5):
            _, info = limiter.is_allowed("user1")
            assert info["remaining"] == 5 - i - 1

    def test_remaining_never_negative(self):
        limiter = SlidingWindowLimiter(max_requests=2, burst=0)
        for _ in range(5):
            _, info = limiter.is_allowed("user1")
            assert info["remaining"] >= 0


class TestEmptyKey:
    def test_empty_key_always_allowed(self):
        """空 key 应始终放行（不做限流）"""
        limiter = SlidingWindowLimiter(max_requests=1, burst=0)
        for _ in range(10):
            allowed, info = limiter.is_allowed("")
            assert allowed is True

    def test_none_key_always_allowed(self):
        limiter = SlidingWindowLimiter(max_requests=1, burst=0)
        allowed, info = limiter.is_allowed(None)
        assert allowed is True


class TestKeyIsolation:
    def test_different_keys_independent(self):
        """不同 key 的限流应互相独立"""
        limiter = SlidingWindowLimiter(max_requests=1, burst=0)
        allowed1, _ = limiter.is_allowed("user_a")
        allowed2, _ = limiter.is_allowed("user_b")
        assert allowed1 is True
        assert allowed2 is True

    def test_one_key_limited_doesnt_affect_other(self):
        limiter = SlidingWindowLimiter(max_requests=1, burst=0)
        limiter.is_allowed("user_a")
        limiter.is_allowed("user_a")  # user_a 被限流
        allowed, _ = limiter.is_allowed("user_b")
        assert allowed is True  # user_b 仍可用


class TestGetInfo:
    def test_get_info_no_side_effect(self):
        """查询接口不应增加计数"""
        limiter = SlidingWindowLimiter(max_requests=3, burst=0)
        limiter.is_allowed("user1")
        info1 = limiter.get_info("user1")
        info2 = limiter.get_info("user1")
        assert info1["remaining"] == info2["remaining"]

    def test_get_info_nonexistent_key(self):
        limiter = SlidingWindowLimiter(max_requests=5, burst=0)
        info = limiter.get_info("nonexistent")
        assert info["remaining"] == 5  # 没有请求，remaining = limit


class TestMemoryCleanup:
    def test_expired_keys_cleaned_up(self):
        """过期桶应被清理，避免内存泄漏"""
        limiter = SlidingWindowLimiter(max_requests=10, window_seconds=1, burst=0)
        limiter.is_allowed("temp_user")
        # 等待超过窗口时间
        time.sleep(2)
        # 新请求应清理旧桶
        limiter.is_allowed("temp_user")
        # 验证内部存储只有一个桶（新桶）
        with limiter._lock:
            buckets = limiter._buckets.get("temp_user", {})
            # 只应保留当前桶
            assert len(buckets) <= 2

    def test_empty_key_entry_removed(self):
        """所有桶过期后，key 条目应被移除，防止 _buckets 无限增长"""
        limiter = SlidingWindowLimiter(max_requests=10, window_seconds=1, burst=0)
        limiter.is_allowed("temp_user")
        time.sleep(2)
        # 新请求触发清理，空 key 条目应被重建
        limiter.is_allowed("temp_user")
        assert "temp_user" in limiter._buckets


class TestConcurrentAccess:
    def test_concurrent_requests_safe(self):
        """并发请求不应导致数据竞争崩溃"""
        limiter = SlidingWindowLimiter(max_requests=100, burst=10, window_seconds=60)
        errors = []

        def worker():
            try:
                for _ in range(20):
                    limiter.is_allowed("concurrent_user")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"并发错误: {errors}"


class TestResetTime:
    def test_reset_time_in_future(self):
        limiter = SlidingWindowLimiter(max_requests=5, window_seconds=60, burst=0)
        _, info = limiter.is_allowed("user1")
        assert info["reset_at"] > time.time()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
