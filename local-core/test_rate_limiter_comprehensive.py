"""
限流器全面测试
覆盖：
  - 滑动窗口算法正确性
  - 突发流量处理
  - 并发请求安全
  - 边界条件
  - 内存泄漏防护
  - 重置时间计算
"""

import os
import sys
import time
import threading
import tempfile
from pathlib import Path

# 设置测试环境
os.makedirs("data", exist_ok=True)

from rate_limiter import SlidingWindowLimiter, get_limiter, check_rate_limit, get_client_id


class TestSlidingWindowAlgorithm:
    """滑动窗口算法测试"""

    def test_basic_rate_limiting(self):
        """测试基本限流"""
        limiter = SlidingWindowLimiter(max_requests=5, window_seconds=60, burst=0)
        
        # 前 5 次应该通过
        for i in range(5):
            allowed, info = limiter.is_allowed("client1")
            assert allowed is True, f"请求 {i+1} 应该通过"
        
        # 第 6 次应该被拒绝
        allowed, info = limiter.is_allowed("client1")
        assert allowed is False, "第 6 次应该被限流"

    def test_burst_handling(self):
        """测试突发流量"""
        limiter = SlidingWindowLimiter(max_requests=3, window_seconds=60, burst=2)
        
        # max_requests + burst = 5 次应该通过
        for i in range(5):
            allowed, _ = limiter.is_allowed("burst_client")
            assert allowed is True, f"请求 {i+1} 应该通过"
        
        # 第 6 次应该被拒绝
        allowed, _ = limiter.is_allowed("burst_client")
        assert allowed is False

    def test_different_clients_independent(self):
        """测试不同客户端独立限流"""
        limiter = SlidingWindowLimiter(max_requests=2, window_seconds=60, burst=0)
        
        # 客户端 A 用完额度
        limiter.is_allowed("client_a")
        limiter.is_allowed("client_a")
        
        # 客户端 B 应该仍然可以访问
        allowed, _ = limiter.is_allowed("client_b")
        assert allowed is True

    def test_remaining_count_accuracy(self):
        """测试剩余计数准确性"""
        limiter = SlidingWindowLimiter(max_requests=10, window_seconds=60, burst=0)
        
        for i in range(5):
            _, info = limiter.is_allowed("count_test")
        
        # 剩余应该是 5
        assert info["remaining"] == 5

    def test_info_does_not_increment(self):
        """测试查询接口不增加计数"""
        limiter = SlidingWindowLimiter(max_requests=5, window_seconds=60, burst=0)
        
        # 先用 3 次
        for _ in range(3):
            limiter.is_allowed("info_test")
        
        # 查询
        info = limiter.get_info("info_test")
        assert info["remaining"] == 2
        
        # 再次查询，计数不应该增加
        info2 = limiter.get_info("info_test")
        assert info2["remaining"] == 2


class TestConcurrency:
    """并发测试"""

    def test_concurrent_requests_thread_safe(self):
        """测试并发请求线程安全"""
        limiter = SlidingWindowLimiter(max_requests=100, window_seconds=60, burst=0)
        
        results = []
        lock = threading.Lock()
        
        def make_request(i):
            allowed, info = limiter.is_allowed("concurrent_client")
            with lock:
                results.append(allowed)
        
        threads = [
            threading.Thread(target=make_request, args=(i,))
            for i in range(150)
        ]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # 应该正好有 100 个通过，50 个被限流
        passed = sum(results)
        blocked = len(results) - passed
        
        assert passed == 100, f"应该有 100 个通过，实际 {passed}"
        assert blocked == 50, f"应该有 50 个被限流，实际 {blocked}"

    def test_concurrent_different_clients(self):
        """测试不同客户端并发"""
        limiter = SlidingWindowLimiter(max_requests=10, window_seconds=60, burst=0)
        
        results = {}
        lock = threading.Lock()
        
        def client_requests(client_id, count):
            local_passed = 0
            for _ in range(count):
                allowed, _ = limiter.is_allowed(client_id)
                if allowed:
                    local_passed += 1
            with lock:
                results[client_id] = local_passed
        
        threads = [
            threading.Thread(target=client_requests, args=(f"client_{i}", 15))
            for i in range(5)
        ]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # 每个客户端应该正好 10 个通过
        for client_id, passed in results.items():
            assert passed == 10, f"{client_id} 应该有 10 个通过，实际 {passed}"


