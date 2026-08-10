"""
缓存层测试脚本
测试内存缓存、Redis 缓存、装饰器、并发安全和边界条件
"""

import time
import threading
import sys
import os
import hashlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cache import (
    cached,
    cache_get,
    cache_set,
    cache_delete,
    cache_clear,
    cache_stats,
    _MemoryCache,
    _make_key,
)


class TestMemoryCache:
    """内存缓存测试"""

    def test_basic_get_set(self):
        """基础读写"""
        cache = _MemoryCache()
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_get_nonexistent_key(self):
        """读取不存在的键应返回 None"""
        cache = _MemoryCache()
        assert cache.get("nonexistent") is None

    def test_delete_key(self):
        """删除键"""
        cache = _MemoryCache()
        cache.set("key1", "value1")
        cache.delete("key1")
        assert cache.get("key1") is None

    def test_clear_all(self):
        """清空所有缓存"""
        cache = _MemoryCache()
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.clear()
        assert cache.get("key1") is None
        assert cache.get("key2") is None

    def test_ttl_expiry(self):
        """TTL 过期测试"""
        cache = _MemoryCache()
        cache.set("key1", "value1", ttl=1)
        assert cache.get("key1") == "value1"
        time.sleep(1.1)
        assert cache.get("key1") is None

    def test_ttl_zero_no_expiry(self):
        """TTL 为 0 表示永不过期"""
        cache = _MemoryCache()
        cache.set("key1", "value1", ttl=0)
        time.sleep(0.5)
        assert cache.get("key1") == "value1"

    def test_overwrite_key(self):
        """覆盖已存在的键"""
        cache = _MemoryCache()
        cache.set("key1", "value1")
        cache.set("key1", "value2")
        assert cache.get("key1") == "value2"

    def test_stats_tracking(self):
        """统计信息追踪"""
        cache = _MemoryCache()
        cache.set("key1", "value1")

        # 命中
        cache.get("key1")
        # 未命中
        cache.get("nonexistent")

        stats = cache.stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["size"] == 1
        assert 0 < stats["hit_rate"] < 1

    def test_concurrent_access(self):
        """并发访问安全"""
        cache = _MemoryCache()
        errors = []

        def reader():
            try:
                for i in range(100):
                    cache.get(f"key_{i % 10}")
            except Exception as e:
                errors.append(e)

        def writer():
            try:
                for i in range(100):
                    cache.set(f"key_{i % 10}", f"value_{i}")
            except Exception as e:
                errors.append(e)

        threads = []
        for _ in range(5):
            threads.append(threading.Thread(target=reader))
            threads.append(threading.Thread(target=writer))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"并发访问出错: {errors}"

    def test_high_volume(self):
        """高容量测试"""
        cache = _MemoryCache()
        for i in range(1000):
            cache.set(f"key_{i}", f"value_{i}")

        for i in range(1000):
            assert cache.get(f"key_{i}") == f"value_{i}"

        assert cache.stats()["size"] == 1000


