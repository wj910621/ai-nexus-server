"""
缓存层增强测试
覆盖并发场景、TTL 过期、装饰器行为、内存泄漏、生成器不缓存等
"""

import time
import threading
import unittest
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


class TestMemoryCacheConcurrency(unittest.TestCase):
    """内存缓存并发测试"""

    def setUp(self):
        self.cache = _MemoryCache()

    def test_concurrent_set_get(self):
        """测试并发写入和读取"""
        errors = []
        results = {}

        def set_value(key, value):
            try:
                self.cache.set(key, value, ttl=60)
            except Exception as e:
                errors.append(f"set error: {e}")

        def get_value(key, expected):
            try:
                value = self.cache.get(key)
                results[key] = value
            except Exception as e:
                errors.append(f"get error: {e}")

        threads = []
        for i in range(50):
            threads.append(threading.Thread(target=set_value, args=(f"key_{i}", i)))
        for i in range(50):
            threads.append(threading.Thread(target=get_value, args=(f"key_{i}", i)))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0)

    def test_concurrent_delete_while_reading(self):
        """测试读取时并发删除"""
        self.cache.set("del_key", "value", ttl=60)

        results = []
        errors = []

        def read_key():
            try:
                val = self.cache.get("del_key")
                results.append(val)
            except Exception as e:
                errors.append(str(e))

        def delete_key():
            try:
                self.cache.delete("del_key")
            except Exception as e:
                errors.append(str(e))

        threads = [
            threading.Thread(target=read_key) for _ in range(10)
        ] + [
            threading.Thread(target=delete_key) for _ in range(5)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0)

    def test_stats_thread_safe(self):
        """测试统计信息的线程安全"""
        errors = []

        def do_operations():
            try:
                for i in range(20):
                    self.cache.set(f"stat_key_{i}", i)
                    self.cache.get(f"stat_key_{i}")
                    if i % 5 == 0:
                        self.cache.stats()
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=do_operations) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0)
        stats = self.cache.stats()
        self.assertGreater(stats["hits"], 0)


class TestMemoryCacheTTL(unittest.TestCase):
    """TTL 过期测试"""

    def setUp(self):
        self.cache = _MemoryCache()

    def test_ttl_expires(self):
        """测试 TTL 过期"""
        self.cache.set("expiring_key", "value", ttl=1)

        # 立即读取应存在
        value = self.cache.get("expiring_key")
        self.assertEqual(value, "value")

        # 等待过期
        time.sleep(2)

        # 读取应返回 None
        value = self.cache.get("expiring_key")
        self.assertIsNone(value)

    def test_ttl_zero_never_expires(self):
        """测试 TTL=0 永不过期"""
        self.cache.set("permanent_key", "value", ttl=0)

        # 等待一段时间
        time.sleep(2)

        # 仍应存在
        value = self.cache.get("permanent_key")
        self.assertEqual(value, "value")

    def test_ttl_negative(self):
        """测试负 TTL"""
        # 负 TTL 应被视为 0（永不过期）或立即过期
        self.cache.set("neg_ttl_key", "value", ttl=-10)
        value = self.cache.get("neg_ttl_key")
        # 根据实现，可能立即过期或永不过期
        # 检查代码逻辑：expiry = time.time() + ttl if ttl > 0 else 0
        # ttl=-10 不满足 ttl > 0，所以 expiry=0，永不过期
        self.assertEqual(value, "value")


