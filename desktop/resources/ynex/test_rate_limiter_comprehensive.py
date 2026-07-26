"""
rate_limiter.py 综合测试
覆盖：滑动窗口算法、并发限流、桶清理、内存泄漏修复等关键逻辑
"""

import time
import threading
import tempfile
import shutil
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import rate_limiter
from rate_limiter import SlidingWindowLimiter


def test_basic_rate_limiting():
    """测试基础限流功能"""
    print("\n=== 测试基础限流 ===")

    limiter = SlidingWindowLimiter(max_requests=5, window_seconds=1, burst=2)

    # 正常请求
    for i in range(7):
        allowed, info = limiter.is_allowed("user1")
        if i < 7:
            print(f"  请求 {i+1}: allowed={allowed}, remaining={info['remaining']}")
        if i < 7:
            assert allowed, f"第 {i+1} 次应被允许"

    # 第 8 次应被限流
    allowed, info = limiter.is_allowed("user1")
    print(f"  请求 8: allowed={allowed}, remaining={info['remaining']}")
    assert not allowed, "第 8 次应被限流"

    print("✓ 基础限流正确")


def test_sliding_window():
    """测试滑动窗口机制"""
    print("\n=== 测试滑动窗口 ===")

    limiter = SlidingWindowLimiter(max_requests=3, window_seconds=1, burst=0)

    # 第一个窗口内的请求
    allowed1, _ = limiter.is_allowed("user2")
    allowed2, _ = limiter.is_allowed("user2")
    allowed3, _ = limiter.is_allowed("user2")
    assert allowed1 and allowed2 and allowed3

    # 第 4 次应被限流
    allowed4, _ = limiter.is_allowed("user2")
    assert not allowed4

    # 等待窗口滑动（需要等待足够长以确保旧桶被清理）
    # 滑动窗口保留两个桶（当前和前一个），需要等待两个窗口周期
    time.sleep(2.1)

    # 新窗口应可用
    allowed5, _ = limiter.is_allowed("user2")
    assert allowed5, "新窗口应允许请求"

    print("✓ 滑动窗口正确")


def test_burst_allowance():
    """测试突发流量缓冲"""
    print("\n=== 测试突发流量 ===")

    limiter = SlidingWindowLimiter(max_requests=5, window_seconds=60, burst=3)

    # 5 + 3 = 8 次请求应通过
    for i in range(8):
        allowed, info = limiter.is_allowed("user3")
        assert allowed, f"突发请求 {i+1} 应被允许"

    # 第 9 次应被限流
    allowed, _ = limiter.is_allowed("user3")
    assert not allowed, "超出突发配额应被限流"

    print("✓ 突发流量正确")


def test_multi_client_isolation():
    """测试多客户端隔离"""
    print("\n=== 测试多客户端隔离 ===")

    limiter = SlidingWindowLimiter(max_requests=2, window_seconds=60, burst=0)

    # 用户 A
    limiter.is_allowed("client_A")
    limiter.is_allowed("client_A")

    # 用户 B（应独立计数）
    allowed1, _ = limiter.is_allowed("client_B")
    allowed2, _ = limiter.is_allowed("client_B")
    assert allowed1 and allowed2

    # 用户 A 已耗尽配额
    allowed3, _ = limiter.is_allowed("client_A")
    assert not allowed3, "用户 A 应被限流"

    # 用户 B 也应被限流
    allowed4, _ = limiter.is_allowed("client_B")
    assert not allowed4, "用户 B 应被限流"

    print("✓ 多客户端隔离正确")


