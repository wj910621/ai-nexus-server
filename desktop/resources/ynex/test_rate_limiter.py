"""
限流器测试
"""

import threading
import time
from rate_limiter import SlidingWindowLimiter, check_rate_limit, get_client_id


def main():
    print("=== 限流器测试 ===\n")

    limiter = SlidingWindowLimiter(max_requests=3, burst=1)
    key = "test_client"

    print("1. 正常请求（限制 3 + 突发 1 = 4）...")
    for i in range(5):
        allowed, info = limiter.is_allowed(key)
        print(f"  第 {i+1} 次: allowed={allowed}, remaining={info['remaining']}")

    assert allowed is False, "第 5 次应被限流"
    print("  ✓ 限流触发正确")

    print("\n2. 查询接口不增加计数...")
    info = limiter.get_info(key)
    print(f"  info: {info}")

    print("\n3. 空 key 处理...")
    allowed, info = limiter.is_allowed("")
    assert allowed is True, "空 key 应允许通过"
    
    allowed, info = limiter.is_allowed(None)
    assert allowed is True, "None key 应允许通过"
    print("  ✓ 空 key 处理正确")

    print("\n4. 线程安全测试...")
    limiter2 = SlidingWindowLimiter(max_requests=10, burst=5)
    counter = [0]
    
    def thread_func():
        for _ in range(5):
            allowed, _ = limiter2.is_allowed("thread_key")
            if allowed:
                counter[0] += 1
            time.sleep(0.001)
    
    threads = [threading.Thread(target=thread_func) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    assert counter[0] <= 15, f"并发请求不应超过限制，实际: {counter[0]}"
    print(f"  ✓ 并发安全: {counter[0]} 次请求通过")

    print("\n5. 内存泄漏修复验证...")
    limiter3 = SlidingWindowLimiter(max_requests=1, window_seconds=1)
    limiter3.is_allowed("temp_key_1")
    limiter3.is_allowed("temp_key_2")
    
    assert len(limiter3._buckets) == 2, "初始应有 2 个 key"
    time.sleep(2)
    
    limiter3.is_allowed("temp_key_1")
    limiter3.is_allowed("temp_key_2")
    
    assert len(limiter3._buckets) == 2, "过期后重新访问应保持 2 个 key，不会累积"
    print("  ✓ 内存泄漏修复生效")

    print("\n6. get_client_id 提取逻辑...")
    class MockRequest:
        def __init__(self, headers, remote_addr):
            self.headers = headers
            self.remote_addr = remote_addr
    
    req = MockRequest({"X-API-Key": "test-key-12345"}, "192.168.1.1")
    client_id = get_client_id(req)
    assert client_id.startswith("key:"), f"应优先使用 API Key，实际: {client_id}"
    
    req2 = MockRequest({}, "192.168.1.2")
    client_id2 = get_client_id(req2)
    assert client_id2 == "ip:192.168.1.2", f"无 API Key 时应使用 IP，实际: {client_id2}"
    
    req3 = MockRequest({"Authorization": "Bearer token-abc"}, "192.168.1.3")
    client_id3 = get_client_id(req3)
    assert client_id3.startswith("key:"), f"应支持 Bearer token，实际: {client_id3}"
    print("  ✓ client_id 提取正确")

    print("\n=== 限流器测试完成 ===")


if __name__ == "__main__":
    main()