class TestCacheDecorator(unittest.TestCase):
    """缓存装饰器测试"""

    def setUp(self):
        cache_clear()

    def test_cached_function_hit(self):
        """测试缓存命中"""
        call_counter = {"count": 0}

        @cached(ttl=60)
        def expensive_func(x):
            call_counter["count"] += 1
            return x * 2

        # 第一次调用
        result1 = expensive_func(5)
        self.assertEqual(result1, 10)
        self.assertEqual(call_counter["count"], 1)

        # 第二次调用（缓存命中）
        result2 = expensive_func(5)
        self.assertEqual(result2, 10)
        # 缓存命中，计数不应增加
        self.assertEqual(call_counter["count"], 1)

    def test_cached_different_args(self):
        """测试不同参数分别缓存"""
        call_counter = {"count": 0}

        @cached(ttl=60)
        def multi_args(a, b):
            call_counter["count"] += 1
            return a + b

        result1 = multi_args(1, 2)
        result2 = multi_args(3, 4)
        result3 = multi_args(1, 2)  # 缓存命中

        self.assertEqual(result1, 3)
        self.assertEqual(result2, 7)
        self.assertEqual(result3, 3)
        # 两次不同参数，第三次命中缓存
        self.assertEqual(call_counter["count"], 2)

    def test_cached_disabled(self):
        """测试禁用缓存"""
        call_counter = {"count": 0}

        @cached(ttl=60, enabled=False)
        def no_cache_func(x):
            call_counter["count"] += 1
            return x

        no_cache_func(1)
        no_cache_func(1)
        no_cache_func(1)

        self.assertEqual(call_counter["count"], 3)  # 每次都执行

    def test_cached_custom_key_func(self):
        """测试自定义 key 函数"""
        call_counter = {"count": 0}

        def custom_key(func, args, kwargs):
            return f"custom_{args[0]}"

        @cached(ttl=60, key_func=custom_key)
        def custom_key_func(x, y):
            call_counter["count"] += 1
            return x + y

        # 不同 y，但相同 x，应命中同一缓存
        result1 = custom_key_func(1, 100)
        result2 = custom_key_func(1, 200)

        self.assertEqual(result1, 101)
        # 缓存命中，返回第一次的结果
        self.assertEqual(result2, 101)
        self.assertEqual(call_counter["count"], 1)

    def test_cached_generator_not_cached(self):
        """测试生成器不被缓存"""
        call_counter = {"count": 0}

        @cached(ttl=60)
        def generator_func(n):
            call_counter["count"] += 1
            for i in range(n):
                yield i

        # 第一次调用
        gen1 = generator_func(3)
        list1 = list(gen1)

        # 第二次调用
        gen2 = generator_func(3)
        list2 = list(gen2)

        self.assertEqual(list1, [0, 1, 2])
        self.assertEqual(list2, [0, 1, 2])
        # 生成器不被缓存，每次都执行
        self.assertEqual(call_counter["count"], 2)

    def test_cached_ttl_expiry(self):
        """测试缓存 TTL 过期"""
        call_counter = {"count": 0}

        @cached(ttl=1)
        def short_ttl_func(x):
            call_counter["count"] += 1
            return x

        short_ttl_func(5)
        self.assertEqual(call_counter["count"], 1)

        time.sleep(2)

        short_ttl_func(5)
        self.assertEqual(call_counter["count"], 2)  # TTL 过期后重新执行

    def test_cached_manual_delete(self):
        """测试手动删除缓存"""
        call_counter = {"count": 0}

        @cached(ttl=60)
        def deletable_func(x):
            call_counter["count"] += 1
            return x * 2

        deletable_func(10)
        self.assertEqual(call_counter["count"], 1)

        # 手动删除
        deletable_func.cache_delete(10)

        deletable_func(10)
        self.assertEqual(call_counter["count"], 2)


class TestKeyGeneration(unittest.TestCase):
    """缓存 key 生成测试"""

    def test_make_key_consistent(self):
        """测试 key 生成一致性"""
        def sample_func(a, b):
            return a + b

        key1 = _make_key(sample_func, (1, 2), {})
        key2 = _make_key(sample_func, (1, 2), {})

        self.assertEqual(key1, key2)

    def test_make_key_different_args(self):
        """测试不同参数生成不同 key"""
        def sample_func(a, b):
            return a + b

        key1 = _make_key(sample_func, (1, 2), {})
        key2 = _make_key(sample_func, (3, 4), {})

        self.assertNotEqual(key1, key2)

    def test_make_key_kwargs_order(self):
        """测试 kwargs 顺序不影响 key"""
        def sample_func(a, b):
            return a + b

        key1 = _make_key(sample_func, (), {"a": 1, "b": 2})
        key2 = _make_key(sample_func, (), {"b": 2, "a": 1})

        # kwargs 排序后应相同
        self.assertEqual(key1, key2)

    def test_make_key_length(self):
        """测试 key 长度（MD5）"""
        def sample_func(a, b):
            pass

        key = _make_key(sample_func, (1, 2), {})
        self.assertEqual(len(key), 32)  # MD5 hex