class TestCachedDecorator:
    """缓存装饰器测试"""

    def test_basic_caching(self):
        """基础装饰器缓存"""
        call_count = 0

        @cached(ttl=1)
        def expensive_function(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        # 第一次调用
        result1 = expensive_function(5)
        assert result1 == 10
        assert call_count == 1

        # 第二次调用（缓存命中）
        result2 = expensive_function(5)
        assert result2 == 10
        assert call_count == 1  # 未增加

    def test_different_args_different_cache(self):
        """不同参数使用不同缓存"""
        call_count = 0

        @cached(ttl=1)
        def func(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        result1 = func(1)
        result2 = func(2)
        result3 = func(1)  # 缓存命中

        assert result1 == 2
        assert result2 == 4
        assert result3 == 2
        assert call_count == 2  # 只调用 2 次

    def test_ttl_expiry(self):
        """装饰器 TTL 过期"""
        call_count = 0

        @cached(ttl=1)
        def func(x):
            nonlocal call_count
            call_count += 1
            return x

        func(1)
        time.sleep(1.1)
        func(1)

        assert call_count == 2  # 过期后重新调用

    def test_disabled_caching(self):
        """禁用缓存"""
        call_count = 0

        @cached(ttl=1, enabled=False)
        def func(x):
            nonlocal call_count
            call_count += 1
            return x

        func(1)
        func(1)

        assert call_count == 2  # 禁用时每次都调用

    def test_custom_key_func(self):
        """自定义 key 生成函数"""
        call_count = 0

        def custom_key_func(func, args, kwargs):
            return f"custom:{args[0]}"

        @cached(ttl=1, key_func=custom_key_func)
        def func(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        result1 = func(5)
        result2 = func(5)

        assert result1 == result2 == 10
        assert call_count == 1

    def test_manual_cache_delete(self):
        """手动删除缓存"""
        call_count = 0

        @cached(ttl=10)
        def func(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        func(5)
        func(5)
        assert call_count == 1

        # 手动删除
        func.cache_delete(5)
        func(5)
        assert call_count == 2

    def test_generator_not_cached(self):
        """生成器不缓存"""
        call_count = 0

        @cached(ttl=10)
        def gen_func(n):
            nonlocal call_count
            call_count += 1
            for i in range(n):
                yield i

        # 第一次调用
        list(gen_func(3))
        assert call_count == 1

        # 第二次调用（不缓存，重新执行）
        list(gen_func(3))
        assert call_count == 2


class TestGlobalCacheAPI:
    """全局缓存 API 测试"""

    def test_set_get_delete(self):
        """手动 set/get/delete"""
        cache_clear()

        cache_set("test_key", {"value": 123}, ttl=5)
        result = cache_get("test_key")
        assert result == {"value": 123}

        cache_delete("test_key")
        assert cache_get("test_key") is None

    def test_overwrite(self):
        """覆盖已存在的键"""
        cache_clear()

        cache_set("key", "value1", ttl=5)
        cache_set("key", "value2", ttl=5)

        assert cache_get("key") == "value2"

    def test_stats(self):
        """统计信息"""
        cache_clear()

        cache_set("key1", "value1")
        cache_get("key1")
        cache_get("nonexistent")

        stats = cache_stats()
        assert "memory" in stats
        assert "redis" in stats

    def test_concurrent_operations(self):
        """并发操作"""
        cache_clear()
        errors = []

        def worker(worker_id):
            try:
                for i in range(50):
                    key = f"worker_{worker_id}_key_{i}"
                    cache_set(key, f"value_{i}", ttl=10)
                    cache_get(key)
                    cache_delete(key)
            except Exception as e:
                errors.append((worker_id, str(e)))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"并发操作出错: {errors}"


class TestMakeKey:
    """key 生成函数测试"""

    def test_basic_key_generation(self):
        """基础 key 生成"""
        def func(a, b):
            return a + b

        key = _make_key(func, (1, 2), {})
        assert isinstance(key, str)
        assert len(key) == 32  # MD5 hex

    def test_kwargs_in_key(self):
        """kwargs 影响 key"""
        def func(a, b):
            return a + b

        key1 = _make_key(func, (1,), {"b": 2})
        key2 = _make_key(func, (1, 2), {})

        # 不同参数应生成不同 key
        assert key1 != key2

    def test_same_args_same_key(self):
        """相同参数生成相同 key"""
        def func(a, b):
            return a + b

        key1 = _make_key(func, (1, 2), {})
        key2 = _make_key(func, (1, 2), {})

        assert key1 == key2

    def test_unserializable_args(self):
        """不可序列化的参数应 fallback"""
        class Unserializable:
            pass

        def func(obj):
            return obj

        # 不应崩溃
        key = _make_key(func, (Unserializable(),), {})
        assert isinstance(key, str)


class TestEdgeCases:
    """边界情况测试"""

    def test_empty_key(self):
        """空键名"""
        cache = _MemoryCache()
        cache.set("", "empty_key_value")
        assert cache.get("") == "empty_key_value"

    def test_none_value(self):
        """None 值"""
        cache = _MemoryCache()
        cache.set("none_key", None)
        # 注意：get 返回 None 可能是值本身，也可能是未找到
        # 需要依赖统计来区分
        stats_before = cache.stats()
        cache.get("none_key")
        stats_after = cache.stats()
        # 如果命中，misses 不应增加
        assert stats_after["misses"] == stats_before["misses"]

    def test_complex_value(self):
        """复杂值类型"""
        cache = _MemoryCache()

        # 嵌套字典
        complex_value = {
            "list": [1, 2, 3],
            "dict": {"nested": "value"},
            "tuple": (1, 2),
        }
        cache.set("complex", complex_value)
        assert cache.get("complex") == complex_value

    def test_unicode_key_and_value(self):
        """Unicode 键名和值"""
        cache = _MemoryCache()
        cache.set("中文键", "中文值")
        assert cache.get("中文键") == "中文值"

    def test_very_long_key(self):
        """超长键名"""
        cache = _MemoryCache()
        long_key = "a" * 10000
        cache.set(long_key, "value")
        assert cache.get(long_key) == "value"

    def test_very_long_value(self):
        """超长值"""
        cache = _MemoryCache()
        long_value = "x" * 100000
        cache.set("long_value_key", long_value)
        assert cache.get("long_value_key") == long_value


def run_all_tests():
    """运行所有测试"""
    test_classes = [
        TestMemoryCache,
        TestCachedDecorator,
        TestGlobalCacheAPI,
        TestMakeKey,
        TestEdgeCases,
    ]

    total_tests = 0
    passed_tests = 0
    failed_tests = []

    print("=" * 60)
    print("缓存层测试")
    print("=" * 60)

    for test_class in test_classes:
        print(f"\n{test_class.__name__}:")
        test_instance = test_class()

        test_methods = [
            method
            for method in dir(test_instance)
            if method.startswith("test_") and callable(getattr(test_instance, method))
        ]

        for method_name in test_methods:
            total_tests += 1
            try:
                method = getattr(test_instance, method_name)
                method()
                print(f"  ✓ {method_name}")
                passed_tests += 1
            except AssertionError as e:
                print(f"  ✗ {method_name}: {e}")
                failed_tests.append((test_class.__name__, method_name, str(e)))
            except Exception as e:
                print(f"  ✗ {method_name}: {type(e).__name__}: {e}")
                failed_tests.append((test_class.__name__, method_name, f"{type(e).__name__}: {e}"))

    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    print(f"总计: {total_tests} 个测试")
    print(f"通过: {passed_tests} 个")
    print(f"失败: {len(failed_tests)} 个")

    if failed_tests:
        print("\n失败的测试:")
        for class_name, method_name, error in failed_tests:
            print(f"  - {class_name}.{method_name}: {error}")
        return False
    else:
        print("\n✅ 所有测试通过")
        return True


@cached(ttl=2)
def slow_add(a, b):
    time.sleep(0.1)
    return a + b


def main():
    success = run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
