"""
限流器测试
覆盖滑动窗口限流、并发安全、内存泄漏修复路径、配置关闭限流、client_id 提取。
"""

import threading
import time

from rate_limiter import SlidingWindowLimiter, check_rate_limit, get_client_id


def test_basic_limiting():
    """基本限流：max 3 + burst 1 = 4"""
    print("\n=== 基本限流 ===")
    limiter = SlidingWindowLimiter(max_requests=3, burst=1)
    key = "test_client"

    for i in range(5):
        allowed, info = limiter.is_allowed(key)
        print(f"  第 {i+1} 次: allowed={allowed}, remaining={info['remaining']}")

    assert allowed is False, "第 5 次应被限流"
    print("  ✅ 基本限流正确")


def test_get_info_no_increment():
    """get_info 不增加计数"""
    print("\n=== 查询不增加计数 ===")
    limiter = SlidingWindowLimiter(max_requests=3, burst=1)
    key = "info_client"

    limiter.is_allowed(key)
    info1 = limiter.get_info(key)
    info2 = limiter.get_info(key)
    assert info1["remaining"] == info2["remaining"]
    print("  ✅ 查询不增加计数正确")


def test_empty_key():
    """空 key 应直接放行"""
    print("\n=== 空 key 放行 ===")
    limiter = SlidingWindowLimiter(max_requests=1, burst=0)
    allowed, info = limiter.is_allowed("")
    assert allowed is True
    assert info == {}
    print("  ✅ 空 key 放行正确")


def test_concurrent_safety():
    """并发安全：多线程同时请求不应超发"""
    print("\n=== 并发安全 ===")
    limiter = SlidingWindowLimiter(max_requests=100, burst=0)
    key = "concurrent"
    allowed_count = {"n": 0}
    lock = threading.Lock()

    def worker():
        for _ in range(20):
            allowed, _ = limiter.is_allowed(key)
            if allowed:
                with lock:
                    allowed_count["n"] += 1

    threads = [threading.Thread(target=worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert allowed_count["n"] == 100, f"并发下应恰好通过 100 次，实际 {allowed_count['n']}"
    print(f"  ✅ 并发安全正确（通过 {allowed_count['n']}/200 次）")


def test_memory_leak_cleanup():
    """内存泄漏修复：过期桶清空后应删除 key 条目"""
    print("\n=== 内存泄漏清理 ===")
    limiter = SlidingWindowLimiter(max_requests=10, window_seconds=1, burst=0)
    key = "leak_test"

    limiter.is_allowed(key)
    assert key in limiter._buckets

    # 等待 2 个窗口周期以上，确保旧桶完全过期（window_start = now_bucket - 1，需跨 2 个 bucket）
    time.sleep(2.5)
    limiter.is_allowed(key)  # 触发清理并创建新桶

    # 再等待一轮，让刚才创建的桶也过期，再次触发清理
    time.sleep(2.5)
    limiter.is_allowed(key)
    buckets = limiter._buckets.get(key, {})
    assert len(buckets) <= 1, f"过期桶应被清理，实际剩余 {len(buckets)} 个"
    print("  ✅ 内存泄漏清理正确")


def test_check_rate_limit_disabled():
    """限流关闭时应直接放行"""
    print("\n=== 限流关闭放行 ===")
    import rate_limiter
    original = rate_limiter.settings.rate_limit_enabled
    rate_limiter.settings.rate_limit_enabled = False

    try:
        allowed, info = check_rate_limit("any_client")
        assert allowed is True
        assert info["limit"] == 0
    finally:
        rate_limiter.settings.rate_limit_enabled = original
    print("  ✅ 限流关闭放行正确")


def test_get_client_id():
    """从请求中提取 client_id"""
    print("\n=== Client ID 提取 ===")

    class FakeRequest:
        def __init__(self, headers=None, remote_addr=None):
            self.headers = headers or {}
            self.remote_addr = remote_addr

    # API Key 优先
    req1 = FakeRequest(headers={"X-API-Key": "mysecretkey123"}, remote_addr="1.2.3.4")
    assert get_client_id(req1) == "key:mysecretkey123"

    # Authorization Bearer
    req2 = FakeRequest(headers={"Authorization": "Bearer tokenabc"}, remote_addr="1.2.3.4")
    assert get_client_id(req2) == "key:tokenabc"

    # IP 兜底
    req3 = FakeRequest(headers={}, remote_addr="5.6.7.8")
    assert get_client_id(req3) == "ip:5.6.7.8"

    # 无 remote_addr
    req4 = FakeRequest(headers={})
    assert get_client_id(req4) == "ip:unknown"
    print("  ✅ Client ID 提取正确")


def main():
    print("=" * 60)
    print("  限流器模块测试")
    print("=" * 60)

    test_basic_limiting()
    test_get_info_no_increment()
    test_empty_key()
    test_concurrent_safety()
    test_memory_leak_cleanup()
    test_check_rate_limit_disabled()
    test_get_client_id()

    print("\n" + "=" * 60)
    print("  ✅ 全部限流器测试通过")
    print("=" * 60)


if __name__ == "__main__":
    main()
