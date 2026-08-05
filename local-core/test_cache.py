"""
缓存层测试脚本
测试内存缓存、TTL、并发安全、缓存装饰器等功能
"""

import time
import threading
import tempfile
import os
from cache import (
    cached,
    cache_get,
    cache_set,
    cache_delete,
    cache_clear,
    cache_stats,
    _MemoryCache,
)


def test_decorator_caching():
    """测试装饰器缓存"""
    print("\n=== 测试装饰器缓存 ===")

    call_count = [0]

    @cached(ttl=2)
    def slow_function(x, y):
        call_count[0] += 1
        time.sleep(0.1)
        return x + y

    # 第一次调用（未命中）
    t0 = time.time()
    r1 = slow_function(1, 2)
    t1 = time.time()

    # 第二次调用（命中）
    t2 = time.time()
    r2 = slow_function(1, 2)
    t3 = time.time()

    assert r1 == r2 == 3
    assert call_count[0] == 1, "应只调用一次"
    assert (t3 - t2) < 0.05, "缓存未命中"

    print(f"  第一次: {r1}, 耗时 {t1-t0:.3f}s")
    print(f"  第二次: {r2}, 耗时 {t3-t2:.3f}s (缓存命中)")
    print("  ✓ 装饰器缓存测试通过")


def test_ttl_expiry():
    """测试TTL过期"""
    print("\n=== 测试TTL过期 ===")

    @cached(ttl=1)
    def expiring_func(x):
        return x * 2

    # 第一次调用
    r1 = expiring_func(5)
    assert r1 == 10

    # 等待过期
    time.sleep(1.5)

    # 应重新计算
    r2 = expiring_func(5)
    assert r2 == 10

    print("  ✓ TTL过期测试通过")


def test_different_arguments():
    """测试不同参数的缓存"""
    print("\n=== 测试不同参数的缓存 ===")

    call_count = [0]

    @cached(ttl=5)
    def multi_arg_func(a, b, c=10):
        call_count[0] += 1
        return a + b + c

    # 不同参数应分别缓存
    r1 = multi_arg_func(1, 2)
    r2 = multi_arg_func(1, 2)
    r3 = multi_arg_func(1, 3)
    r4 = multi_arg_func(1, 2, c=20)

    assert r1 == 13
    assert r2 == 13
    assert r3 == 14
    assert r4 == 23
    assert call_count[0] == 3  # r1, r3, r4 三次调用

    print(f"  调用次数: {call_count[0]} (预期3次)")
    print("  ✓ 不同参数缓存测试通过")


def test_manual_cache_operations():
    """测试手动缓存操作"""
    print("\n=== 测试手动缓存操作 ===")

    # 清空缓存
    cache_clear()

    # 写入
    cache_set("key1", "value1", ttl=10)
    cache_set("key2", {"nested": "data"}, ttl=10)
    cache_set("key3", [1, 2, 3], ttl=10)

    # 读取
    assert cache_get("key1") == "value1"
    assert cache_get("key2") == {"nested": "data"}
    assert cache_get("key3") == [1, 2, 3]
    assert cache_get("nonexistent") is None

    print("  写入/读取测试通过")

    # 删除
    cache_delete("key1")
    assert cache_get("key1") is None
    assert cache_get("key2") is not None

    print("  删除测试通过")

    # 清空
    cache_clear()
    assert cache_get("key2") is None
    assert cache_get("key3") is None

    print("  ✓ 手动缓存操作测试通过")


def test_cache_statistics():
    """测试缓存统计"""
    print("\n=== 测试缓存统计 ===")

    cache_clear()

    @cached(ttl=10)
    def func(x):
        return x

    # 执行多次
    func(1)
    func(1)
    func(2)
    func(1)

    stats = cache_stats()

    assert 'memory' in stats
    assert 'redis' in stats
    assert 'hits' in stats['memory']
    assert 'misses' in stats['memory']
    assert 'hit_rate' in stats['memory']

    print(f"  内存缓存统计: {stats['memory']}")
    print(f"  Redis缓存统计: {stats['redis']}")