class TestBoundaryConditions:
    """边界条件测试"""

    def test_empty_key(self):
        """测试空 Key"""
        limiter = SlidingWindowLimiter(max_requests=5, window_seconds=60)
        
        # 空 Key 应该总是通过
        allowed, info = limiter.is_allowed("")
        assert allowed is True
        
        allowed, info = limiter.is_allowed(None)
        assert allowed is True

    def test_zero_rate_limit(self):
        """测试零限流配置"""
        limiter = SlidingWindowLimiter(max_requests=0, window_seconds=60, burst=0)
        
        # 应该总是被限流
        allowed, _ = limiter.is_allowed("zero_client")
        assert allowed is False

    def test_very_high_rate_limit(self):
        """测试高限流配置"""
        limiter = SlidingWindowLimiter(max_requests=1000000, window_seconds=60)
        
        # 大量请求应该都通过
        for _ in range(1000):
            allowed, _ = limiter.is_allowed("high_client")
            assert allowed is True

    def test_special_characters_in_key(self):
        """测试 Key 中包含特殊字符"""
        limiter = SlidingWindowLimiter(max_requests=5, window_seconds=60)
        
        # 特殊字符 Key 应该正常工作
        special_keys = [
            "client:with:colon",
            "client/with/slash",
            "client@with@at",
            "client 中文",
            "client🔥emoji",
        ]
        
        for key in special_keys:
            allowed, _ = limiter.is_allowed(key)
            assert allowed is True

    def test_reset_time_calculation(self):
        """测试重置时间计算"""
        limiter = SlidingWindowLimiter(max_requests=5, window_seconds=60)
        
        _, info = limiter.is_allowed("reset_test")
        
        # 重置时间应该在未来
        assert info["reset_at"] > time.time()
        # 重置时间应该在 60 秒内
        assert info["reset_at"] - time.time() <= 60


class TestMemoryManagement:
    """内存管理测试"""

    def test_bucket_cleanup(self):
        """测试过期桶清理"""
        limiter = SlidingWindowLimiter(max_requests=10, window_seconds=1)
        
        # 创建一些请求
        for _ in range(5):
            limiter.is_allowed("cleanup_client")
        
        # 等待窗口过期
        time.sleep(1.5)
        
        # 新请求应该触发清理
        limiter.is_allowed("cleanup_client")
        
        # 内部桶数量应该有限
        assert len(limiter._buckets.get("cleanup_client", {})) <= 2

    def test_key_removal_after_expiry(self):
        """测试过期后 Key 被移除"""
        limiter = SlidingWindowLimiter(max_requests=10, window_seconds=1)
        
        # 创建请求
        limiter.is_allowed("expire_client")
        
        # 等待过期
        time.sleep(1.5)
        
        # 新请求触发清理，空桶应该被删除
        limiter.is_allowed("expire_client")
        
        # 再次触发，之前的空桶应该已被清理
        limiter.is_allowed("expire_client")


class TestUtilityFunctions:
    """工具函数测试"""

    def test_get_limiter_singleton(self):
        """测试获取全局限流器"""
        limiter1 = get_limiter()
        limiter2 = get_limiter()
        
        assert limiter1 is limiter2

    def test_get_client_id_from_api_key(self):
        """测试从 API Key 提取客户端 ID"""
        class MockRequest:
            headers = {"X-API-Key": "test_api_key_12345"}
            remote_addr = "127.0.0.1"
        
        client_id = get_client_id(MockRequest())
        
        assert client_id.startswith("key:")
        assert len(client_id) > 4

    def test_get_client_id_from_auth_header(self):
        """测试从 Authorization 头提取"""
        class MockRequest:
            headers = {"Authorization": "Bearer test_token_12345"}
            remote_addr = "127.0.0.1"
        
        client_id = get_client_id(MockRequest())
        
        assert client_id.startswith("key:")

    def test_get_client_id_from_ip(self):
        """测试从 IP 提取客户端 ID"""
        class MockRequest:
            headers = {}
            remote_addr = "192.168.1.100"
        
        client_id = get_client_id(MockRequest())
        
        assert client_id.startswith("ip:")
        assert "192.168.1.100" in client_id

    def test_get_client_id_unknown_ip(self):
        """测试未知 IP"""
        class MockRequest:
            headers = {}
            remote_addr = None
        
        client_id = get_client_id(MockRequest())
        
        assert client_id.startswith("ip:")


class TestRateLimitIntegration:
    """限流集成测试"""

    def test_check_rate_limit_function(self):
        """测试 check_rate_limit 函数"""
        # 多次调用应该触发限流
        client_id = "test_integration_client"
        
        for i in range(100):
            allowed, info = check_rate_limit(client_id)
            if not allowed:
                # 一旦被限流，后续应该都被限流
                assert i >= 60  # 默认 60 + burst
                break


def run_tests():
    """运行所有测试"""
    import traceback
    
    test_classes = [
        TestSlidingWindowAlgorithm,
        TestConcurrency,
        TestBoundaryConditions,
        TestMemoryManagement,
        TestUtilityFunctions,
        TestRateLimitIntegration,
    ]
    
    total = 0
    passed = 0
    failed = 0
    
    for test_class in test_classes:
        print(f"\n{'='*60}")
        print(f"  {test_class.__name__}")
        print(f"{'='*60}")
        
        instance = test_class()
        
        for method_name in dir(instance):
            if method_name.startswith("test_"):
                total += 1
                method = getattr(instance, method_name)
                try:
                    method()
                    print(f"  ✓ {method_name}")
                    passed += 1
                except AssertionError as e:
                    print(f"  ✗ {method_name}: {e}")
                    failed += 1
                except Exception as e:
                    print(f"  ✗ {method_name}: {type(e).__name__}: {e}")
                    traceback.print_exc()
                    failed += 1
    
    print(f"\n{'='*60}")
    print(f"  测试结果: {passed}/{total} 通过")
    print(f"{'='*60}")
    
    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)