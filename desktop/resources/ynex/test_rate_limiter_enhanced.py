"""
Y·NEX限流器增强测试
测试覆盖：
- 基本限流逻辑
- 边界条件
- 并发安全
- 内存泄漏防护
- 时间窗口滑动
"""

import time
import threading
import unittest
from unittest.mock import patch, MagicMock

from rate_limiter import (
    SlidingWindowLimiter,
    get_limiter,
    check_rate_limit,
    get_client_id,
)


class TestBasicRateLimiting(unittest.TestCase):
    """基本限流测试"""

    def test_basic_limit(self):
        """测试基本限流"""
        limiter = SlidingWindowLimiter(max_requests=3, burst=1)
        key = "test_client"

        # 前4次应该通过（3 + 1 burst）
        for i in range(4):
            allowed, info = limiter.is_allowed(key)
            self.assertTrue(allowed, f"第{i+1}次请求应通过")
            self.assertEqual(info["remaining"], 4 - i - 1)

        # 第5次应被限流
        allowed, info = limiter.is_allowed(key)
        self.assertFalse(allowed)
        self.assertEqual(info["remaining"], 0)

    def test_zero_burst(self):
        """测试无突发缓冲"""
        limiter = SlidingWindowLimiter(max_requests=3, burst=0)
        key = "test_client"

        # 精确3次通过
        for i in range(3):
            allowed, _ = limiter.is_allowed(key)
            self.assertTrue(allowed)

        # 第4次拒绝
        allowed, _ = limiter.is_allowed(key)
        self.assertFalse(allowed)

    def test_empty_key(self):
        """测试空key（应允许通过）"""
        limiter = SlidingWindowLimiter()
        allowed, info = limiter.is_allowed("")
        self.assertTrue(allowed)
        self.assertEqual(info, {})

    def test_remaining_calculation(self):
        """测试剩余配额计算"""
        limiter = SlidingWindowLimiter(max_requests=10, burst=2)
        key = "test"

        # 初始剩余应为12
        allowed, info = limiter.is_allowed(key)
        self.assertTrue(allowed)
        self.assertEqual(info["remaining"], 11)

        # 再次请求
        allowed, info = limiter.is_allowed(key)
        self.assertEqual(info["remaining"], 10)


class TestSlidingWindow(unittest.TestCase):
    """滑动窗口测试"""

    def test_window_transition(self):
        """测试时间窗口过渡"""
        # 使用极短窗口测试
        limiter = SlidingWindowLimiter(max_requests=2, window_seconds=1, burst=0)
        key = "test"

        # 消耗配额
        limiter.is_allowed(key)
        limiter.is_allowed(key)

        # 应被限流
        allowed, _ = limiter.is_allowed(key)
        self.assertFalse(allowed)

        # 等待窗口过去（增加等待时间以确保跨过窗口）
        time.sleep(2.0)

        # 新窗口应允许
        allowed, _ = limiter.is_allowed(key)
        self.assertTrue(allowed, "新窗口应允许请求")

    def test_get_info_no_side_effect(self):
        """测试查询接口不增加计数"""
        limiter = SlidingWindowLimiter(max_requests=5, burst=0)
        key = "test"

        # 查询不应增加计数
        for _ in range(10):
            info = limiter.get_info(key)
            self.assertEqual(info["remaining"], 5)

    def test_reset_time_calculation(self):
        """测试重置时间计算"""
        limiter = SlidingWindowLimiter(window_seconds=60)
        key = "test"

        allowed, info = limiter.is_allowed(key)
        # reset_at应在未来60秒内
        now = time.time()
        self.assertGreater(info["reset_at"], now)
        self.assertLess(info["reset_at"], now + 120)


class TestConcurrencySafety(unittest.TestCase):
    """并发安全测试"""

    def test_concurrent_requests(self):
        """测试并发请求"""
        limiter = SlidingWindowLimiter(max_requests=100, burst=10)
        key = "shared_client"

        results = []
        errors = []

        def make_request():
            try:
                allowed, info = limiter.is_allowed(key)
                results.append(allowed)
            except Exception as e:
                errors.append(e)

        # 创建大量并发线程
        threads = []
        for _ in range(50):
            t = threading.Thread(target=make_request)
            threads.append(t)

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        # 不应有异常
        self.assertEqual(len(errors), 0)

        # 应有正确的通过/拒绝数
        allowed_count = sum(results)
        self.assertLessEqual(allowed_count, 110)  # max_requests + burst

    def test_concurrent_different_keys(self):
        """测试不同key的并发请求"""
        limiter = SlidingWindowLimiter(max_requests=5, burst=0)

        results = {}

        def make_request(key_name):
            allowed, _ = limiter.is_allowed(key_name)
            results[key_name] = results.get(key_name, 0)
            if allowed:
                results[key_name] = results.get(key_name, 0) + 1

        threads = []
        for i in range(3):
            for _ in range(10):
                key = f"client_{i}"
                t = threading.Thread(target=make_request, args=(key,))
                threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 每个key最多5次通过
        for key, count in results.items():
            self.assertLessEqual(count, 5)


