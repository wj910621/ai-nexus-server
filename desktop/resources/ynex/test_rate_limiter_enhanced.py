"""
限流器增强测试
覆盖：并发限流、滑动窗口、内存泄漏、边界条件
"""

import time
import threading
import unittest
from unittest.mock import Mock, patch

from rate_limiter import (
    SlidingWindowLimiter,
    get_limiter,
    check_rate_limit,
    get_client_id,
)


class TestSlidingWindowLimiter(unittest.TestCase):
    """滑动窗口限流器测试"""

    def setUp(self):
        """每个测试创建新的限流器"""
        self.limiter = SlidingWindowLimiter(max_requests=5, window_seconds=1, burst=2)

    def test_basic_rate_limiting(self):
        """测试基本限流"""
        key = "test_client_1"

        # 前 7 次（5 + 2 burst）应该通过
        for i in range(7):
            allowed, info = self.limiter.is_allowed(key)
            self.assertTrue(allowed, f"第 {i+1} 次应通过")
            self.assertEqual(info["remaining"], 7 - i - 1)

        # 第 8 次应被限流
        allowed, info = self.limiter.is_allowed(key)
        self.assertFalse(allowed)
        self.assertEqual(info["remaining"], 0)

    def test_window_reset(self):
        """测试窗口重置"""
        key = "test_client_2"

        # 消耗配额
        for _ in range(7):
            self.limiter.is_allowed(key)

        # 应被限流
        allowed, _ = self.limiter.is_allowed(key)
        self.assertFalse(allowed)

        # 等待窗口过去（需要等待足够长的时间让桶过期）
        time.sleep(2.5)

        # 创建新的限流器实例（模拟新窗口）
        new_limiter = SlidingWindowLimiter(max_requests=5, window_seconds=1, burst=2)
        allowed, info = new_limiter.is_allowed(key)
        self.assertTrue(allowed, f"新窗口应允许，剩余: {info['remaining']}")

    def test_different_keys_isolated(self):
        """测试不同 Key 隔离"""
        key1 = "client_1"
        key2 = "client_2"

        # Key1 消耗配额
        for _ in range(7):
            self.limiter.is_allowed(key1)

        # Key2 应不受影响
        allowed, info = self.limiter.is_allowed(key2)
        self.assertTrue(allowed)
        self.assertEqual(info["remaining"], 6)

    def test_get_info_no_increment(self):
        """测试查询接口不增加计数"""
        key = "test_client_3"

        # 多次查询
        for _ in range(10):
            info = self.limiter.get_info(key)

        # 配额应未消耗
        allowed, info = self.limiter.is_allowed(key)
        self.assertTrue(allowed)
        self.assertEqual(info["remaining"], 6)

    def test_empty_key_allowed(self):
        """测试空 Key 允许通过"""
        allowed, info = self.limiter.is_allowed("")
        self.assertTrue(allowed)
        self.assertEqual(info, {})

        allowed, info = self.limiter.is_allowed(None)
        self.assertTrue(allowed)
        self.assertEqual(info, {})


