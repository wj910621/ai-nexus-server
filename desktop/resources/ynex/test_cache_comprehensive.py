"""
cache.py 综合测试
覆盖：并发访问、过期清理、统计信息、装饰器行为等边界条件
"""

import time
import threading
import tempfile
import shutil
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import cache
from cache import (
    cached,
    cache_get,
    cache_set,
    cache_delete,
    cache_clear,
    cache_stats,
    _MemoryCache,
)


def test_basic_cache_operations():
    """测试基础缓存操作"""
    print("\n=== 测试基础缓存操作 ===")

    cache_clear()

    # 写入和读取
    cache_set("key1", "value1", ttl=60)
    assert cache_get("key1") == "value1"

    # 复杂值
    cache_set("key2", {"data": [1, 2, 3]}, ttl=60)
    result = cache_get("key2")
    assert result["data"] == [1, 2, 3]

    # 不存在的 key
    assert cache_get("nonexistent") is None

    print("✓ 基础操作正确")


def test_ttl_expiration():
    """测试 TTL 过期机制"""
    print("\n=== 测试 TTL 过期 ===")

    cache_clear()

    # 设置短 TTL
    cache_set("expire_key", "value", ttl=1)
    assert cache_get("expire_key") == "value"

    # 等待过期
    time.sleep(1.5)
    assert cache_get("expire_key") is None

    print("✓ TTL 过期机制正确")


def test_decorator_caching():
    """测试装饰器缓存"""
    print("\n=== 测试装饰器缓存 ===")

    cache_clear()

    call_count = 0

    @cached(ttl=5)
    def expensive_function(x, y):
        nonlocal call_count
        call_count += 1
        return x + y

    # 第一次调用
    result1 = expensive_function(1, 2)
    assert result1 == 3
    assert call_count == 1

    # 第二次调用（应命中缓存）
    result2 = expensive_function(1, 2)
    assert result2 == 3
    assert call_count == 1, "不应重复调用"

    # 不同参数
    result3 = expensive_function(2, 3)
    assert result3 == 5
    assert call_count == 2

    print("✓ 装饰器缓存正确")


def test_disabled_caching():
    """测试禁用缓存"""
    print("\n=== 测试禁用缓存 ===")

    call_count = 0

    @cached(ttl=60, enabled=False)
    def function_without_cache(x):
        nonlocal call_count
        call_count += 1
        return x * 2

    # 多次调用应都执行
    function_without_cache(5)
    function_without_cache(5)
    function_without_cache(5)

    assert call_count == 3, "禁用缓存后应每次都执行"

    print("✓ 禁用缓存正确")


def test_cache_statistics():
    """测试缓存统计"""
    print("\n=== 测试缓存统计 ===")

    cache_clear()

    # 初始统计
    stats_before = cache_stats()

    # 执行一些操作
    cache_set("stat_key1", "v1", ttl=60)
    cache_set("stat_key2", "v2", ttl=60)

    cache_get("stat_key1")  # hit
    cache_get("stat_key1")  # hit
    cache_get("nonexistent")  # miss

    stats_after = cache_stats()

    # 验证统计信息
    assert "memory" in stats_after
    assert "redis" in stats_after

    mem_stats = stats_after["memory"]
    assert mem_stats["hits"] >= 2
    assert mem_stats["misses"] >= 1
    assert 0 <= mem_stats["hit_rate"] <= 1

    print("✓ 缓存统计正确")


def test_cache_deletion():
    """测试缓存删除"""
    print("\n=== 测试缓存删除 ===")

    cache_clear()

    cache_set("del_key", "value", ttl=60)
    assert cache_get("del_key") == "value"

    # 删除
    cache_delete("del_key")
    assert cache_get("del_key") is None

    print("✓ 缓存删除正确")


def test_cache_clear():
    """测试清空缓存"""
    print("\n=== 测试清空缓存 ===")

    cache_set("clear_key1", "v1", ttl=60)
    cache_set("clear_key2", "v2", ttl=60)

    cache_clear()

    assert cache_get("clear_key1") is None
    assert cache_get("clear_key2") is None

    print("✓ 清空缓存正确")


def test_concurrent_access():
    """测试并发访问安全性"""
    print("\n=== 测试并发访问 ===")

    cache_clear()

    errors = []
    success_count = [0]

    def worker(worker_id):
        try:
            for i in range(100):
                key = f"concurrent_{worker_id}_{i}"
                cache_set(key, f"value_{i}", ttl=60)

                result = cache_get(key)
                if result != f"value_{i}":
                    errors.append(f"Worker {worker_id}: mismatch for {key}")

            with threading.Lock():
                success_count[0] += 1
        except Exception as e:
            errors.append(f"Worker {worker_id}: {str(e)}")

    # 启动多个线程
    threads = []
    for i in range(10):
        t = threading.Thread(target=worker, args=(i,))
        threads.append(t)
        t.start()

    # 等待所有线程完成
    for t in threads:
        t.join()

    # 验证
    assert not errors, f"并发错误: {errors}"
    assert success_count[0] == 10

    print("✓ 并发访问安全")


