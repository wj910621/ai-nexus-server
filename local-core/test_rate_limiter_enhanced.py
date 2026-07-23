"""
限流器增强测试 - 测试滑动窗口算法、并发安全、边界条件、极端情况
"""

import threading
import time
import unittest
from unittest.mock import patch, MagicMock

from rate_limiter import SlidingWindowLimiter, get_limiter, check_rate_limit, get_client_id


class TestSlidingWindowLimiter(unittest.TestCase):
    """测试滑动窗口限流器核心功能"""

    def test_basic_rate_limiting(self):
        """基本限流功能"""
        limiter = SlidingWindowLimiter(max_requests=5, window_seconds=60, burst=0)

        # 前 5 次请求应通过
        for i in range(5):
            allowed, info = limiter.is_allowed("client_1")
            self.assertTrue(allowed, f"第 {i+1} 次请求应通过")

        # 第 6 次请求应被拒绝
        allowed, info = limiter.is_allowed("client_1")
        self.assertFalse(allowed, "第 6 次请求应被拒绝")

    def test_burst_allowance(self):
        """突发流量允许"""
        limiter = SlidingWindowLimiter(max_requests=5, window_seconds=60, burst=2)

        # 5 + 2 = 7 次请求应通过
        for i in range(7):
            allowed, info = limiter.is_allowed("client_1")
            self.assertTrue(allowed, f"第 {i+1} 次请求（含突发）应通过")

        # 第 8 次请求应被拒绝
        allowed, info = limiter.is_allowed("client_1")
        self.assertFalse(allowed, "超过突发上限的请求应被拒绝")

    def test_remaining_quota_calculation(self):
        """剩余配额计算"""
        limiter = SlidingWindowLimiter(max_requests=10, window_seconds=60, burst=2)

        # 初始配额应为 12
        allowed, info = limiter.is_allowed("client_1")
        self.assertEqual(info["limit"], 12)
        self.assertEqual(info["remaining"], 11)

        # 使用 5 次后
        for _ in range(4):
            limiter.is_allowed("client_1")

        allowed, info = limiter.is_allowed("client_1")
        self.assertEqual(info["remaining"], 6)

    def test_reset_time_calculation(self):
        """重置时间计算"""
        limiter = SlidingWindowLimiter(max_requests=5, window_seconds=60, burst=0)

        allowed, info = limiter.is_allowed("client_1")

        # 重置时间应大于当前时间
        self.assertGreater(info["reset_at"], time.time())
        # 重置时间应在未来 60 秒内
        self.assertLess(info["reset_at"] - time.time(), 120)

    def test_different_clients_independent(self):
        """不同客户端独立计数"""
        limiter = SlidingWindowLimiter(max_requests=2, window_seconds=60, burst=0)

        # client_1 使用 2 次
        limiter.is_allowed("client_1")
        limiter.is_allowed("client_1")

        # client_1 应被限流
        allowed, _ = limiter.is_allowed("client_1")
        self.assertFalse(allowed)

        # client_2 应不受影响
        allowed, _ = limiter.is_allowed("client_2")
        self.assertTrue(allowed)

    def test_empty_key_allowed(self):
        """空密钥应始终允许"""
        limiter = SlidingWindowLimiter(max_requests=1, window_seconds=60, burst=0)

        # 空密钥应允许
        allowed, info = limiter.is_allowed("")
        self.assertTrue(allowed)
        self.assertEqual(info, {})

        allowed, info = limiter.is_allowed(None)
        self.assertTrue(allowed)

    def test_get_info_does_not_increase_count(self):
        """get_info 不增加计数"""
        limiter = SlidingWindowLimiter(max_requests=2, window_seconds=60, burst=0)

        # 使用 1 次
        limiter.is_allowed("client_1")

        # 查询信息不应增加计数
        info = limiter.get_info("client_1")
        self.assertEqual(info["remaining"], 1)

        # 再次查询
        info = limiter.get_info("client_1")
        self.assertEqual(info["remaining"], 1)

        # 实际请求应只剩 1 次
        allowed, _ = limiter.is_allowed("client_1")
        self.assertTrue(allowed)

        allowed, _ = limiter.is_allowed("client_1")
        self.assertFalse(allowed)

    def test_window_sliding_behavior(self):
        """滑动窗口行为（模拟时间流逝）"""
        limiter = SlidingWindowLimiter(max_requests=3, window_seconds=1, burst=0)

        # 快速使用 3 次配额
        for _ in range(3):
            limiter.is_allowed("client_1")

        # 应被限流
        allowed, _ = limiter.is_allowed("client_1")
        self.assertFalse(allowed)

        # 等待窗口过期（2 个窗口周期）
        time.sleep(2.1)

        # 新请求应通过
        allowed, _ = limiter.is_allowed("client_1")
        self.assertTrue(allowed)

    def test_bucket_cleanup(self):
        """桶清理机制"""
        limiter = SlidingWindowLimiter(max_requests=5, window_seconds=1, burst=0)

        # 创建一些请求
        for _ in range(3):
            limiter.is_allowed("client_1")

        # 等待桶过期
        time.sleep(2.5)

        # 新请求应能正常工作，且不应有内存泄漏
        allowed, info = limiter.is_allowed("client_1")
        self.assertTrue(allowed)

    def test_memory_cleanup_on_key_removal(self):
        """内存清理：key 在所有桶过期后被删除"""
        limiter = SlidingWindowLimiter(max_requests=2, window_seconds=1, burst=0)

        # 使用临时 key
        limiter.is_allowed("temp_client")

        # 等待桶过期
        time.sleep(2.5)

        # 使用新请求触发清理
        limiter.is_allowed("temp_client")

        # 验证清理逻辑执行（不应报错）


