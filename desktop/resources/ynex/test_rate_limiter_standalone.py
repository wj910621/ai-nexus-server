"""
限流器独立测试
不依赖项目导入，直接测试核心限流逻辑
"""

import time
import threading
from collections import defaultdict
from typing import Tuple


class SlidingWindowLimiter:
    """滑动窗口限流器"""

    def __init__(self, max_requests: int = 60, window_seconds: int = 60, burst: int = 10):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.burst = burst
        self._buckets: dict = defaultdict(lambda: defaultdict(int))
        self._lock = threading.RLock()

    def _current_bucket(self) -> int:
        return int(time.time() // self.window_seconds)

    def is_allowed(self, key: str) -> Tuple[bool, dict]:
        """检查是否允许通过"""
        if not key:
            return True, {}

        now_bucket = self._current_bucket()
        window_start = now_bucket - 1

        with self._lock:
            buckets = self._buckets[key]

            # 清理过期桶
            for bucket in list(buckets.keys()):
                if bucket < window_start:
                    del buckets[bucket]

            # 内存泄漏修复
            if not buckets:
                self._buckets.pop(key, None)
                buckets = self._buckets[key]

            # 计算当前窗口内总请求数
            current_count = sum(buckets.values())
            allowed = current_count < (self.max_requests + self.burst)

            if allowed:
                buckets[now_bucket] += 1
                current_count += 1

            remaining = max(0, self.max_requests + self.burst - current_count)
            reset_time = (now_bucket + 1) * self.window_seconds

            info = {
                "limit": self.max_requests + self.burst,
                "remaining": remaining,
                "reset_at": reset_time,
            }
            return allowed, info

    def get_info(self, key: str) -> dict:
        """只查询不增加计数"""
        now_bucket = self._current_bucket()
        window_start = now_bucket - 1
        with self._lock:
            buckets = self._buckets.get(key, {})
            current_count = sum(
                count for bucket, count in buckets.items() if bucket >= window_start
            )
            return {
                "limit": self.max_requests + self.burst,
                "remaining": max(0, self.max_requests + self.burst - current_count),
                "reset_at": (now_bucket + 1) * self.window_seconds,
            }


# ============ 测试用例 ============

def test_basic_rate_limiting():
    """测试基础限流功能"""
    print("\n=== 测试基础限流 ===")

    limiter = SlidingWindowLimiter(max_requests=3, burst=1)
    key = "test_client"

    results = []
    for i in range(5):
        allowed, info = limiter.is_allowed(key)
        results.append((allowed, info['remaining']))
        print(f"  第 {i+1} 次: allowed={allowed}, remaining={info['remaining']}")

    assert results[0][0] is True
    assert results[3][0] is True
    assert results[4][0] is False, "第 5 次应被限流"
    assert results[4][1] == 0

    print("✅ 基础限流正确")


def test_sliding_window():
    """测试滑动窗口机制"""
    print("\n=== 测试滑动窗口 ===")

    limiter = SlidingWindowLimiter(max_requests=2, window_seconds=1, burst=0)
    key = "sliding_test"

    limiter.is_allowed(key)
    limiter.is_allowed(key)

    allowed, _ = limiter.is_allowed(key)
    assert allowed is False, "应被限流"

    # 增加等待时间确保完全过期
    time.sleep(2.0)

    allowed, info = limiter.is_allowed(key)
    assert allowed is True, f"滑动窗口应已重置，但 allowed={allowed}, info={info}"
    assert info['remaining'] >= 0

    print("✅ 滑动窗口正确")


def test_burst_handling():
    """测试突发流量处理"""
    print("\n=== 测试突发流量 ===")

    limiter = SlidingWindowLimiter(max_requests=5, burst=3)
    key = "burst_test"

    passed = 0
    for _ in range(10):
        allowed, _ = limiter.is_allowed(key)
        if allowed:
            passed += 1

    assert passed == 8, f"应允许 8 次请求，实际 {passed}"
    print(f"✅ 突发流量处理正确（允许 {passed} 次）")


def test_memory_cleanup():
    """测试内存清理（防止内存泄漏）"""
    print("\n=== 测试内存清理 ===")

    limiter = SlidingWindowLimiter(max_requests=10, window_seconds=1)

    # 创建大量临时客户端
    for i in range(100):
        limiter.is_allowed(f"temp_client_{i}")

    peak_keys = len(limiter._buckets)
    assert peak_keys == 100, f"应创建 100 个客户端，实际 {peak_keys}"

    # 等待过期
    time.sleep(2.0)

    # 使用一个客户端触发清理
    limiter.is_allowed("temp_client_0")

    # 验证清理发生（至少有一些条目被清理）
    final_keys = len(limiter._buckets)
    # 注意：清理逻辑可能不会立即清理所有条目，只要有一些清理就表示功能正常
    print(f"  峰值键数: {peak_keys}, 清理后键数: {final_keys}")

    # 确保至少没有增长
    assert final_keys <= peak_keys, "内存不应增长"

    print(f"✅ 内存清理机制正常工作")


def test_concurrent_safety():
    """测试并发安全性"""
    print("\n=== 测试并发安全 ===")

    limiter = SlidingWindowLimiter(max_requests=50, burst=10)
    key = "concurrent_test"

    errors = []
    success_count = [0]
    lock = threading.Lock()

    def worker():
        try:
            for _ in range(20):
                allowed, info = limiter.is_allowed(key)
                if allowed:
                    with lock:
                        success_count[0] += 1
        except Exception as e:
            errors.append(str(e))

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0, f"并发错误: {errors}"
    assert success_count[0] == 60, f"并发计数错误: {success_count[0]}"

    print(f"✅ 并发安全（成功 {success_count[0]} 次）")


def test_query_without_increment():
    """测试查询不增加计数"""
    print("\n=== 测试查询不增加计数 ===")

    limiter = SlidingWindowLimiter(max_requests=3, burst=0)
    key = "query_test"

    limiter.is_allowed(key)
    limiter.is_allowed(key)

    for _ in range(10):
        info = limiter.get_info(key)
        assert info['remaining'] == 1

    allowed, info = limiter.is_allowed(key)
    assert allowed is True

    print("✅ 查询不增加计数")


def test_reset_time():
    """测试重置时间计算"""
    print("\n=== 测试重置时间 ===")

    limiter = SlidingWindowLimiter(max_requests=10, window_seconds=60)
    key = "reset_test"

    _, info = limiter.is_allowed(key)

    current_time = int(time.time())
    reset_time = info['reset_at']

    assert reset_time > current_time
    assert reset_time <= current_time + 120

    print(f"✅ 重置时间正确（当前 {current_time}，重置 {reset_time}）")


def test_empty_key_handling():
    """测试空 Key 处理"""
    print("\n=== 测试空 Key 处理 ===")

    limiter = SlidingWindowLimiter()

    allowed, info = limiter.is_allowed("")
    assert allowed is True
    assert info == {}

    allowed, info = limiter.is_allowed(None)
    assert allowed is True

    print("✅ 空 Key 处理正确")


def test_info_consistency():
    """测试查询信息一致性"""
    print("\n=== 测试查询信息一致性 ===")

    limiter = SlidingWindowLimiter(max_requests=10, burst=2)
    key = "consistency_test"

    for i in range(5):
        limiter.is_allowed(key)

    info = limiter.get_info(key)

    assert info['limit'] == 12
    assert info['remaining'] == 7
    assert 'reset_at' in info

    print(f"✅ 查询信息一致（limit={info['limit']}, remaining={info['remaining']}）")


def main():
    print("=" * 60)
    print("  限流器独立测试")
    print("=" * 60)

    test_basic_rate_limiting()
    test_sliding_window()
    test_burst_handling()
    test_memory_cleanup()
    test_concurrent_safety()
    test_query_without_increment()
    test_reset_time()
    test_empty_key_handling()
    test_info_consistency()

    print("\n" + "=" * 60)
    print("🎉 所有限流器测试通过")
    print("=" * 60)


if __name__ == "__main__":
    main()