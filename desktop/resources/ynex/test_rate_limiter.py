"""
限流器完整测试
覆盖：滑动窗口、突发流量、并发安全、内存泄漏修复验证
"""

import time
import threading
from rate_limiter import SlidingWindowLimiter, check_rate_limit, get_client_id


def test_basic_rate_limiting():
    """测试基础限流功能"""
    print("\n=== 测试基础限流 ===")

    limiter = SlidingWindowLimiter(max_requests=3, burst=1)
    key = "test_client"

    # 正常请求（限制 3 + 突发 1 = 4）
    results = []
    for i in range(5):
        allowed, info = limiter.is_allowed(key)
        results.append((allowed, info['remaining']))
        print(f"  第 {i+1} 次: allowed={allowed}, remaining={info['remaining']}")

    # 验证前 4 次通过，第 5 次被限流
    assert results[0][0] is True
    assert results[3][0] is True
    assert results[4][0] is False, "第 5 次应被限流"
    assert results[4][1] == 0

    print("✅ 基础限流正确")


def test_sliding_window():
    """测试滑动窗口机制"""
    print("\n=== 测试滑动窗口 ===")

    # 使用短窗口便于测试
    limiter = SlidingWindowLimiter(max_requests=2, window_seconds=1, burst=0)
    key = "sliding_test"

    # 消耗配额
    limiter.is_allowed(key)
    limiter.is_allowed(key)

    # 应被限流
    allowed, _ = limiter.is_allowed(key)
    assert allowed is False

    # 等待窗口滑动
    time.sleep(1.1)

    # 应恢复配额
    allowed, info = limiter.is_allowed(key)
    assert allowed is True
    assert info['remaining'] >= 1

    print("✅ 滑动窗口正确")


def test_burst_handling():
    """测试突发流量处理"""
    print("\n=== 测试突发流量 ===")

    limiter = SlidingWindowLimiter(max_requests=5, burst=3)
    key = "burst_test"

    # 正常配额 + 突发配额 = 8
    passed = 0
    for _ in range(10):
        allowed, _ = limiter.is_allowed(key)
        if allowed:
            passed += 1

    assert passed == 8, f"应允许 8 次请求，实际 {passed}"
    print(f"✅ 突发流量处理正确（允许 {passed} 次）")


def test_memory_cleanup():
    """测试内存清理（防止内存泄漏）"""
    print("\n=== 测试内存清理 ===")

    limiter = SlidingWindowLimiter(max_requests=10, window_seconds=1)
    initial_keys = len(limiter._buckets)

    # 创建大量临时客户端
    for i in range(100):
        limiter.is_allowed(f"temp_client_{i}")

    peak_keys = len(limiter._buckets)
    assert peak_keys == 100

    # 等待过期
    time.sleep(1.5)

    # 使用一个客户端触发清理
    limiter.is_allowed("temp_client_0")

    # 验证大部分已清理
    final_keys = len(limiter._buckets)
    assert final_keys < peak_keys

    print(f"✅ 内存清理正确（峰值 {peak_keys} -> 清理后 {final_keys}）")


def test_concurrent_safety():
    """测试并发安全性"""
    print("\n=== 测试并发安全 ===")

    limiter = SlidingWindowLimiter(max_requests=50, burst=10)
    key = "concurrent_test"

    errors = []
    success_count = [0]
    lock = threading.Lock()

    def worker():
        try:
            for _ in range(20):
                allowed, info = limiter.is_allowed(key)
                if allowed:
                    with lock:
                        success_count[0] += 1
        except Exception as e:
            errors.append(str(e))

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0, f"并发错误: {errors}"
    # 总成功数应等于 max_requests + burst
    assert success_count[0] == 60, f"并发计数错误: {success_count[0]}"

    print(f"✅ 并发安全（成功 {success_count[0]} 次）")


def test_query_without_increment():
    """测试查询不增加计数"""
    print("\n=== 测试查询不增加计数 ===")

    limiter = SlidingWindowLimiter(max_requests=3, burst=0)
    key = "query_test"

    # 消耗配额
    limiter.is_allowed(key)
    limiter.is_allowed(key)

    # 多次查询
    for _ in range(10):
        info = limiter.get_info(key)
        assert info['remaining'] == 1

    # 配额应未变化
    allowed, info = limiter.is_allowed(key)
    assert allowed is True

    print("✅ 查询不增加计数")


def test_reset_time():
    """测试重置时间计算"""
    print("\n=== 测试重置时间 ===")

    limiter = SlidingWindowLimiter(max_requests=10, window_seconds=60)
    key = "reset_test"

    _, info = limiter.is_allowed(key)

    current_time = int(time.time())
    reset_time = info['reset_at']

    # 重置时间应在下一个窗口
    assert reset_time > current_time
    assert reset_time <= current_time + 120

    print(f"✅ 重置时间正确（当前 {current_time}，重置 {reset_time}）")


def test_empty_key_handling():
    """测试空 Key 处理"""
    print("\n=== 测试空 Key 处理 ===")

    limiter = SlidingWindowLimiter()

    # 空 Key 应被允许（不限流）
    allowed, info = limiter.is_allowed("")
    assert allowed is True
    assert info == {}

    allowed, info = limiter.is_allowed(None)
    assert allowed is True

    print("✅ 空 Key 处理正确")


def test_info_consistency():
    """测试查询信息一致性"""
    print("\n=== 测试查询信息一致性 ===")

    limiter = SlidingWindowLimiter(max_requests=10, burst=2)
    key = "consistency_test"

    # 执行请求
    for i in range(5):
        limiter.is_allowed(key)

    # 查询信息
    info = limiter.get_info(key)

    assert info['limit'] == 12  # max_requests + burst
    assert info['remaining'] == 7
    assert 'reset_at' in info

    print(f"✅ 查询信息一致（limit={info['limit']}, remaining={info['remaining']}）")


def main():
    print("=" * 60)
    print("  限流器完整测试")
    print("=" * 60)

    test_basic_rate_limiting()
    test_sliding_window()
    test_burst_handling()
    test_memory_cleanup()
    test_concurrent_safety()
    test_query_without_increment()
    test_reset_time()
    test_empty_key_handling()
    test_info_consistency()

    print("\n" + "=" * 60)
    print("🎉 所有限流器测试通过")
    print("=" * 60)


if __name__ == "__main__":
    main()
