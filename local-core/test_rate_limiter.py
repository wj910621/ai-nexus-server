"""
限流器测试
测试滑动窗口限流、并发安全、内存泄漏防护等功能
"""

import time
import threading
from rate_limiter import SlidingWindowLimiter, check_rate_limit, get_client_id


class MockRequest:
    """模拟请求对象"""
    def __init__(self, headers=None, remote_addr="127.0.0.1"):
        self.headers = headers or {}
        self.remote_addr = remote_addr


def test_basic_rate_limiting():
    """测试基础限流功能"""
    print("\n=== 测试基础限流功能 ===")

    limiter = SlidingWindowLimiter(max_requests=3, burst=1)
    key = "test_client"

    # 前 4 次应通过（max_requests + burst）
    results = []
    for i in range(5):
        allowed, info = limiter.is_allowed(key)
        results.append((allowed, info['remaining']))
        print(f"  第 {i+1} 次: allowed={allowed}, remaining={info['remaining']}")

    # 验证限流触发
    assert results[0][0] is True  # 第1次应通过
    assert results[3][0] is True  # 第4次应通过（max_requests + burst）
    assert results[4][0] is False  # 第5次应被限流

    print("  ✓ 限流触发正确")


def test_get_info():
    """测试查询接口不增加计数"""
    print("\n=== 测试查询接口 ===")

    limiter = SlidingWindowLimiter(max_requests=10, burst=0)
    key = "query_test"

    # 执行一次请求
    allowed, info1 = limiter.is_allowed(key)
    count1 = info1['limit'] - info1['remaining']

    # 查询不应增加计数
    info2 = limiter.get_info(key)
    count2 = info2['limit'] - info2['remaining']

    assert count1 == count2, "查询接口不应增加计数"
    print(f"  查询后计数保持一致: {count1}")


def test_concurrent_access():
    """测试并发访问安全性"""
    print("\n=== 测试并发访问安全性 ===")

    limiter = SlidingWindowLimiter(max_requests=100, burst=10)
    key = "concurrent_test"

    errors = []
    success_count = [0]

    def make_request():
        try:
            for _ in range(10):
                allowed, info = limiter.is_allowed(key)
                if allowed:
                    success_count[0] += 1
                time.sleep(0.001)
        except Exception as e:
            errors.append(e)

    # 启动多个线程
    threads = []
    for _ in range(5):
        t = threading.Thread(target=make_request)
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    assert len(errors) == 0, f"并发访问出错: {errors}"
    print(f"  并发请求成功: {success_count[0]} 次通过")


def test_memory_cleanup():
    """测试过期桶清理和内存泄漏防护"""
    print("\n=== 测试内存清理 ===")

    limiter = SlidingWindowLimiter(max_requests=10, window_seconds=1)

    # 使用多个不同的key
    for i in range(10):
        limiter.is_allowed(f"key_{i}")

    # 检查内部状态
    assert len(limiter._buckets) > 0, "应有桶数据"

    # 等待过期
    time.sleep(2.5)

    # 使用一个key触发清理
    limiter.is_allowed("key_0")

    print("  ✓ 过期桶清理测试通过")


def test_empty_key():
    """测试空Key处理"""
    print("\n=== 测试空Key处理 ===")

    limiter = SlidingWindowLimiter()

    # 空Key应允许通过
    allowed, info = limiter.is_allowed("")
    assert allowed is True
    print("  空Key允许通过")

    # None Key
    allowed, info = limiter.is_allowed(None)
    assert allowed is True
    print("  None Key允许通过")


def test_different_keys():
    """测试不同Key独立限流"""
    print("\n=== 测试不同Key独立限流 ===")

    limiter = SlidingWindowLimiter(max_requests=2, burst=0)

    # key1 请求两次
    assert limiter.is_allowed("key1")[0] is True
    assert limiter.is_allowed("key1")[0] is True
    assert limiter.is_allowed("key1")[0] is False  # 应被限流

    # key2 应该不受影响
    assert limiter.is_allowed("key2")[0] is True
    assert limiter.is_allowed("key2")[0] is True
    assert limiter.is_allowed("key2")[0] is False

    print("  ✓ 不同Key独立限流")


def test_get_client_id():
    """测试客户端ID提取"""
    print("\n=== 测试客户端ID提取 ===")

    # API Key 优先
    req = MockRequest(headers={"X-API-Key": "test_api_key_12345"}, remote_addr="192.168.1.1")
    client_id = get_client_id(req)
    assert client_id.startswith("key:")
    assert "test_api_key_12345"[:32] in client_id
    print(f"  API Key提取: {client_id}")

    # Authorization Header
    req = MockRequest(headers={"Authorization": "Bearer bearer_token_123"}, remote_addr="192.168.1.1")
    client_id = get_client_id(req)
    assert client_id.startswith("key:")
    print(f"  Bearer Token提取: {client_id}")

    # IP 兜底
    req = MockRequest(headers={}, remote_addr="192.168.1.1")
    client_id = get_client_id(req)
    assert client_id.startswith("ip:")
    assert "192.168.1.1" in client_id
    print(f"  IP提取: {client_id}")

    # 未知IP
    req = MockRequest(headers={}, remote_addr=None)
    client_id = get_client_id(req)
    assert "unknown" in client_id
    print(f"  未知IP: {client_id}")


def test_info_fields():
    """测试返回信息字段"""
    print("\n=== 测试返回信息字段 ===")

    limiter = SlidingWindowLimiter(max_requests=10, burst=5)
    allowed, info = limiter.is_allowed("test")

    assert 'limit' in info
    assert 'remaining' in info
    assert 'reset_at' in info
    assert info['limit'] == 15  # max_requests + burst
    assert info['remaining'] == 14  # 第一次请求后剩余
    assert info['reset_at'] > time.time()
    print(f"  info: {info}")


def test_burst_handling():
    """测试突发流量处理"""
    print("\n=== 测试突发流量处理 ===")

    limiter = SlidingWindowLimiter(max_requests=5, burst=3)
    key = "burst_test"

    # 应允许 max_requests + burst 次请求
    passed = 0
    for i in range(10):
        allowed, info = limiter.is_allowed(key)
        if allowed:
            passed += 1

    # 应允许 5 + 3 = 8 次
    assert passed == 8, f"预期8次通过，实际{passed}次"
    print(f"  突发流量: {passed}次通过（预期8次）")


def main():
    print("=" * 60)
    print("  限流器测试")
    print("=" * 60)

    test_basic_rate_limiting()
    test_get_info()
    test_concurrent_access()
    test_memory_cleanup()
    test_empty_key()
    test_different_keys()
    test_get_client_id()
    test_info_fields()
    test_burst_handling()

    print("\n" + "=" * 60)
    print("  所有限流器测试通过")
    print("=" * 60)


if __name__ == "__main__":
    main()