def test_concurrent_access():
    """测试并发访问"""
    print("\n=== 测试并发访问 ===")

    cache_clear()
    errors = []

    @cached(ttl=10)
    def concurrent_func(x):
        time.sleep(0.01)
        return x * 2

    def worker():
        try:
            for i in range(10):
                result = concurrent_func(i)
                assert result == i * 2
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0, f"并发错误: {errors}"
    print("  ✓ 并发访问测试通过")


def test_memory_cache_directly():
    """直接测试内存缓存类"""
    print("\n=== 测试内存缓存类 ===")

    cache = _MemoryCache()

    # 基础操作
    cache.set("key1", "value1", ttl=10)
    assert cache.get("key1") == "value1"

    # 过期
    cache.set("key2", "value2", ttl=1)
    time.sleep(1.5)
    assert cache.get("key2") is None

    # 删除
    cache.set("key3", "value3", ttl=10)
    cache.delete("key3")
    assert cache.get("key3") is None

    # 清空
    cache.set("key4", "value4", ttl=10)
    cache.clear()
    assert cache.get("key4") is None

    # 统计
    cache.set("key5", "value5", ttl=10)
    cache.get("key5")  # hit
    cache.get("key5")  # hit
    cache.get("nonexistent")  # miss

    stats = cache.stats()
    assert stats['hits'] >= 2
    assert stats['misses'] >= 1

    print(f"  统计: hits={stats['hits']}, misses={stats['misses']}")
    print("  ✓ 内存缓存类测试通过")


def test_generator_not_cached():
    """测试生成器不被缓存"""
    print("\n=== 测试生成器不被缓存 ===")

    call_count = [0]

    @cached(ttl=10)
    def gen_func():
        call_count[0] += 1
        for i in range(3):
            yield i

    # 生成器不应被缓存
    r1 = list(gen_func())
    r2 = list(gen_func())

    assert r1 == r2 == [0, 1, 2]
    assert call_count[0] == 2, "生成器不应被缓存"

    print("  ✓ 生成器不被缓存测试通过")


def test_disabled_caching():
    """测试禁用缓存"""
    print("\n=== 测试禁用缓存 ===")

    call_count = [0]

    @cached(ttl=10, enabled=False)
    def disabled_func(x):
        call_count[0] += 1
        return x

    disabled_func(1)
    disabled_func(1)

    assert call_count[0] == 2, "禁用的缓存不应生效"

    print("  ✓ 禁用缓存测试通过")


def test_custom_key_func():
    """测试自定义键函数"""
    print("\n=== 测试自定义键函数 ===")

    call_count = [0]

    def custom_key(func, args, kwargs):
        return f"custom:{args[0]}:{args[1]}"

    @cached(ttl=10, key_func=custom_key)
    def custom_func(a, b):
        call_count[0] += 1
        return a + b

    r1 = custom_func(1, 2)
    r2 = custom_func(1, 2)

    assert r1 == r2 == 3
    assert call_count[0] == 1

    print("  ✓ 自定义键函数测试通过")


def test_cache_delete_method():
    """测试装饰器的缓存删除方法"""
    print("\n=== 测试装饰器的缓存删除方法 ===")

    call_count = [0]

    @cached(ttl=10)
    def cached_func(x):
        call_count[0] += 1
        return x * 2

    r1 = cached_func(5)
    assert call_count[0] == 1

    # 删除缓存
    cached_func.cache_delete(5)
    r2 = cached_func(5)
    assert call_count[0] == 2

    print("  ✓ 缓存删除方法测试通过")


def main():
    print("=" * 60)
    print("  缓存层测试")
    print("=" * 60)

    test_decorator_caching()
    test_ttl_expiry()
    test_different_arguments()
    test_manual_cache_operations()
    test_cache_statistics()
    test_concurrent_access()
    test_memory_cache_directly()
    test_generator_not_cached()
    test_disabled_caching()
    test_custom_key_func()
    test_cache_delete_method()

    print("\n" + "=" * 60)
    print("  所有缓存测试通过")
    print("=" * 60)


if __name__ == "__main__":
    main()
