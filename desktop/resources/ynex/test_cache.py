"""
缓存层测试 - 增强版
覆盖并发访问、TTL 边界、统计信息等关键逻辑
"""

import unittest
import time
import threading
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cache import (
    cached,
    cache_get,
    cache_set,
    cache_delete,
    cache_clear,
    cache_stats,
    _MemoryCache,
)


class TestMemoryCache(unittest.TestCase):
    """内存缓存测试"""

    def setUp(self):
        self.cache = _MemoryCache()

    def test_basic_set_get(self):
        """基础读写"""
        self.cache.set("key1", "value1", ttl=10)
        result = self.cache.get("key1")
        self.assertEqual(result, "value1")

    def test_missing_key(self):
        """缺失键"""
        result = self.cache.get("nonexistent")
        self.assertIsNone(result)

    def test_delete(self):
        """删除键"""
        self.cache.set("key1", "value1")
        self.cache.delete("key1")
        result = self.cache.get("key1")
        self.assertIsNone(result)

    def test_clear(self):
        """清空缓存"""
        self.cache.set("key1", "value1")
        self.cache.set("key2", "value2")
        self.cache.clear()
        self.assertIsNone(self.cache.get("key1"))
        self.assertIsNone(self.cache.get("key2"))

    def test_ttl_expiry(self):
        """TTL 过期"""
        self.cache.set("key1", "value1", ttl=1)
        time.sleep(1.1)
        result = self.cache.get("key1")
        self.assertIsNone(result)

    def test_ttl_not_expired(self):
        """TTL 未过期"""
        self.cache.set("key1", "value1", ttl=10)
        time.sleep(0.5)
        result = self.cache.get("key1")
        self.assertEqual(result, "value1")

    def test_zero_ttl_never_expires(self):
        """TTL=0 永不过期"""
        self.cache.set("key1", "value1", ttl=0)
        time.sleep(0.5)
        result = self.cache.get("key1")
        self.assertEqual(result, "value1")

    def test_stats(self):
        """统计信息"""
        self.cache.set("key1", "value1")
        self.cache.get("key1")  # hit
        self.cache.get("key1")  # hit
        self.cache.get("missing")  # miss

        stats = self.cache.stats()
        self.assertEqual(stats["hits"], 2)
        self.assertEqual(stats["misses"], 1)
        self.assertEqual(stats["size"], 1)
        self.assertAlmostEqual(stats["hit_rate"], 0.6667, places=2)

    def test_concurrent_access(self):
        """并发访问"""
        errors = []

        def writer():
            try:
                for i in range(100):
                    self.cache.set(f"key_{i}", f"value_{i}")
            except Exception as e:
                errors.append(e)

        def reader():
            try:
                for i in range(100):
                    self.cache.get(f"key_{i}")
            except Exception as e:
                errors.append(e)

        threads = []
        for _ in range(5):
            threads.append(threading.Thread(target=writer))
            threads.append(threading.Thread(target=reader))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"并发错误: {errors}")

    def test_overwrite_value(self):
        """覆盖写入"""
        self.cache.set("key1", "value1")
        self.cache.set("key1", "value2")
        result = self.cache.get("key1")
        self.assertEqual(result, "value2")


