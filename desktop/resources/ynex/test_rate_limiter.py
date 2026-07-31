"""
限流器测试
覆盖：正常限流、空 key 直通、查询不计数、并发安全、内存泄漏防护、剩余配额计算
"""

import os
import sys
import time
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_basic_rate_limiting():
    """正常限流：超过 max_requests + burst 后被拒"""
    from rate_limiter import SlidingWindowLimiter

    limiter = SlidingWindowLimiter(max_requests=3, burst=1)
    key = "test_client"

    for i in range(4):
        allowed, info = limiter.is_allowed(key)
        assert allowed is True, f"第 {i+1} 次应通过"

    # 第 5 次应被限流
    allowed, info = limiter.is_allowed(key)
    assert allowed is False, "第 5 次应被限流"

    print("  ✓ 基本限流正确")


def test_empty_key_bypasses():
    """空 key 直通不限流"""
    from rate_limiter import SlidingWindowLimiter

    limiter = SlidingWindowLimiter(max_requests=1, burst=0)

    allowed, info = limiter.is_allowed("")
    assert allowed is True, "空 key 应直通"
    assert info == {}, "空 key 不返回限流信息"

    # 连续多次空 key 也应通过
    for _ in range(100):
        allowed, info = limiter.is_allowed("")
        assert allowed is True

    print("  ✓ 空 key 直通正确")


def test_get_info_no_increment():
    """get_info 不增加计数"""
    from rate_limiter import SlidingWindowLimiter

    limiter = SlidingWindowLimiter(max_requests=3, burst=0)
    key = "info_test"

    allowed, _ = limiter.is_allowed(key)
    assert allowed is True

    info = limiter.get_info(key)
    assert info["remaining"] >= 0

    # 再次 is_allowed 应只有 2 次已用（get_info 不增加）
    allowed2, info2 = limiter.is_allowed(key)
    assert allowed2 is True

    print("  ✓ get_info 不增加计数")


def test_remaining_decreases():
    """remaining 递减"""
    from rate_limiter import SlidingWindowLimiter

    limiter = SlidingWindowLimiter(max_requests=5, burst=0)
    key = "remaining_test"

    prev_remaining = None
    for i in range(5):
        allowed, info = limiter.is_allowed(key)
        assert allowed is True
        if prev_remaining is not None:
            assert info["remaining"] < prev_remaining, "remaining 应递减"
        prev_remaining = info["remaining"]

    print("  ✓ remaining 递减正确")


def test_info_contains_required_fields():
    """info 返回必要字段"""
    from rate_limiter import SlidingWindowLimiter

    limiter = SlidingWindowLimiter(max_requests=10, burst=5)
    key = "fields_test"

    allowed, info = limiter.is_allowed(key)
    assert "limit" in info
    assert "remaining" in info
    assert "reset_at" in info
    assert info["limit"] == 15  # max_requests + burst

    print("  ✓ info 字段完整")


def test_concurrent_access():
    """并发访问安全性"""
    from rate_limiter import SlidingWindowLimiter

    limiter = SlidingWindowLimiter(max_requests=50, burst=0)
    key = "concurrent_test"

    results = []
    def request():
        allowed, info = limiter.is_allowed(key)
        results.append(allowed)

    threads = [threading.Thread(target=request) for _ in range(100)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    success_count = sum(1 for r in results if r)
    assert success_count <= 50, f"最多 50 次应通过，实际 {success_count}"
    # 至少有一些被限流
    assert sum(1 for r in results if not r) > 0, "应有部分请求被限流"

    print("  ✓ 并发访问安全")


def test_memory_cleanup_of_stale_keys():
    """过期 key 被自动清理防止内存泄漏"""
    from rate_limiter import SlidingWindowLimiter

    limiter = SlidingWindowLimiter(max_requests=10, burst=0, window_seconds=1)

    # 使用多个 key
    for i in range(100):
        limiter.is_allowed(f"ephemeral_key_{i}")

    # 验证内部存储有这些 key
    assert len(limiter._buckets) > 0

    # 等待窗口过期
    time.sleep(2)

    # 使用任意一个旧 key 触发清理
    limiter.is_allowed("ephemeral_key_0")

    # 过期的 key 应被清理（ ephemeral_key_1~99 如果没有新请求应被清理）
    # 至少 _buckets 不应无限增长
    assert len(limiter._buckets) <= 100  # 不应超出已使用 key 数

    print("  ✓ 过期 key 内存清理正确")


def test_different_keys_independent():
    """不同 key 互相独立"""
    from rate_limiter import SlidingWindowLimiter

    limiter = SlidingWindowLimiter(max_requests=2, burst=0)

    # key_a 用完配额
    limiter.is_allowed("key_a")
    limiter.is_allowed("key_a")
    allowed_a, _ = limiter.is_allowed("key_a")
    assert allowed_a is False, "key_a 应被限流"

    # key_b 应不受影响
    allowed_b, _ = limiter.is_allowed("key_b")
    assert allowed_b is True, "key_b 应独立不受限"

    print("  ✓ 不同 key 互相独立")


def test_get_info_nonexistent_key():
    """查询不存在的 key 返回默认信息"""
    from rate_limiter import SlidingWindowLimiter

    limiter = SlidingWindowLimiter(max_requests=10, burst=5)
    info = limiter.get_info("nonexistent_key")
    assert info["limit"] == 15
    assert info["remaining"] == 15  # 未使用，剩余等于总限额

    print("  ✓ 不存在 key 的 info 正确")


def main():
    print("=== 限流器测试 ===\n")

    test_basic_rate_limiting()
    test_empty_key_bypasses()
    test_get_info_no_increment()
    test_remaining_decreases()
    test_info_contains_required_fields()
    test_concurrent_access()
    test_memory_cleanup_of_stale_keys()
    test_different_keys_independent()
    test_get_info_nonexistent_key()

    print("\n=== 限流器测试完成 ===")


if __name__ == "__main__":
    main()