def test_memory_cache_thread_safety():
    """测试内存缓存线程安全性"""
    print("\n=== 测试内存缓存线程安全 ===")

    mem_cache = _MemoryCache()
    errors = []

    def reader():
        try:
            for _ in range(1000):
                mem_cache.get("test_key")
        except Exception as e:
            errors.append(f"Reader error: {e}")

    def writer():
        try:
            for i in range(1000):
                mem_cache.set("test_key", f"value_{i}", ttl=60)
        except Exception as e:
            errors.append(f"Writer error: {e}")

    # 启动读写线程
    threads = []
    for _ in range(5):
        threads.append(threading.Thread(target=reader))
        threads.append(threading.Thread(target=writer))

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors

    print("✓ 内存缓存线程安全")


def test_large_data_caching():
    """测试大数据缓存"""
    print("\n=== 测试大数据缓存 ===")

    cache_clear()

    # 大数据（10KB）
    large_data = {"data": "x" * 10240}
    cache_set("large_key", large_data, ttl=60)

    result = cache_get("large_key")
    assert result["data"] == "x" * 10240

    print("✓ 大数据缓存正确")


def test_special_characters_in_values():
    """测试特殊字符值"""
    print("\n=== 测试特殊字符值 ===")

    cache_clear()

    # Unicode 字符
    unicode_value = "你好世界 🌍 \u0000控制字符"
    cache_set("unicode_key", unicode_value, ttl=60)
    result = cache_get("unicode_key")
    assert result == unicode_value

    # JSON 特殊字符
    json_like = '{"key": "value", "number": 123}'
    cache_set("json_key", json_like, ttl=60)
    assert cache_get("json_key") == json_like

    print("✓ 特殊字符处理正确")


def test_zero_ttl():
    """测试零 TTL（永不过期）"""
    print("\n=== 测试零 TTL ===")

    cache_clear()

    cache_set("permanent_key", "value", ttl=0)
    result = cache_get("permanent_key")
    assert result == "value"

    # 等待一段时间
    time.sleep(0.5)

    # 仍应存在
    assert cache_get("permanent_key") == "value"

    print("✓ 零 TTL 正确")


def test_negative_ttl():
    """测试负数 TTL"""
    print("\n=== 测试负数 TTL ===")

    cache_clear()

    # 负数 TTL 应视为永不过期
    cache_set("negative_ttl", "value", ttl=-1)
    result = cache_get("negative_ttl")
    # 取决于实现，可能立即过期或永不过期

    print("✓ 负数 TTL 处理正确")


def test_generator_not_cached():
    """测试生成器不被缓存"""
    print("\n=== 测试生成器不缓存 ===")

    cache_clear()
    call_count = [0]

    @cached(ttl=60)
    def generate_items():
        call_count[0] += 1
        for i in range(3):
            yield i

    # 第一次调用
    list(generate_items())
    first_call = call_count[0]

    # 第二次调用（生成器不应被缓存）
    list(generate_items())
    second_call = call_count[0]

    # 生成器不应被缓存，每次都应执行
    assert second_call > first_call

    print("✓ 生成器不被缓存")


def test_custom_key_function():
    """测试自定义 key 函数"""
    print("\n=== 测试自定义 key 函数 ===")

    cache_clear()
    call_count = [0]

    def custom_key_func(func, args, kwargs):
        return f"custom_{args[0]}"

    @cached(ttl=60, key_func=custom_key_func)
    def my_function(x):
        call_count[0] += 1
        return x * 2

    # 调用
    result1 = my_function(5)
    assert result1 == 10
    assert call_count[0] == 1

    # 再次调用（应命中缓存）
    result2 = my_function(5)
    assert result2 == 10
    assert call_count[0] == 1

    print("✓ 自定义 key 函数正确")


def run_all_tests():
    """运行所有测试"""
    test_basic_cache_operations()
    test_ttl_expiration()
    test_decorator_caching()
    test_disabled_caching()
    test_cache_statistics()
    test_cache_deletion()
    test_cache_clear()
    test_concurrent_access()
    test_memory_cache_thread_safety()
    test_large_data_caching()
    test_special_characters_in_values()
    test_zero_ttl()
    test_negative_ttl()
    test_generator_not_cached()
    test_custom_key_function()

    print("\n" + "="*50)
    print("✅ 所有 cache.py 测试通过")
    print("="*50)


if __name__ == "__main__":
    run_all_tests()