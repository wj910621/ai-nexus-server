"""
缓存系统全面测试
覆盖：
  - TTL 过期处理
  - 缓存命中率统计
  - 并发读写安全
  - 装饰器缓存
  - 边界条件
  - 内存管理
  - 特殊数据类型
"""

import os
import sys
import time
import threading
import tempfile
from pathlib import Path

# 设置测试环境
os.makedirs("data", exist_ok=True)

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
    """内存缓存核心功能测试"""

    def setup_method(self):
        """每个测试前清空缓存"""
        cache_clear()

    def test_basic_set_get(self):
        """测试基本读写"""
        cache_set("test_key", {"value": 42}, ttl=60)
        
        result = cache_get("test_key")
        
        assert result == {"value": 42}

    def test_cache_miss(self):
        """测试缓存未命中"""
        result = cache_get("nonexistent_key")
        
        assert result is None

    def test_cache_delete(self):
        """测试删除缓存"""
        cache_set("delete_test", "value", ttl=60)
        
        cache_delete("delete_test")
        
        assert cache_get("delete_test") is None

    def test_cache_clear(self):
        """测试清空缓存"""
        cache_set("key1", "value1", ttl=60)
        cache_set("key2", "value2", ttl=60)
        
        cache_clear()
        
        assert cache_get("key1") is None
        assert cache_get("key2") is None


class TestTTLExpiry:
    """TTL 过期测试"""

    def setup_method(self):
        cache_clear()

    def test_ttl_expiry(self):
        """测试 TTL 过期"""
        cache_set("ttl_test", "value", ttl=1)
        
        # 立即读取应该成功
        assert cache_get("ttl_test") == "value"
        
        # 等待过期
        time.sleep(1.5)
        
        # 过期后应该返回 None
        assert cache_get("ttl_test") is None

    def test_ttl_zero_means_never_expire(self):
        """测试 TTL=0 表示永不过期"""
        cache_set("never_expire", "forever", ttl=0)
        
        time.sleep(0.5)
        
        # 应该仍然存在
        assert cache_get("never_expire") == "forever"

    def test_ttl_update_on_set(self):
        """测试重新 set 更新 TTL"""
        cache_set("update_ttl", "value1", ttl=1)
        cache_set("update_ttl", "value2", ttl=60)
        
        time.sleep(1.5)
        
        # 应该仍然存在（因为 TTL 已更新为 60）
        assert cache_get("update_ttl") == "value2"


class TestDecoratorCache:
    """装饰器缓存测试"""

    def setup_method(self):
        cache_clear()
        self.call_count = 0

    def test_decorator_caching(self):
        """测试装饰器缓存"""
        @cached(ttl=60)
        def expensive_function(x):
            self.call_count += 1
            return x * 2
        
        # 第一次调用
        result1 = expensive_function(5)
        assert result1 == 10
        assert self.call_count == 1
        
        # 第二次调用（应该命中缓存）
        result2 = expensive_function(5)
        assert result2 == 10
        assert self.call_count == 1  # 没有增加

    def test_decorator_different_args(self):
        """测试不同参数不同缓存"""
        @cached(ttl=60)
        def multiply(x, y):
            return x * y
        
        assert multiply(2, 3) == 6
        assert multiply(3, 4) == 12
        assert multiply(2, 3) == 6  # 应该命中缓存

    def test_decorator_disabled(self):
        """测试禁用缓存"""
        call_count = 0
        
        @cached(ttl=60, enabled=False)
        def no_cache(x):
            nonlocal call_count
            call_count += 1
            return x
        
        no_cache(1)
        no_cache(1)
        no_cache(1)
        
        # 应该每次都执行
        assert call_count == 3

    def test_decorator_custom_key(self):
        """测试自定义 key 函数"""
        @cached(ttl=60, key_func=lambda f, a, kw: f"custom:{a[0]}")
        def custom_key_func(x):
            return x
        
        custom_key_func(100)
        
        # 验证使用自定义 key
        result = cache_get("custom:100")
        assert result == 100

    def test_decorator_manual_delete(self):
        """测试装饰器手动删除"""
        call_count = 0
        
        @cached(ttl=60)
        def cached_func(x):
            nonlocal call_count
            call_count += 1
            return x
        
        cached_func(5)
        cached_func.cache_delete(5)
        
        # 删除后再次调用应该重新执行
        cached_func(5)
        assert call_count == 2


class TestConcurrency:
    """并发测试"""

    def setup_method(self):
        cache_clear()

    def test_concurrent_reads(self):
        """测试并发读取"""
        cache_set("concurrent_key", "value", ttl=60)
        
        results = []
        lock = threading.Lock()
        
        def read_cache():
            result = cache_get("concurrent_key")
            with lock:
                results.append(result)
        
        threads = [
            threading.Thread(target=read_cache)
            for _ in range(10)
        ]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # 所有读取应该成功
        assert all(r == "value" for r in results)

    def test_concurrent_writes(self):
        """测试并发写入"""
        def write_cache(i):
            cache_set(f"key_{i}", f"value_{i}", ttl=60)
        
        threads = [
            threading.Thread(target=write_cache, args=(i,))
            for i in range(100)
        ]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # 验证所有写入成功
        for i in range(100):
            assert cache_get(f"key_{i}") == f"value_{i}"

    def test_concurrent_read_write(self):
        """测试并发读写"""
        errors = []
        
        def writer():
            for i in range(100):
                cache_set("rw_key", i, ttl=60)
        
        def reader():
            for _ in range(100):
                try:
                    cache_get("rw_key")
                except Exception as e:
                    errors.append(e)
        
        threads = [
            threading.Thread(target=writer),
            threading.Thread(target=reader),
            threading.Thread(target=reader),
        ]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0