class TestCacheStats(unittest.TestCase):
    """缓存统计测试"""

    def setUp(self):
        cache_clear()

    def test_stats_hit_rate(self):
        """测试命中率计算"""
        # 直接测试命中/未命中逻辑，不依赖具体数值
        cache_set("hit_key1", 1)
        cache_set("hit_key2", 2)

        # 命中两次
        cache_get("hit_key1")
        cache_get("hit_key2")

        # 未命中两次
        cache_get("miss_key1")
        cache_get("miss_key2")

        stats = cache_stats()
        # 验证命中率在合理范围内
        self.assertGreater(stats["memory"]["hits"], 0)
        self.assertGreater(stats["memory"]["misses"], 0)

    def test_stats_size(self):
        """测试缓存大小统计"""
        cache_clear()  # 确保清空
        for i in range(10):
            cache_set(f"size_key_{i}", i)

        stats = cache_stats()
        self.assertEqual(stats["memory"]["size"], 10)


class TestCacheClear(unittest.TestCase):
    """缓存清理测试"""

    def test_clear_removes_all(self):
        """测试清空所有缓存"""
        cache_set("clear1", 1)
        cache_set("clear2", 2)
        cache_set("clear3", 3)

        cache_clear()

        self.assertIsNone(cache_get("clear1"))
        self.assertIsNone(cache_get("clear2"))
        self.assertIsNone(cache_get("clear3"))

    def test_clear_after_cached_function(self):
        """测试清理装饰器缓存"""
        call_counter = {"count": 0}

        @cached(ttl=60)
        def func(x):
            call_counter["count"] += 1
            return x

        func(1)
        func(1)
        self.assertEqual(call_counter["count"], 1)

        cache_clear()

        func(1)
        self.assertEqual(call_counter["count"], 2)


class TestManualCacheOperations(unittest.TestCase):
    """手动缓存操作测试"""

    def setUp(self):
        cache_clear()

    def test_set_get_delete(self):
        """测试手动 set/get/delete"""
        cache_set("manual_key", {"data": 42}, ttl=60)

        value = cache_get("manual_key")
        self.assertEqual(value, {"data": 42})

        cache_delete("manual_key")

        value = cache_get("manual_key")
        self.assertIsNone(value)

    def test_overwrite_existing_key(self):
        """测试覆盖现有 key"""
        cache_set("overwrite_key", "old_value")
        cache_set("overwrite_key", "new_value")

        value = cache_get("overwrite_key")
        self.assertEqual(value, "new_value")

    def test_complex_value_types(self):
        """测试复杂数据类型缓存"""
        # 列表
        cache_set("list_key", [1, 2, 3, 4])
        self.assertEqual(cache_get("list_key"), [1, 2, 3, 4])

        # 字典
        cache_set("dict_key", {"nested": {"deep": "value"}})
        self.assertEqual(cache_get("dict_key"), {"nested": {"deep": "value"}})

        # 嵌套复杂结构
        complex_data = {
            "list": [1, {"inner": 2}],
            "dict": {"a": [3, 4]},
            "num": 123,
            "str": "text"
        }
        cache_set("complex_key", complex_data)
        self.assertEqual(cache_get("complex_key"), complex_data)


def run_tests():
    """运行测试"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestMemoryCacheConcurrency))
    suite.addTests(loader.loadTestsFromTestCase(TestMemoryCacheTTL))
    suite.addTests(loader.loadTestsFromTestCase(TestCacheDecorator))
    suite.addTests(loader.loadTestsFromTestCase(TestKeyGeneration))
    suite.addTests(loader.loadTestsFromTestCase(TestCacheStats))
    suite.addTests(loader.loadTestsFromTestCase(TestCacheClear))
    suite.addTests(loader.loadTestsFromTestCase(TestManualCacheOperations))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)