class TestConcurrentRateLimiting(unittest.TestCase):
    """测试并发场景下的限流器"""

    def test_concurrent_requests_thread_safety(self):
        """并发请求线程安全"""
        limiter = SlidingWindowLimiter(max_requests=100, window_seconds=60, burst=10)
        results = []
        errors = []

        def make_requests(client_id, count):
            try:
                for _ in range(count):
                    allowed, info = limiter.is_allowed(client_id)
                    results.append((client_id, allowed))
            except Exception as e:
                errors.append(e)

        # 创建多个线程并发请求
        threads = []
        for i in range(5):
            t = threading.Thread(target=make_requests, args=(f"client_{i}", 25))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # 不应有线程安全错误
        self.assertEqual(len(errors), 0, f"并发错误: {errors}")

        # 总通过请求不应超过限制
        allowed_count = sum(1 for _, allowed in results if allowed)
        self.assertLessEqual(allowed_count, 110 * 5)  # 每个客户端 110 次

    def test_concurrent_same_client(self):
        """同一客户端并发请求"""
        limiter = SlidingWindowLimiter(max_requests=10, window_seconds=60, burst=0)
        allowed_count = [0]
        lock = threading.Lock()

        def make_request():
            allowed, _ = limiter.is_allowed("shared_client")
            if allowed:
                with lock:
                    allowed_count[0] += 1

        # 创建并发线程
        threads = [threading.Thread(target=make_request) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 应正好有 10 次通过
        self.assertEqual(allowed_count[0], 10)

    def test_stress_test_high_concurrency(self):
        """压力测试：高并发场景"""
        limiter = SlidingWindowLimiter(max_requests=1000, window_seconds=60, burst=100)
        success_count = [0]
        fail_count = [0]
        lock = threading.Lock()

        def stress_requests():
            for _ in range(100):
                allowed, _ = limiter.is_allowed("stress_client")
                with lock:
                    if allowed:
                        success_count[0] += 1
                    else:
                        fail_count[0] += 1

        threads = [threading.Thread(target=stress_requests) for _ in range(20)]

        start_time = time.time()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        duration = time.time() - start_time

        # 验证总数正确
        total = success_count[0] + fail_count[0]
        self.assertEqual(total, 2000)

        # 验证通过数不超过限制
        self.assertLessEqual(success_count[0], 1100)

        print(f"\n压力测试完成: {total} 请求在 {duration:.2f} 秒内处理")


class TestEdgeCases(unittest.TestCase):
    """测试边界条件和极端情况"""

    def test_zero_max_requests(self):
        """零配额限流"""
        limiter = SlidingWindowLimiter(max_requests=0, window_seconds=60, burst=0)

        # 所有请求应被拒绝
        allowed, _ = limiter.is_allowed("client_1")
        self.assertFalse(allowed)

    def test_very_large_max_requests(self):
        """极大配额"""
        limiter = SlidingWindowLimiter(max_requests=1000000, window_seconds=60, burst=100000)

        # 应能处理大量请求
        for _ in range(1000):
            allowed, _ = limiter.is_allowed("client_1")
            self.assertTrue(allowed)

    def test_very_short_window(self):
        """极短时间窗口"""
        limiter = SlidingWindowLimiter(max_requests=5, window_seconds=0.1, burst=0)

        # 快速使用配额
        for _ in range(5):
            limiter.is_allowed("client_1")

        # 等待窗口过期
        time.sleep(0.2)

        # 应能再次请求
        allowed, _ = limiter.is_allowed("client_1")
        self.assertTrue(allowed)

    def test_very_long_key(self):
        """超长密钥"""
        limiter = SlidingWindowLimiter(max_requests=5, window_seconds=60, burst=0)
        long_key = "a" * 10000

        allowed, _ = limiter.is_allowed(long_key)
        self.assertTrue(allowed)

    def test_special_characters_in_key(self):
        """密钥中的特殊字符"""
        limiter = SlidingWindowLimiter(max_requests=5, window_seconds=60, burst=0)

        special_keys = [
            "client\x00null",
            "client\nnewline",
            "client\ttab",
            "client space",
            "client/ slash",
            "client\\ backslash",
        ]

        for key in special_keys:
            allowed, _ = limiter.is_allowed(key)
            self.assertTrue(allowed, f"特殊字符密钥 {repr(key)} 应被处理")

    def test_unicode_key(self):
        """Unicode 密钥"""
        limiter = SlidingWindowLimiter(max_requests=5, window_seconds=60, burst=0)

        unicode_keys = [
            "客户端_测试",
            "клиент_тест",
            "🚀_rocket",
            "客户🔥测试",
        ]

        for key in unicode_keys:
            allowed, _ = limiter.is_allowed(key)
            self.assertTrue(allowed)

    def test_negative_remaining(self):
        """剩余配额不应为负数"""
        limiter = SlidingWindowLimiter(max_requests=2, window_seconds=60, burst=0)

        # 使用所有配额
        for _ in range(3):
            limiter.is_allowed("client_1")

        info = limiter.get_info("client_1")
        self.assertGreaterEqual(info["remaining"], 0)


class TestGlobalFunctions(unittest.TestCase):
    """测试全局限流函数"""

    @patch('rate_limiter.settings')
    def test_check_rate_limit_enabled(self, mock_settings):
        """限流启用时的检查"""
        mock_settings.rate_limit_enabled = True
        mock_settings.rate_limit_requests_per_minute = 60
        mock_settings.rate_limit_burst = 10

        client_id = "test_client"
        allowed, info = check_rate_limit(client_id)
        self.assertIsInstance(allowed, bool)
        self.assertIn("limit", info)
        self.assertIn("remaining", info)

    @patch('rate_limiter.settings')
    def test_check_rate_limit_disabled(self, mock_settings):
        """限流禁用时的检查"""
        mock_settings.rate_limit_enabled = False

        allowed, info = check_rate_limit("test_client")
        self.assertTrue(allowed)
        self.assertEqual(info, {"limit": 0, "remaining": 0, "reset_at": 0})

    def test_get_client_id_with_api_key(self):
        """从请求提取 API Key"""
        mock_request = MagicMock()
        mock_request.headers.get.side_effect = lambda k, v=None: {
            "X-API-Key": "test_api_key_12345",
            "Authorization": "",
        }.get(k, v)
        mock_request.remote_addr = "192.168.1.100"

        client_id = get_client_id(mock_request)
        self.assertEqual(client_id, "key:test_api_key_12345")

    def test_get_client_id_with_bearer_token(self):
        """从 Bearer token 提取 API Key"""
        mock_request = MagicMock()
        mock_request.headers.get.side_effect = lambda k, v=None: {
            "X-API-Key": "",
            "Authorization": "Bearer bearer_token_12345",
        }.get(k, v)
        mock_request.remote_addr = "192.168.1.100"

        client_id = get_client_id(mock_request)
        self.assertEqual(client_id, "key:bearer_token_12345")

    def test_get_client_id_fallback_to_ip(self):
        """无 API Key 时使用 IP"""
        mock_request = MagicMock()
        mock_request.headers.get.return_value = ""
        mock_request.remote_addr = "192.168.1.100"

        client_id = get_client_id(mock_request)
        self.assertEqual(client_id, "ip:192.168.1.100")

    def test_get_client_id_unknown_ip(self):
        """IP 地址未知"""
        mock_request = MagicMock()
        mock_request.headers.get.return_value = ""
        mock_request.remote_addr = None

        client_id = get_client_id(mock_request)
        self.assertEqual(client_id, "ip:unknown")


class TestRateLimiterIntegration(unittest.TestCase):
    """限流器集成测试"""

    def test_real_world_scenario(self):
        """真实场景模拟"""
        limiter = SlidingWindowLimiter(max_requests=100, window_seconds=60, burst=20)

        # 模拟 1 分钟内的请求分布
        allowed_total = 0
        denied_total = 0

        # 模拟正常流量
        for i in range(80):
            allowed, _ = limiter.is_allowed("normal_user")
            if allowed:
                allowed_total += 1
            else:
                denied_total += 1

        # 模拟突发流量
        for i in range(50):
            allowed, _ = limiter.is_allowed("normal_user")
            if allowed:
                allowed_total += 1
            else:
                denied_total += 1

        # 应正好有 120 次通过（100 + 20 突发）
        self.assertEqual(allowed_total, 120)
        self.assertEqual(denied_total, 10)

    def test_distributed_client_simulation(self):
        """分布式客户端模拟"""
        limiter = SlidingWindowLimiter(max_requests=50, window_seconds=60, burst=5)

        # 多个客户端同时请求
        clients = [f"client_{i}" for i in range(10)]
        results = {}

        for client in clients:
            allowed_count = 0
            for _ in range(60):  # 每个客户端请求 60 次
                allowed, _ = limiter.is_allowed(client)
                if allowed:
                    allowed_count += 1
            results[client] = allowed_count

        # 每个客户端应正好有 55 次通过
        for client, count in results.items():
            self.assertEqual(count, 55, f"{client} 通过次数不正确")


def run_rate_limiter_tests():
    """运行限流器增强测试"""
    suite = unittest.TestLoader().loadTestsFromModule(__import__(__name__))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == "__main__":
    import sys
    success = run_rate_limiter_tests()
    sys.exit(0 if success else 1)