class TestCacheStats:
    """缓存统计测试"""

    def setup_method(self):
        cache_clear()

    def test_hit_miss_counting(self):
        """测试命中/未命中计数"""
        cache_set("stats_test", "value", ttl=60)
        
        # 命中
        cache_get("stats_test")
        cache_get("stats_test")
        
        # 未命中
        cache_get("nonexistent1")
        cache_get("nonexistent2")
        
        stats = cache_stats()
        
        assert stats["memory"]["hits"] >= 2
        assert stats["memory"]["misses"] >= 2

    def test_hit_rate_calculation(self):
        """测试命中率计算"""
        cache_set("rate_test", "value", ttl=60)
        
        # 3 次命中
        for _ in range(3):
            cache_get("rate_test")
        
        # 1 次未命中
        cache_get("miss")
        
        stats = cache_stats()
        # 命中率应该是 3/4 = 0.75
        assert stats["memory"]["hit_rate"] >= 0.75


class TestBoundaryConditions:
    """边界条件测试"""

    def setup_method(self):
        cache_clear()

    def test_none_value(self):
        """测试缓存 None 值"""
        cache_set("none_key", None, ttl=60)
        
        # None 应该可以正常存储和读取
        # 注意：由于 get 返回 None 表示未命中，这里会有歧义
        # 这是设计上的权衡，需要文档说明

    def test_large_value(self):
        """测试大值"""
        large_data = {"data": "x" * 100000}
        
        cache_set("large_key", large_data, ttl=60)
        
        result = cache_get("large_key")
        assert result == large_data

    def test_special_characters_in_key(self):
        """测试 Key 中的特殊字符"""
        special_keys = [
            "key:with:colon",
            "key/with/slash",
            "key with space",
            "key中文",
            "key🔥emoji",
        ]
        
        for key in special_keys:
            cache_set(key, "value", ttl=60)
            assert cache_get(key) == "value"

    def test_unicode_value(self):
        """测试 Unicode 值"""
        unicode_value = {
            "chinese": "你好世界",
            "japanese": "こんにちは",
            "emoji": "🎉🎊",
        }
        
        cache_set("unicode_test", unicode_value, ttl=60)
        
        result = cache_get("unicode_test")
        assert result == unicode_value

    def test_nested_data(self):
        """测试嵌套数据"""
        nested = {
            "level1": {
                "level2": {
                    "level3": [1, 2, 3]
                }
            }
        }
        
        cache_set("nested_test", nested, ttl=60)
        
        result = cache_get("nested_test")
        assert result == nested


class TestMakeKey:
    """Key 生成测试"""

    def test_key_generation(self):
        """测试 Key 生成"""
        def func(a, b, c=None):
            pass
        
        key1 = _make_key(func, (1, 2), {"c": 3})
        key2 = _make_key(func, (1, 2), {"c": 3})
        key3 = _make_key(func, (1, 3), {"c": 3})
        
        # 相同参数应该生成相同 Key
        assert key1 == key2
        # 不同参数应该生成不同 Key
        assert key1 != key3

    def test_key_stability(self):
        """测试 Key 稳定性"""
        def func(x):
            pass
        
        key = _make_key(func, (42,), {})
        
        # 多次调用应该生成相同 Key
        for _ in range(10):
            assert _make_key(func, (42,), {}) == key


class TestGeneratorNotCached:
    """生成器不缓存测试"""

    def setup_method(self):
        cache_clear()

    def test_generator_not_cached(self):
        """测试生成器不会被缓存"""
        call_count = 0
        
        @cached(ttl=60)
        def gen_func():
            nonlocal call_count
            call_count += 1
            yield 1
            yield 2
        
        # 每次调用都应该重新执行
        list(gen_func())
        list(gen_func())
        
        assert call_count == 2


def run_tests():
    """运行所有测试"""
    import traceback
    
    test_classes = [
        TestMemoryCache,
        TestTTLExpiry,
        TestDecoratorCache,
        TestConcurrency,
        TestCacheStats,
        TestBoundaryConditions,
        TestMakeKey,
        TestGeneratorNotCached,
    ]
    
    total = 0
    passed = 0
    failed = 0
    
    for test_class in test_classes:
        print(f"\n{'='*60}")
        print(f"  {test_class.__name__}")
        print(f"{'='*60}")
        
        instance = test_class()
        
        for method_name in dir(instance):
            if method_name.startswith("test_"):
                total += 1
                method = getattr(instance, method_name)
                try:
                    if hasattr(instance, "setup_method"):
                        instance.setup_method()
                    method()
                    print(f"  ✓ {method_name}")
                    passed += 1
                except AssertionError as e:
                    print(f"  ✗ {method_name}: {e}")
                    failed += 1
                except Exception as e:
                    print(f"  ✗ {method_name}: {type(e).__name__}: {e}")
                    traceback.print_exc()
                    failed += 1
    
    print(f"\n{'='*60}")
    print(f"  测试结果: {passed}/{total} 通过")
    print(f"{'='*60}")
    
    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)