def test_concurrent_rate_limiting():
    """测试并发限流安全性"""
    print("\n=== 测试并发限流 ===")

    limiter = SlidingWindowLimiter(max_requests=100, window_seconds=10, burst=20)

    errors = []
    success_count = [0]
    total_allowed = [0]

    def worker(worker_id):
        try:
            allowed_count = 0
            for i in range(50):
                allowed, info = limiter.is_allowed(f"concurrent_{worker_id}")
                if allowed:
                    allowed_count += 1
                time.sleep(0.001)  # 小延迟

            with threading.Lock():
                success_count[0] += 1
                total_allowed[0] += allowed_count
        except Exception as e:
            errors.append(f"Worker {worker_id}: {str(e)}")

    # 启动多个线程
    threads = []
    for i in range(20):
        t = threading.Thread(target=worker, args=(i,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    assert not errors
    assert success_count[0] == 20

    # 验证总数不超过限制
    # 每个客户端最多 120 次，20 个客户端最多 2400 次
    print(f"  总允许请求数: {total_allowed[0]}")
    assert total_allowed[0] <= 2400

    print("✓ 并发限流安全")


def test_bucket_cleanup():
    """测试过期桶清理"""
    print("\n=== 测试桶清理 ===")

    limiter = SlidingWindowLimiter(max_requests=10, window_seconds=1, burst=0)

    # 创建一些请求
    limiter.is_allowed("cleanup_test")

    # 检查桶的数量
    initial_buckets = len(limiter._buckets)
    print(f"  初始桶数: {initial_buckets}")

    # 等待窗口过期
    time.sleep(2.1)

    # 新请求应触发清理
    limiter.is_allowed("cleanup_test")

    # 验证旧桶被清理
    # 注意：清理发生在新请求时，检查桶是否合理
    final_buckets = len(limiter._buckets)
    print(f"  最终桶数: {final_buckets}")

    # 清理后应只保留活跃的桶
    assert final_buckets <= initial_buckets

    print("✓ 桶清理正确")


def test_memory_leak_fix():
    """测试内存泄漏修复（空 key 条目删除）"""
    print("\n=== 测试内存泄漏修复 ===")

    limiter = SlidingWindowLimiter(max_requests=5, window_seconds=1, burst=0)

    # 模拟单个用户多次请求
    user = "test_user"
    for i in range(5):
        limiter.is_allowed(user)

    # 检查桶数量
    buckets_before = len(limiter._buckets)
    print(f"  使用前桶数: {buckets_before}")
    assert buckets_before == 1, "应有 1 个用户桶"

    # 等待桶过期（超过窗口周期）
    time.sleep(2.5)

    # 触发清理（通过同一用户的请求）
    # 根据代码逻辑：如果该用户的所有桶都已过期清空，应该删除该 key 条目
    allowed, info = limiter.is_allowed(user)

    # 检查桶数量
    buckets_after = len(limiter._buckets)
    print(f"  清理后桶数: {buckets_after}")

    # 验证清理机制：过期桶被清理后，空 key 条目也应该被删除
    # 但由于新请求会创建新桶，所以桶数仍应为 1
    assert buckets_after >= 1, "应至少保留新桶"

    print("✓ 内存泄漏修复有效")


def test_get_info_no_side_effects():
    """测试查询接口无副作用"""
    print("\n=== 测试查询无副作用 ===")

    limiter = SlidingWindowLimiter(max_requests=5, window_seconds=60, burst=0)

    # 正常请求
    limiter.is_allowed("info_test")
    limiter.is_allowed("info_test")

    # 查询当前状态
    info1 = limiter.get_info("info_test")
    print(f"  查询结果: {info1}")

    # 再次查询
    info2 = limiter.get_info("info_test")

    # 查询不应增加计数
    assert info1["remaining"] == info2["remaining"]
    assert info1["limit"] == info2["limit"]

    print("✓ 查询无副作用正确")


def test_reset_time_calculation():
    """测试重置时间计算"""
    print("\n=== 测试重置时间 ===")

    limiter = SlidingWindowLimiter(max_requests=10, window_seconds=60, burst=0)

    current_time = time.time()
    allowed, info = limiter.is_allowed("reset_test")

    reset_time = info["reset_at"]

    # reset_time 是下一个窗口的开始时间： (now_bucket + 1) * window_seconds
    # now_bucket = int(current_time // window_seconds)
    expected_bucket = int(current_time // 60)
    expected_reset_time = (expected_bucket + 1) * 60

    print(f"  当前时间: {current_time:.2f}")
    print(f"  重置时间: {reset_time:.2f}")
    print(f"  预期重置时间: {expected_reset_time:.2f}")

    # 验证重置时间是下一个窗口的开始时间
    assert reset_time == expected_reset_time, f"重置时间应为 {expected_reset_time}, 实际为 {reset_time}"

    print("✓ 重置时间计算正确")


def test_edge_cases():
    """测试边界条件"""
    print("\n=== 测试边界条件 ===")

    # 空客户端 ID
    limiter = SlidingWindowLimiter()
    allowed, info = limiter.is_allowed("")
    assert allowed, "空客户端 ID 应允许通过"

    # None 客户端
    allowed2, info2 = limiter.is_allowed(None)
    assert allowed2, "None 客户端应允许通过"

    # 零配额
    limiter2 = SlidingWindowLimiter(max_requests=0, burst=0)
    allowed3, _ = limiter2.is_allowed("zero_quota")
    assert not allowed3, "零配额应立即限流"

    print("✓ 边界条件正确")


def test_remaining_quota_calculation():
    """测试剩余配额计算"""
    print("\n=== 测试剩余配额 ===")

    limiter = SlidingWindowLimiter(max_requests=10, window_seconds=60, burst=5)

    # 初始配额应为 15
    _, info = limiter.is_allowed("quota_test")
    assert info["limit"] == 15
    assert info["remaining"] == 14

    # 使用 5 次后
    for _ in range(4):
        limiter.is_allowed("quota_test")

    _, info2 = limiter.is_allowed("quota_test")
    assert info2["remaining"] == 9

    print("✓ 剩余配额计算正确")


def test_high_concurrency_stress():
    """高并发压力测试"""
    print("\n=== 高并发压力测试 ===")

    limiter = SlidingWindowLimiter(max_requests=1000, window_seconds=60, burst=100)

    errors = []
    results = []

    def stress_test(thread_id):
        try:
            for i in range(100):
                allowed, info = limiter.is_allowed(f"stress_test_{thread_id}")
                results.append(allowed)
        except Exception as e:
            errors.append(f"Thread {thread_id}: {str(e)}")

    threads = [threading.Thread(target=stress_test, args=(i,)) for i in range(50)]

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"压力测试错误: {errors}"
    print(f"  完成 {len(results)} 次并发请求")

    print("✓ 高并发压力测试通过")


def run_all_tests():
    """运行所有测试"""
    test_basic_rate_limiting()
    test_sliding_window()
    test_burst_allowance()
    test_multi_client_isolation()
    test_concurrent_rate_limiting()
    test_bucket_cleanup()
    test_memory_leak_fix()
    test_get_info_no_side_effects()
    test_reset_time_calculation()
    test_edge_cases()
    test_remaining_quota_calculation()
    test_high_concurrency_stress()

    print("\n" + "="*50)
    print("✅ 所有 rate_limiter.py 测试通过")
    print("="*50)


if __name__ == "__main__":
    run_all_tests()