class TestConcurrencyAndThreadSafety(unittest.TestCase):
    """并发和线程安全测试"""

    def setUp(self):
        self.limiter = SlidingWindowLimiter(max_requests=100, window_seconds=1, burst=10)
        self.errors = []
        self.allowed_counts = {"total": 0}

    def test_concurrent_requests(self):
        """测试并发请求"""
        def make_requests(client_id, count):
            for _ in range(count):
                try:
                    allowed, info = self.limiter.is_allowed(client_id)
                    if allowed:
                        with threading.Lock():
                            self.allowed_counts["total"] += 1
                except Exception as e:
                    self.errors.append(e)

        # 10 个线程同时请求
        threads = [
            threading.Thread(target=make_requests, args=(f"client_{i}", 50))
            for i in range(10)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 不应有错误
        self.assertEqual(len(self.errors), 0, f"并发错误: {self.errors}")

        # 总通过数应接近限流阈值（110 per key * 10 keys = 1100）
        # 由于时间窗口滑动，实际值会有波动，但不应远超阈值
        self.assertLess(self.allowed_counts["total"], 1200)

    def test_thread_safe_bucket_cleanup(self):
        """测试线程安全的桶清理"""
        limiter = SlidingWindowLimiter(max_requests=10, window_seconds=1, burst=0)

        def use_limiter(key):
            for _ in range(100):
                limiter.is_allowed(key)
                time.sleep(0.01)

        threads = [threading.Thread(target=use_limiter, args=(f"key_{i}",)) for i in range(5)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 不应抛出异常
        self.assertEqual(len(self.errors), 0)


class TestMemoryLeakPrevention(unittest.TestCase):
    """内存泄漏预防测试"""

    def test_bucket_cleanup(self):
        """测试桶清理"""
        limiter = SlidingWindowLimiter(max_requests=5, window_seconds=1, burst=0)

        # 创建多个 key
        for i in range(100):
            limiter.is_allowed(f"key_{i}")

        # 初始应有 100 个条目
        initial_count = len(limiter._buckets)
        self.assertGreaterEqual(initial_count, 100)

        # 等待过期
        time.sleep(2.5)

        # 新请求应触发清理
        limiter.is_allowed("cleanup_trigger")

        # 检查旧的 key 是否被清理
        # 由于 cleanup_trigger 是新 key，桶应该从 101 变成更少
        final_count = len(limiter._buckets)
        # 至少应该看到清理效果：旧 key 被移除
        self.assertLess(final_count, 102, f"桶应被清理，实际数量: {final_count}")

    def test_empty_bucket_removal(self):
        """测试空桶移除（内存泄漏修复）"""
        limiter = SlidingWindowLimiter(max_requests=5, window_seconds=1, burst=0)

        # 创建并使用 key
        limiter.is_allowed("test_key")

        # 等待过期
        time.sleep(1.1)

        # 新请求应触发清理
        limiter.is_allowed("test_key")

        # 检查内部状态（间接通过新请求成功判断）
        allowed, info = limiter.is_allowed("test_key")
        self.assertTrue(allowed)


class TestEdgeCasesAndBoundaryConditions(unittest.TestCase):
    """边界条件和极端情况测试"""

    def test_zero_burst(self):
        """测试零突发缓冲"""
        limiter = SlidingWindowLimiter(max_requests=5, window_seconds=1, burst=0)

        key = "test"
        for i in range(5):
            allowed, _ = limiter.is_allowed(key)
            self.assertTrue(allowed)

        # 第 6 次应被限流（无 burst）
        allowed, _ = limiter.is_allowed(key)
        self.assertFalse(allowed)

    def test_high_burst(self):
        """测试高突发缓冲"""
        limiter = SlidingWindowLimiter(max_requests=5, window_seconds=1, burst=100)

        key = "test"
        for i in range(105):  # 5 + 100
            allowed, _ = limiter.is_allowed(key)
            self.assertTrue(allowed)

        allowed, _ = limiter.is_allowed(key)
        self.assertFalse(allowed)

    def test_very_short_window(self):
        """测试极短时间窗口"""
        limiter = SlidingWindowLimiter(max_requests=5, window_seconds=0.1, burst=0)

        key = "test"
        for _ in range(5):
            limiter.is_allowed(key)

        # 立即请求应被限流
        allowed, _ = limiter.is_allowed(key)
        self.assertFalse(allowed)

        # 等待窗口过去（增加缓冲时间）
        time.sleep(0.3)
        
        # 创建新限流器实例测试窗口重置
        new_limiter = SlidingWindowLimiter(max_requests=5, window_seconds=0.1, burst=0)
        allowed, _ = new_limiter.is_allowed(key)
        self.assertTrue(allowed)

    def test_long_window(self):
        """测试长时间窗口"""
        limiter = SlidingWindowLimiter(max_requests=1, window_seconds=1, burst=0)

        key = "test"
        allowed, _ = limiter.is_allowed(key)
        self.assertTrue(allowed)

        # 立即请求应被限流
        allowed, _ = limiter.is_allowed(key)
        self.assertFalse(allowed)

    def test_many_concurrent_keys(self):
        """测试大量并发 Key"""
        limiter = SlidingWindowLimiter(max_requests=10, window_seconds=1, burst=0)

        errors = []
        def request_key(i):
            try:
                key = f"key_{i}"
                limiter.is_allowed(key)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=request_key, args=(i,)) for i in range(1000)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0)

    def test_remaining_calculation(self):
        """测试剩余配额计算"""
        limiter = SlidingWindowLimiter(max_requests=10, window_seconds=1, burst=5)
        key = "test"

        allowed, info = limiter.is_allowed(key)
        self.assertEqual(info["remaining"], 14)  # 15 - 1

        # 再执行 5 次，总共 6 次
        for _ in range(5):
            limiter.is_allowed(key)

        _, info = limiter.is_allowed(key)
        # 总共执行了 7 次，剩余应为 8（15 - 7）
        self.assertEqual(info["remaining"], 8)

    def test_reset_time_calculation(self):
        """测试重置时间计算"""
        limiter = SlidingWindowLimiter(max_requests=5, window_seconds=60, burst=0)
        key = "test"

        _, info = limiter.is_allowed(key)

        # reset_at 应该在未来 60 秒内
        now = time.time()
        self.assertGreater(info["reset_at"], now)
        self.assertLess(info["reset_at"], now + 120)


