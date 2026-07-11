"""
缓存层测试脚本
"""

import time
import threading
from cache import (
    cached,
    cache_get,
    cache_set,
    cache_delete,
    cache_clear,
    cache_stats,
)


@cached(ttl=2)
def slow_add(a, b):
    time.sleep(0.1)
    return a + b


@cached(ttl=0)
def no_cache_func(x):
    return x * 2


def main():
    print("=== 缓存层测试 ===\n")

    print("1. 测试装饰器缓存（TTL=2s）...")
    t0 = time.time()
    r1 = slow_add(1, 2)
    t1 = time.time()
    r2 = slow_add(1, 2)
    t2 = time.time()
    print(f"  第一次调用: {r1}, 耗时 {t1 - t0:.3f}s")
    print(f"  第二次调用: {r2}, 耗时 {t2 - t1:.3f}s")
    assert r1 == r2 == 3
    assert t2 - t1 < 0.05, "缓存未命中"
    print("  ✓ 缓存命中生效")

    print("\n2. TTL 过期测试...")
    cache_set("ttl_test_key", "expiring_value", ttl=1)
    assert cache_get("ttl_test_key") == "expiring_value"
    
    time.sleep(1.5)
    assert cache_get("ttl_test_key") is None, "TTL 过期后缓存应失效"
    print("  ✓ TTL 过期生效")

    print("\n3. 测试手动缓存读写...")
    cache_set("test_key", {"value": 42}, ttl=5)
    val = cache_get("test_key")
    assert val == {"value": 42}
    print(f"  写入/读取: {val}")

    cache_delete("test_key")
    assert cache_get("test_key") is None
    print("  ✓ 删除生效")

    print("\n4. 线程安全测试...")
    counter = [0]
    
    @cached(ttl=5)
    def thread_safe_func(x):
        counter[0] += 1
        return x
    
    def thread_func():
        for _ in range(10):
            thread_safe_func(42)
            time.sleep(0.001)
    
    threads = [threading.Thread(target=thread_func) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    assert counter[0] == 1, f"缓存应只计算一次，实际计算次数: {counter[0]}"
    print("  ✓ 线程安全")

    print("\n5. 流式生成器不缓存...")
    @cached(ttl=10)
    def generator_func():
        for i in range(3):
            yield i
    
    result1 = list(generator_func())
    result2 = list(generator_func())
    assert result1 == [0, 1, 2]
    assert result2 == [0, 1, 2]
    print("  ✓ 流式生成器每次调用都执行")

    print("\n6. enabled=False 禁用缓存...")
    counter2 = [0]
    
    @cached(ttl=10, enabled=False)
    def disabled_cache_func(x):
        counter2[0] += 1
        return x
    
    disabled_cache_func(1)
    disabled_cache_func(1)
    assert counter2[0] == 2, "enabled=False 应每次都执行"
    print("  ✓ enabled=False 禁用缓存正确")

    print("\n7. 缓存统计...")
    stats = cache_stats()
    print(f"  内存缓存: {stats['memory']}")
    print(f"  Redis 缓存: {stats['redis']}")
    assert "hit_rate" in stats["memory"]
    assert "size" in stats["memory"]
    print("  ✓ 统计信息完整")

    print("\n8. 清空缓存...")
    cache_set("clear_test", "value", ttl=100)
    assert cache_get("clear_test") is not None
    cache_clear()
    assert cache_get("clear_test") is None
    print("  ✓ 已清空")

    print("\n=== 缓存测试完成 ===")


if __name__ == "__main__":
    main()