class TestCachedDecorator(unittest.TestCase):
    """缓存装饰器测试"""

    def setUp(self):
        cache_clear()

    def test_cache_hit(self):
        """缓存命中"""
        call_count = [0]

        @cached(ttl=10)
        def expensive_func(x):
            call_count[0] += 1
            return x * 2

        # 第一次调用
        result1 = expensive_func(5)
        self.assertEqual(result1, 10)
        self.assertEqual(call_count[0], 1)

        # 第二次调用（缓存命中）
        result2 = expensive_func(5)
        self.assertEqual(result2, 10)
        self.assertEqual(call_count[0], 1)  # 未增加

    def test_cache_miss_different_args(self):
        """不同参数导致缓存未命中"""
        call_count = [0]

        @cached(ttl=10)
        def func(x):
            call_count[0] += 1
            return x * 2

        func(1)
        func(2)
        self.assertEqual(call_count[0], 2)

    def test_cache_disabled(self):
        """禁用缓存"""
        call_count = [0]

        @cached(ttl=10, enabled=False)
        def func(x):
            call_count[0] += 1
            return x

        func(1)
        func(1)
        self.assertEqual(call_count[0], 2)

    def test_custom_key_func(self):
        """自定义 key 函数"""
        @cached(ttl=10, key_func=lambda f, args, kwargs: f"custom:{args[0]}")
        def func(x):
            return x * 2

        result = func(5)
        # 验证自定义 key 生效
        cached_result = cache_get("custom:5")
        self.assertEqual(cached_result, 10)

    def test_generator_not_cached(self):
        """生成器不被缓存"""
        @cached(ttl=10)
        def gen_func(n):
            for i in range(n):
                yield i

        # 生成器每次都应执行
        gen1 = gen_func(3)
        gen2 = gen_func(3)

        self.assertEqual(list(gen1), [0, 1, 2])
        self.assertEqual(list(gen2), [0, 1, 2])


class TestCacheFunctions(unittest.TestCase):
    """缓存函数测试"""

    def setUp(self):
        cache_clear()

    def test_manual_set_get(self):
        """手动读写"""
        cache_set("manual_key", {"data": 123}, ttl=10)
        result = cache_get("manual_key")
        self.assertEqual(result, {"data": 123})

    def test_manual_delete(self):
        """手动删除"""
        cache_set("del_key", "value")
        cache_delete("del_key")
        result = cache_get("del_key")
        self.assertIsNone(result)

    def test_stats_after_operations(self):
        """操作后统计"""
        cache_set("k1", "v1")
        cache_get("k1")
        cache_get("missing")

        stats = cache_stats()
        self.assertIn("memory", stats)
        self.assertIn("redis", stats)


class TestTTLBoundary(unittest.TestCase):
    """TTL 边界测试"""

    def setUp(self):
        cache_clear()

    def test_ttl_boundary_exact(self):
        """TTL 边界精确测试"""
        cache = _MemoryCache()
        cache.set("key", "value", ttl=1)

        # 刚好在边界前
        time.sleep(0.9)
        self.assertIsNotNone(cache.get("key"))

        # 边界后
        time.sleep(0.2)
        self.assertIsNone(cache.get("key"))

    def test_ttl_very_short(self):
        """极短 TTL"""
        cache = _MemoryCache()
        cache.set("key", "value", ttl=0.1)
        time.sleep(0.15)
        self.assertIsNone(cache.get("key"))

    def test_ttl_very_long(self):
        """极长 TTL"""
        cache = _MemoryCache()
        cache.set("key", "value", ttl=86400)  # 24小时
        self.assertEqual(cache.get("key"), "value")


class TestCacheKeyGeneration(unittest.TestCase):
    """缓存 key 生成测试"""

    def setUp(self):
        cache_clear()

    def test_same_args_same_key(self):
        """相同参数生成相同 key"""
        call_count = [0]

        @cached(ttl=10)
        def func(a, b, c=None):
            call_count[0] += 1
            return a + b

        func(1, 2, c=3)
        func(1, 2, c=3)
        self.assertEqual(call_count[0], 1)

    def test_kwargs_order_independent(self):
        """kwargs 顺序无关"""
        call_count = [0]

        @cached(ttl=10)
        def func(**kwargs):
            call_count[0] += 1
            return sum(kwargs.values())

        func(a=1, b=2)
        func(b=2, a=1)
        self.assertEqual(call_count[0], 1)


def main():
    print("=== 缓存层测试（增强版） ===")
    unittest.main(verbosity=2)


if __name__ == "__main__":
    main()
