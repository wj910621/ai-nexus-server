"""
限流器测试
覆盖滑动窗口计数、突发缓冲、空 Key、桶清理与并发安全。
"""

import threading
from unittest.mock import patch

from rate_limiter import SlidingWindowLimiter


def test_basic_limit():
    print("1. 基础限流...")
    limiter = SlidingWindowLimiter(max_requests=3, burst=1)
    key = "test_client"

    results = [limiter.is_allowed(key)[0] for _ in range(5)]
    assert results == [True, True, True, True, False], f"意外结果: {results}"

    info = limiter.is_allowed(key)[1]
    assert info["limit"] == 4
    assert info["remaining"] == 0
    print("  ✓ 基础限流正确")


def test_empty_key_allowed():
    print("2. 空 Key 放行...")
    limiter = SlidingWindowLimiter(max_requests=1, burst=0)
    allowed, info = limiter.is_allowed("")
    assert allowed is True
    assert info == {}
    print("  ✓ 空 Key 正确放行")


def test_get_info_read_only():
    print("3. 查询接口只读...")
    limiter = SlidingWindowLimiter(max_requests=3, burst=0)
    key = "read_only_client"

    for _ in range(2):
        limiter.is_allowed(key)

    info_before = limiter.get_info(key)
    assert info_before["remaining"] == 1

    info_after = limiter.get_info(key)
    assert info_after["remaining"] == 1
    assert info_before == info_after
    print("  ✓ 查询接口不增加计数")


def test_bucket_cleanup():
    print("4. 过期桶清理与内存泄漏修复...")
    limiter = SlidingWindowLimiter(max_requests=3, burst=0, window_seconds=60)
    key = "cleanup_client"

    # 模拟在时间桶 0 产生请求
    with patch("time.time", return_value=30):
        limiter.is_allowed(key)
        assert key in limiter._buckets

    # 推进到时间桶 3，旧桶应被清理
    with patch("time.time", return_value=190):
        allowed, info = limiter.is_allowed(key)
        assert allowed is True
        assert info["remaining"] == 2
        assert 0 not in limiter._buckets[key]
        assert 3 in limiter._buckets[key]
    print("  ✓ 过期桶清理正确")


def test_window_slide():
    print("5. 滑动窗口配额恢复...")
    limiter = SlidingWindowLimiter(max_requests=2, burst=0, window_seconds=60)
    key = "slide_client"

    with patch("time.time", return_value=30):
        assert limiter.is_allowed(key)[0] is True
        assert limiter.is_allowed(key)[0] is True
        assert limiter.is_allowed(key)[0] is False

    # 进入下下个窗口，旧桶已过期，配额应恢复
    with patch("time.time", return_value=130):
        assert limiter.is_allowed(key)[0] is True
        assert limiter.is_allowed(key)[0] is True
        assert limiter.is_allowed(key)[0] is False
    print("  ✓ 滑动窗口配额恢复正确")


def test_concurrency():
    print("6. 并发安全...")
    limiter = SlidingWindowLimiter(max_requests=50, burst=0)
    key = "concurrent_client"
    allowed_count = {"value": 0}
    rejected_count = {"value": 0}
    lock = threading.Lock()

    def worker():
        allowed, _ = limiter.is_allowed(key)
        with lock:
            if allowed:
                allowed_count["value"] += 1
            else:
                rejected_count["value"] += 1

    threads = [threading.Thread(target=worker) for _ in range(100)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert allowed_count["value"] == 50, f"应允许 50，实际 {allowed_count['value']}"
    assert rejected_count["value"] == 50, f"应拒绝 50，实际 {rejected_count['value']}"
    print(f"  ✓ 并发安全：允许 {allowed_count['value']}，拒绝 {rejected_count['value']}")


def main():
    print("=== 限流器测试 ===\n")
    test_basic_limit()
    test_empty_key_allowed()
    test_get_info_read_only()
    test_bucket_cleanup()
    test_window_slide()
    test_concurrency()
    print("\n=== 限流器测试全部通过 ===")


if __name__ == "__main__":
    main()
