"""
缓存层测试脚本
"""

import time
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


def main():
    print("=== 缓存层测试 ===\n")

    # 1. 装饰器缓存
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

    # 2. 手动读写
    print("\n2. 测试手动缓存读写...")
    cache_set("test_key", {"value": 42}, ttl=5)
    val = cache_get("test_key")
    assert val == {"value": 42}
    print(f"  写入/读取: {val}")

    cache_delete("test_key")
    assert cache_get("test_key") is None
    print("  ✓ 删除生效")

    # 3. 统计信息
    print("\n3. 缓存统计...")
    stats = cache_stats()
    print(f"  内存缓存: {stats['memory']}")
    print(f"  Redis 缓存: {stats['redis']}")

    # 4. 清理
    print("\n4. 清空缓存...")
    cache_clear()
    print("  ✓ 已清空")

    print("\n=== 缓存测试完成 ===")


if __name__ == "__main__":
    main()
