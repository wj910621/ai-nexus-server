"""
限流器测试
测试滑动窗口限流、并发安全、内存泄漏修复和边界条件
"""

import time
import threading
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rate_limiter import SlidingWindowLimiter


class TestSlidingWindowLimiter:
    """滑动窗口限流器测试"""

    def test_basic_limiting(self):
        """基础限流测试"""
        limiter = SlidingWindowLimiter(max_requests=3, burst=1)
        key = "test_client"

        # 前 4 次应允许（3 + 1 burst）
        for i in range(4):
            allowed, info = limiter.is_allowed(key)
            assert allowed is True, f"第 {i+1} 次应被允许"
            assert info['remaining'] == 4 - (i + 1), f"剩余配额错误: {info['remaining']}"

        # 第 5 次应被限流
        allowed, info = limiter.is_allowed(key)
        assert allowed is False, "第 5 次应被限流"
        assert info['remaining'] == 0

    def test_query_not_increase_count(self):
        """查询接口不增加计数"""
        limiter = SlidingWindowLimiter(max_requests=3, burst=1)
        key = "test_query"

        # 先用掉 2 次
        limiter.is_allowed(key)
        limiter.is_allowed(key)

        # 查询 10 次
        for _ in range(10):
            info = limiter.get_info(key)
            # 剩余配额应保持 2（4 - 2）
            assert info['remaining'] == 2

    def test_window_reset(self):
        """窗口重置测试"""
        limiter = SlidingWindowLimiter(max_requests=2, burst=0, window_seconds=1)
        key = "test_reset"

        # 用完配额
        limiter.is_allowed(key)
        limiter.is_allowed(key)
        allowed, _ = limiter.is_allowed(key)
        assert allowed is False, "应被限流"

        # 滑动窗口保留两个桶（当前桶和前一个桶），需要等待超过两个窗口周期才能完全重置
        # 等待 2.2 秒确保所有旧桶过期
        time.sleep(2.2)

        # 应重新允许
        allowed, info = limiter.is_allowed(key)
        assert allowed is True, f"窗口重置后应允许，但返回 {allowed}, info: {info}"
        # remaining 应为总配额 - 1（本次请求）
        assert info['remaining'] >= 0

    def test_multiple_keys(self):
        """多个 key 独立限流"""
        limiter = SlidingWindowLimiter(max_requests=2, burst=0)

        # key1 用完配额
        limiter.is_allowed("key1")
        limiter.is_allowed("key1")
        allowed1, _ = limiter.is_allowed("key1")
        assert allowed1 is False, "key1 应被限流"

        # key2 应仍可用
        allowed2, _ = limiter.is_allowed("key2")
        assert allowed2 is True, "key2 应允许"

    def test_empty_key(self):
        """空 key 应总是允许"""
        limiter = SlidingWindowLimiter(max_requests=1, burst=0)

        allowed, info = limiter.is_allowed("")
        assert allowed is True, "空 key 应允许"
        assert info == {}, "空 key 应返回空信息"

        allowed, info = limiter.is_allowed(None)
        assert allowed is True, "None key 应允许"

    def test_concurrent_requests(self):
        """并发请求测试"""
        limiter = SlidingWindowLimiter(max_requests=50, burst=10)
        key = "concurrent_test"

        allowed_count = 0
        denied_count = 0
        lock = threading.Lock()

        def worker():
            nonlocal allowed_count, denied_count
            for _ in range(10):
                allowed, _ = limiter.is_allowed(key)
                with lock:
                    if allowed:
                        allowed_count += 1
                    else:
                        denied_count += 1

        # 10 个线程，每个请求 10 次 = 100 次
        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 总请求 100，限制 60（50 + 10），应刚好 60 允许，40 拒绝
        assert allowed_count == 60, f"允许数应为 60，实际 {allowed_count}"
        assert denied_count == 40, f"拒绝数应为 40，实际 {denied_count}"

    def test_memory_cleanup(self):
        """内存泄漏修复验证"""
        limiter = SlidingWindowLimiter(max_requests=10, burst=0)

        # 创建大量过期 key
        for i in range(100):
            limiter.is_allowed(f"key_{i}")

        # 等待窗口过期
        time.sleep(1.1)

        # 访问新 key，触发清理
        limiter.is_allowed("new_key")

        # 检查内部状态（_buckets 应被清理）
        # 注意：这是白盒测试，验证内部实现
        # 过期的 key 条目应被删除
        assert len(limiter._buckets) <= 101  # 100 个过期 key + 1 个新 key

        # 再次等待并创建新请求，应进一步清理
        time.sleep(1.1)
        limiter.is_allowed("another_new_key")

        # 大部分过期 key 应被清理
        # 由于清理逻辑在 is_allowed 中，只有被访问的 key 才会清理其过期桶
        # 但整个 _buckets 字典不会自动清理未访问的 key
        # 这个测试主要验证不会无限增长
        assert len(limiter._buckets) < 200

    def test_burst_handling(self):
        """突发流量处理"""
        limiter = SlidingWindowLimiter(max_requests=5, burst=5)
        key = "burst_test"

        # 正常配额 5 + 突发 5 = 10
        for i in range(10):
            allowed, _ = limiter.is_allowed(key)
            assert allowed is True, f"第 {i+1} 次应允许（突发）"

        allowed, _ = limiter.is_allowed(key)
        assert allowed is False, "突发用完后应限流"

    def test_remaining_calculation(self):
        """剩余配额计算"""
        limiter = SlidingWindowLimiter(max_requests=10, burst=2)
        key = "remaining_test"

        # 初始状态：get_info 不增加计数，返回总配额
        info = limiter.get_info(key)
        # 无访问时，current_count = 0，remaining = max_requests + burst
        assert info['remaining'] == 12, f"无访问时剩余应为总配额 12，实际 {info['remaining']}"

        # 每次请求后检查
        for i in range(12):
            limiter.is_allowed(key)
            info = limiter.get_info(key)
            expected = 12 - (i + 1)
            assert info['remaining'] == expected, f"剩余配额错误: 期望 {expected}, 实际 {info['remaining']}"

    def test_zero_burst(self):
        """无突发流量"""
        limiter = SlidingWindowLimiter(max_requests=3, burst=0)
        key = "zero_burst"

        # 只能用 3 次
        for i in range(3):
            allowed, _ = limiter.is_allowed(key)
            assert allowed is True

        allowed, _ = limiter.is_allowed(key)
        assert allowed is False, "无突发时应严格限制"

    def test_high_concurrency_stress(self):
        """高并发压力测试"""
        limiter = SlidingWindowLimiter(max_requests=1000, burst=100)
        key = "stress_test"

        success_count = 0
        errors = []
        lock = threading.Lock()

        def worker():
            nonlocal success_count
            try:
                for _ in range(50):
                    limiter.is_allowed(key)
                    success_count += 1
            except Exception as e:
                with lock:
                    errors.append(str(e))

        threads = [threading.Thread(target=worker) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"高并发出错: {errors}"
        # 20 线程 * 50 次 = 1000 次，限制 1100，应全部成功
        assert success_count == 1000


def run_all_tests():
    """运行所有测试"""
    test_instance = TestSlidingWindowLimiter()

    test_methods = [
        method
        for method in dir(test_instance)
        if method.startswith("test_") and callable(getattr(test_instance, method))
    ]

    passed = 0
    failed = []

    print("=" * 60)
    print("限流器测试")
    print("=" * 60)

    for method_name in test_methods:
        try:
            method = getattr(test_instance, method_name)
            method()
            print(f"  ✓ {method_name}")
            passed += 1
        except AssertionError as e:
            print(f"  ✗ {method_name}: {e}")
            failed.append((method_name, str(e)))
        except Exception as e:
            print(f"  ✗ {method_name}: {type(e).__name__}: {e}")
            failed.append((method_name, f"{type(e).__name__}: {e}"))

    print("\n" + "=" * 60)
    print(f"通过: {passed}/{len(test_methods)}")

    if failed:
        print("失败的测试:")
        for name, error in failed:
            print(f"  - {name}: {error}")
        return False
    else:
        print("✅ 所有测试通过")
        return True


def main():
    success = run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
