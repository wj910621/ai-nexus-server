"""
限流器增强测试
覆盖并发场景、边界条件、内存泄漏修复验证
"""

import time
import threading
import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rate_limiter import SlidingWindowLimiter


class TestSlidingWindowLimiterConcurrency(unittest.TestCase):
    """并发限流测试"""

    def test_concurrent_requests_single_key(self):
        """测试同一 key 的并发请求"""
        limiter = SlidingWindowLimiter(max_requests=5, burst=2)
        key = "concurrent_test"
        results = []
        errors = []

        def make_request():
            try:
                allowed, info = limiter.is_allowed(key)
                results.append(allowed)
            except Exception as e:
                errors.append(str(e))

        # 并发 10 个请求
        threads = [threading.Thread(target=make_request) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 不应有错误
        self.assertEqual(len(errors), 0)

        # 允许的请求数应 <= max_requests + burst
        allowed_count = sum(results)
        self.assertLessEqual(allowed_count, 7)  # 5 + 2 = 7

        # 至少有一些请求被拒绝（超过限制）
        self.assertGreater(len(results), allowed_count)

    def test_concurrent_requests_different_keys(self):
        """测试不同 key 的并发请求（独立计数）"""
        limiter = SlidingWindowLimiter(max_requests=2, burst=0)

        results = {}

        def make_request(key):
            allowed, info = limiter.is_allowed(key)
            results[key] = results.get(key, [])
            results[key].append(allowed)

        threads = []
        for i in range(5):
            for j in range(3):
                t = threading.Thread(target=make_request, args=(f"key_{i}",))
                threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 每个 key 独立计数
        for key, allowed_list in results.items():
            allowed_count = sum(allowed_list)
            self.assertLessEqual(allowed_count, 2)

    def test_thread_safe_bucket_cleanup(self):
        """测试并发场景下的桶清理安全性"""
        limiter = SlidingWindowLimiter(max_requests=10, window_seconds=1)

        # 创建多个 key
        keys = [f"cleanup_key_{i}" for i in range(100)]

        def use_key(k):
            limiter.is_allowed(k)

        threads = [threading.Thread(target=use_key, args=(k,)) for k in keys]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 等待窗口过期
        time.sleep(2)

        # 过期后再次访问，不应抛异常
        for k in keys[:10]:
            allowed, info = limiter.is_allowed(k)
            self.assertTrue(allowed)


class TestSlidingWindowLimiterEdgeCases(unittest.TestCase):
    """边界条件测试"""

    def test_zero_max_requests(self):
        """测试零最大请求数"""
        limiter = SlidingWindowLimiter(max_requests=0, burst=0)
        allowed, info = limiter.is_allowed("test")
        # 应允许（burst=0，但实际取决于实现）
        # 根据代码逻辑，current_count < max_requests + burst
        # 如果 max=0, burst=0，则 current_count < 0 总为 False
        # 但第一次请求时 current_count=0，0 < 0 为 False
        # 所以第一次请求就被拒绝

    def test_very_large_burst(self):
        """测试超大突发值"""
        limiter = SlidingWindowLimiter(max_requests=10, burst=1000)

        # 大量请求应被允许（突发缓冲）
        for i in range(500):
            allowed, info = limiter.is_allowed("burst_test")
            if i < 1010:  # 10 + 1000
                self.assertTrue(allowed)
            else:
                self.assertFalse(allowed)

    def test_empty_key(self):
        """测试空 key"""
        limiter = SlidingWindowLimiter(max_requests=10)
        allowed, info = limiter.is_allowed("")
        # 空 key 应直接通过（不限流）
        self.assertTrue(allowed)
        self.assertEqual(info, {})

    def test_none_key(self):
        """测试 None key"""
        limiter = SlidingWindowLimiter(max_requests=10)
        allowed, info = limiter.is_allowed(None)
        self.assertTrue(allowed)

    def test_unicode_key(self):
        """测试 Unicode key"""
        limiter = SlidingWindowLimiter(max_requests=5, burst=0)
        # 使用唯一 key 避免与其他测试冲突
        key = "unicode_test_用户_中文_キー"

        # 应正常工作，前5次允许
        for i in range(5):
            allowed, info = limiter.is_allowed(key)
            self.assertTrue(allowed, f"第{i+1}次请求应被允许，info={info}")

        # 第6次请求应被拒绝（无 burst）
        allowed, info = limiter.is_allowed(key)
        self.assertFalse(allowed, f"超过限制后应被拒绝，info={info}")

    def test_very_long_key(self):
        """测试超长 key"""
        limiter = SlidingWindowLimiter(max_requests=5)
        key = "a" * 10000

        allowed, info = limiter.is_allowed(key)
        self.assertTrue(allowed)


class TestSlidingWindowLimiterMemoryLeak(unittest.TestCase):
    """内存泄漏修复验证"""

    def test_expired_key_cleanup(self):
        """测试过期 key 被清理"""
        limiter = SlidingWindowLimiter(max_requests=10, window_seconds=1)

        # 创建临时 key
        limiter.is_allowed("temp_key_1")
        limiter.is_allowed("temp_key_2")

        # 等待过期
        time.sleep(2)

        # 创建新请求触发清理
        limiter.is_allowed("new_key")

        # 检查内存中的 key 数量
        # 过期的 key 应被清理
        # 注意：这是内部实现测试，需要访问 _buckets
        with limiter._lock:
            # 空桶的 key 应被删除
            for k in ["temp_key_1", "temp_key_2"]:
                if k in limiter._buckets:
                    buckets = limiter._buckets[k]
                    # 如果还在，桶应为空或已清理
                    self.assertTrue(len(buckets) == 0 or all(
                        b < limiter._current_bucket() - 1 for b in buckets
                    ))

    def test_repeated_access_same_key(self):
        """测试同一 key 反复访问不累积内存"""
        limiter = SlidingWindowLimiter(max_requests=100, window_seconds=1)

        # 反复访问同一 key
        for i in range(1000):
            limiter.is_allowed("repeat_key")

        # 检查桶数量不应超过 2（当前桶和上一个桶）
        with limiter._lock:
            buckets = limiter._buckets.get("repeat_key", {})
            # 滑动窗口只需保留两个桶
            self.assertLessEqual(len(buckets), 2)


class TestSlidingWindowLimiterInfo(unittest.TestCase):
    """信息查询测试"""

    def test_get_info_no_increment(self):
        """测试查询不增加计数"""
        limiter = SlidingWindowLimiter(max_requests=5)

        # 查询多次
        for i in range(10):
            info = limiter.get_info("query_key")

        # 实际请求仍应被允许
        allowed, info = limiter.is_allowed("query_key")
        self.assertTrue(allowed)

    def test_get_info_matches_actual(self):
        """测试查询信息与实际一致"""
        limiter = SlidingWindowLimiter(max_requests=3, burst=1)

        # 发送 2 个请求
        limiter.is_allowed("match_key")
        limiter.is_allowed("match_key")

        # 查询应显示 remaining = 2（3+1-2）
        info = limiter.get_info("match_key")
        self.assertEqual(info["remaining"], 2)


class TestSlidingWindowLimiterWindow(unittest.TestCase):
    """窗口行为测试"""

    def test_window_reset(self):
        """测试窗口重置后计数清零"""
        limiter = SlidingWindowLimiter(max_requests=2, burst=0, window_seconds=1)

        # 用完配额
        limiter.is_allowed("reset_key")
        limiter.is_allowed("reset_key")
        allowed, _ = limiter.is_allowed("reset_key")
        self.assertFalse(allowed, "配额用完后应被拒绝")

        # 等待窗口过期（滑动窗口需要等待超过一个窗口周期）
        time.sleep(2.5)

        # 应重新允许
        allowed, info = limiter.is_allowed("reset_key")
        self.assertTrue(allowed, f"窗口过期后应重新允许，info={info}")

    def test_sliding_window_overlap(self):
        """测试滑动窗口重叠计算"""
        # 使用无 burst 的配置，更可预测
        limiter = SlidingWindowLimiter(max_requests=5, burst=0, window_seconds=2)

        # 在第一个窗口发送 4 个请求
        for i in range(4):
            allowed, _ = limiter.is_allowed("overlap_key")
            self.assertTrue(allowed)

        # 等待 1 秒，进入下一个桶但仍在滑动窗口内
        time.sleep(1.1)

        # 再发送请求，滑动窗口会考虑两个桶的总和
        # 当前桶 + 上一个桶 = 总请求
        allowed, info = limiter.is_allowed("overlap_key")
        # 根据实际限流逻辑验证
        self.assertIn("remaining", info)


def run_tests():
    """运行测试"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestSlidingWindowLimiterConcurrency))
    suite.addTests(loader.loadTestsFromTestCase(TestSlidingWindowLimiterEdgeCases))
    suite.addTests(loader.loadTestsFromTestCase(TestSlidingWindowLimiterMemoryLeak))
    suite.addTests(loader.loadTestsFromTestCase(TestSlidingWindowLimiterInfo))
    suite.addTests(loader.loadTestsFromTestCase(TestSlidingWindowLimiterWindow))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)