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
    _memory_cache,
)


@cached(ttl=2)
def slow_add(a, b):
    time.sleep(0.1)
    return a + b


@cached(ttl=5, key_func=lambda f, args, kwargs: f"custom:{args[0]}")
def with_custom_key(x):
    time.sleep(0.05)
    return x * 10


@cached(ttl=5, enabled=False)
def disabled_cache_fn(x):
    time.sleep(0.05)
    return x + 1


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
    assert "hits" in stats["memory"]
    assert "misses" in stats["memory"]
    assert "hit_rate" in stats["memory"]

    # 4. 清理
    print("\n4. 清空缓存...")
    cache_clear()
    assert _memory_cache.stats()["size"] == 0
    print("  ✓ 已清空")

    # 5. 自定义 key_func：相同入参应被映射到同一 key
    print("\n5. 自定义 key_func...")
    cache_clear()
    a = with_custom_key(7)
    b = with_custom_key(7)
    assert a == 70 and b == 70
    # 通过内存缓存的 size 验证 key 是按自定义函数生成的
    assert _memory_cache.stats()["size"] >= 1
    # 验证自定义 key 前缀
    assert cache_get("custom:7") == 70
    print("  ✓ key_func 生效，相同入参映射到同一 key")

    # 6. enabled=False 装饰器：永不缓存，每次都执行原函数
    print("\n6. enabled=False 装饰器...")
    cache_clear()
    t0 = time.time()
    r1 = disabled_cache_fn(100)
    t1 = time.time()
    r2 = disabled_cache_fn(100)
    t2 = time.time()
    # 两次调用都应执行 sleep，耗时总和 >= 0.1s
    assert (t2 - t0) >= 0.09, f"enabled=False 时不应缓存, total={t2 - t0}"
    assert r1 == r2 == 101
    assert _memory_cache.stats()["size"] == 0, "enabled=False 时不应写入缓存"
    print(f"  ✓ enabled=False 时每次都执行原函数，总耗时 {t2 - t0:.3f}s")

    # 7. TTL=0 永不过期分支
    print("\n7. TTL=0（永不过期）...")
    cache_clear()
    cache_set("forever", "value", ttl=0)
    assert cache_get("forever") == "value"
    # 内存层不依赖 time.time 之外的过期检查；stats 应报告 size=1
    assert _memory_cache.stats()["size"] == 1
    print("  ✓ TTL=0 时永不过期")

    print("\n=== 缓存测试完成 ===")


if __name__ == "__main__":
    main()