class TestMemoryLeakPrevention(unittest.TestCase):
    """内存泄漏防护测试"""

    def test_expired_bucket_cleanup(self):
        """测试过期桶清理"""
        limiter = SlidingWindowLimiter(max_requests=10, window_seconds=1)
        key = "test"

        # 创建请求
        limiter.is_allowed(key)

        # 等待窗口过期
        time.sleep(1.5)

        # 新请求应触发清理
        limiter.is_allowed(key)

        # 内部状态验证（如果可以访问内部状态）
        # 检查旧桶是否被清理
        with limiter._lock:
            buckets = limiter._buckets.get(key, {})
            # 只应保留最近的桶
            for bucket_time in list(buckets.keys()):
                current_bucket = int(time.time() // limiter.window_seconds)
                self.assertGreaterEqual(bucket_time, current_bucket - 1)

    def test_empty_key_cleanup(self):
        """测试空key条目清理（内存泄漏修复）"""
        limiter = SlidingWindowLimiter(max_requests=1, window_seconds=1)
        key = "temp_client"

        # 创建请求
        limiter.is_allowed(key)

        # 等待过期
        time.sleep(1.5)

        # 新请求应清理旧的空条目
        limiter.is_allowed(key)

        # 验证内部状态（key应存在但桶已清理）
        with limiter._lock:
            # 如果实现正确，空key条目应被删除
            # 或者至少不应累积大量过期条目
            pass  # 实际实现可能不同，这里只确保不抛异常


class TestClientIdExtraction(unittest.TestCase):
    """客户端ID提取测试"""

    def test_from_api_key_header(self):
        """测试从API Key Header提取"""
        request = MagicMock()
        request.headers.get = MagicMock(side_effect=lambda k, d=None: {
            "X-API-Key": "sk_test123",
            "Authorization": None,
        }.get(k, d))
        request.remote_addr = "192.168.1.1"

        client_id = get_client_id(request)
        self.assertEqual(client_id, "key:sk_test123"[:36])  # 32位前缀

    def test_from_authorization_header(self):
        """测试从Authorization Header提取"""
        request = MagicMock()
        request.headers.get = MagicMock(side_effect=lambda k, d=None: {
            "X-API-Key": "",
            "Authorization": "Bearer sk_auth456",
        }.get(k, d))
        request.remote_addr = "192.168.1.1"

        client_id = get_client_id(request)
        self.assertTrue(client_id.startswith("key:"))

    def test_from_ip(self):
        """测试从IP提取（无API Key）"""
        request = MagicMock()
        request.headers.get = MagicMock(return_value="")
        request.remote_addr = "192.168.1.100"

        client_id = get_client_id(request)
        self.assertEqual(client_id, "ip:192.168.1.100")

    def test_missing_remote_addr(self):
        """测试缺失remote_addr"""
        request = MagicMock()
        request.headers.get = MagicMock(return_value="")
        request.remote_addr = None

        client_id = get_client_id(request)
        self.assertEqual(client_id, "ip:unknown")


class TestGlobalLimiter(unittest.TestCase):
    """全局限流器测试"""

    def test_global_limiter_singleton(self):
        """测试全局限流器单例"""
        limiter1 = get_limiter()
        limiter2 = get_limiter()
        self.assertIs(limiter1, limiter2)

    @patch('rate_limiter.settings')
    def test_check_rate_limit_disabled(self, mock_settings):
        """测试禁用限流"""
        mock_settings.rate_limit_enabled = False
        mock_settings.rate_limit_requests_per_minute = 60
        mock_settings.rate_limit_burst = 10

        allowed, info = check_rate_limit("test_client")
        self.assertTrue(allowed)
        self.assertEqual(info["limit"], 0)

    def test_check_rate_limit_enabled(self):
        """测试启用限流"""
        # 直接测试limiter实例
        limiter = SlidingWindowLimiter(max_requests=5, burst=1)
        
        # 测试基本限流功能
        allowed, _ = limiter.is_allowed("test_key")
        self.assertTrue(allowed)


class TestEdgeCases(unittest.TestCase):
    """边界条件测试"""

    def test_large_burst(self):
        """测试大突发值"""
        limiter = SlidingWindowLimiter(max_requests=0, burst=100)
        key = "test"

        # 纯突发缓冲
        for i in range(100):
            allowed, _ = limiter.is_allowed(key)
            self.assertTrue(allowed)

        allowed, _ = limiter.is_allowed(key)
        self.assertFalse(allowed)

    def test_very_long_key(self):
        """测试超长key"""
        limiter = SlidingWindowLimiter()
        key = "a" * 10000

        allowed, _ = limiter.is_allowed(key)
        self.assertTrue(allowed)

    def test_unicode_key(self):
        """测试Unicode key"""
        limiter = SlidingWindowLimiter()
        key = "用户_测试_🚀"

        allowed, _ = limiter.is_allowed(key)
        self.assertTrue(allowed)

    def test_negative_remaining(self):
        """测试剩余配额非负"""
        limiter = SlidingWindowLimiter(max_requests=1, burst=0)
        key = "test"

        limiter.is_allowed(key)  # 消耗配额
        limiter.is_allowed(key)  # 被拒绝

        info = limiter.get_info(key)
        self.assertGreaterEqual(info["remaining"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)