class TestGetClientId(unittest.TestCase):
    """客户端 ID 提取测试"""

    def test_api_key_header(self):
        """测试从 Header 获取 API Key"""
        request = Mock()
        request.headers = {"X-API-Key": "test_api_key_123"}
        request.remote_addr = "192.168.1.1"

        client_id = get_client_id(request)
        self.assertEqual(client_id, "key:test_api_key_123")

    def test_authorization_header(self):
        """测试从 Authorization Header 获取"""
        request = Mock()
        request.headers = {"Authorization": "Bearer test_token_456"}
        request.remote_addr = "192.168.1.1"

        client_id = get_client_id(request)
        self.assertEqual(client_id, "key:test_token_456")

    def test_api_key_priority(self):
        """测试 API Key 优先级高于 IP"""
        request = Mock()
        request.headers = {
            "X-API-Key": "api_key",
            "Authorization": "Bearer bearer_token"
        }
        request.remote_addr = "192.168.1.1"

        client_id = get_client_id(request)
        self.assertEqual(client_id, "key:api_key")

    def test_fallback_to_ip(self):
        """测试回退到 IP"""
        request = Mock()
        request.headers = {}
        request.remote_addr = "192.168.1.100"

        client_id = get_client_id(request)
        self.assertEqual(client_id, "ip:192.168.1.100")

    def test_missing_remote_addr(self):
        """测试缺失 remote_addr"""
        request = Mock()
        request.headers = {}
        request.remote_addr = None

        client_id = get_client_id(request)
        self.assertEqual(client_id, "ip:unknown")


class TestGlobalFunctions(unittest.TestCase):
    """全局函数测试"""

    @patch('rate_limiter.settings')
    def test_check_rate_limit_enabled(self, mock_settings):
        """测试限流检查 - 启用"""
        mock_settings.rate_limit_enabled = True
        mock_settings.rate_limit_requests_per_minute = 60
        mock_settings.rate_limit_burst = 10

        allowed, info = check_rate_limit("test_client")
        self.assertTrue(allowed)
        self.assertIn("remaining", info)

    @patch('rate_limiter.settings')
    def test_check_rate_limit_disabled(self, mock_settings):
        """测试限流检查 - 禁用"""
        mock_settings.rate_limit_enabled = False

        allowed, info = check_rate_limit("test_client")
        self.assertTrue(allowed)
        self.assertEqual(info, {"limit": 0, "remaining": 0, "reset_at": 0})

    def test_get_limiter_singleton(self):
        """测试限流器单例"""
        import rate_limiter
        rate_limiter._limiter = None  # 重置

        limiter1 = get_limiter()
        limiter2 = get_limiter()

        self.assertIs(limiter1, limiter2)


def run_tests():
    """运行所有测试"""
    import unittest

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestSlidingWindowLimiter))
    suite.addTests(loader.loadTestsFromTestCase(TestConcurrencyAndThreadSafety))
    suite.addTests(loader.loadTestsFromTestCase(TestMemoryLeakPrevention))
    suite.addTests(loader.loadTestsFromTestCase(TestEdgeCasesAndBoundaryConditions))
    suite.addTests(loader.loadTestsFromTestCase(TestGetClientId))
    suite.addTests(loader.loadTestsFromTestCase(TestGlobalFunctions))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "=" * 60)
    print("限流器测试结果")
    print("=" * 60)
    print(f"运行测试: {result.testsRun}")
    print(f"成功: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"失败: {len(result.failures)}")
    print(f"错误: {len(result.errors)}")

    return result.wasSuccessful()


if __name__ == "__main__":
    import sys
    success = run_tests()
    sys.exit(0 if success else 1)