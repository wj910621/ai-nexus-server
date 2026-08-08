"""
cache.py 的 pytest 测试（升级自 test_cache.py 脚本式测试）
"""

import sys
import os
import time
import threading

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ""))

from cache import (
    _MemoryCache,
    cached,
    cache_get,
    cache_set,
    cache_delete,
    cache_clear,
    cache_stats,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clean_cache():
    """每个测试前后清空缓存，确保隔离"""
    cache_clear()
    yield
    cache_clear()


@pytest.fixture
def mem_cache():
    """提供独立的 _MemoryCache 实例"""
    return _MemoryCache()


# ---------------------------------------------------------------------------
# _MemoryCache 类测试
# ---------------------------------------------------------------------------

class TestMemoryCacheBasic:
    """_MemoryCache 基本 get/set 操作"""

    def test_set_and_get(self, mem_cache):
        mem_cache.set("k1", "v1", ttl=60)
        assert mem_cache.get("k1") == "v1"

    def test_get_missing_key_returns_none(self, mem_cache):
        assert mem_cache.get("nonexistent") is None

    def test_set_overwrite(self, mem_cache):
        mem_cache.set("k1", "v1", ttl=60)
        mem_cache.set("k1", "v2", ttl=60)
        assert mem_cache.get("k1") == "v2"

    def test_set_various_types(self, mem_cache):
        mem_cache.set("int_key", 42, ttl=60)
        mem_cache.set("dict_key", {"a": 1}, ttl=60)
        mem_cache.set("list_key", [1, 2, 3], ttl=60)
        assert mem_cache.get("int_key") == 42
        assert mem_cache.get("dict_key") == {"a": 1}
        assert mem_cache.get("list_key") == [1, 2, 3]


class TestMemoryCacheTTL:
    """_MemoryCache TTL 过期"""

    def test_value_expires_after_ttl(self, mem_cache):
        mem_cache.set("short", "data", ttl=1)
        assert mem_cache.get("short") == "data"
        time.sleep(1.1)
        assert mem_cache.get("short") is None

    def test_ttl_zero_means_no_expiry(self, mem_cache):
        mem_cache.set("permanent", "data", ttl=0)
        # ttl=0 表示永不过期
        time.sleep(0.2)
        assert mem_cache.get("permanent") == "data"


class TestMemoryCacheDelete:
    """_MemoryCache delete 操作"""

    def test_delete_existing_key(self, mem_cache):
        mem_cache.set("k1", "v1", ttl=60)
        mem_cache.delete("k1")
        assert mem_cache.get("k1") is None

    def test_delete_nonexistent_key_no_error(self, mem_cache):
        mem_cache.delete("nonexistent")  # 不应抛异常


class TestMemoryCacheClear:
    """_MemoryCache clear 操作"""

    def test_clear_removes_all_keys(self, mem_cache):
        for i in range(5):
            mem_cache.set(f"k{i}", f"v{i}", ttl=60)
        mem_cache.clear()
        for i in range(5):
            assert mem_cache.get(f"k{i}") is None


class TestMemoryCacheStats:
    """_MemoryCache stats 统计"""

    def test_stats_initial(self, mem_cache):
        s = mem_cache.stats()
        assert s["hits"] == 0
        assert s["misses"] == 0
        assert s["hit_rate"] == 0.0
        assert s["size"] == 0

    def test_stats_hits_and_misses(self, mem_cache):
        mem_cache.set("k1", "v1", ttl=60)
        mem_cache.get("k1")   # hit
        mem_cache.get("k1")   # hit
        mem_cache.get("x")    # miss
        s = mem_cache.stats()
        assert s["hits"] == 2
        assert s["misses"] == 1
        assert s["hit_rate"] == pytest.approx(2 / 3, abs=0.01)

    def test_stats_size(self, mem_cache):
        mem_cache.set("k1", "v1", ttl=60)
        mem_cache.set("k2", "v2", ttl=60)
        s = mem_cache.stats()
        assert s["size"] == 2


class TestMemoryCacheThreadSafety:
    """_MemoryCache 线程安全"""

    def test_concurrent_set_and_get(self, mem_cache):
        errors = []

        def writer(n):
            try:
                for i in range(100):
                    mem_cache.set(f"key_{n}_{i}", i, ttl=60)
            except Exception as e:
                errors.append(e)

        def reader(n):
            try:
                for i in range(100):
                    mem_cache.get(f"key_{n}_{i}")
            except Exception as e:
                errors.append(e)

        threads = []
        for n in range(5):
            threads.append(threading.Thread(target=writer, args=(n,)))
            threads.append(threading.Thread(target=reader, args=(n,)))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"线程安全测试出错: {errors}"


# ---------------------------------------------------------------------------
# @cached 装饰器测试
# ---------------------------------------------------------------------------

class TestCachedDecorator:
    """@cached 装饰器"""

    def test_caches_result_on_second_call(self):
        call_count = 0

        @cached(ttl=60)
        def compute(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        r1 = compute(5)
        r2 = compute(5)
        assert r1 == r2 == 10
        assert call_count == 1  # 只执行了一次

    def test_second_call_is_faster(self):
        @cached(ttl=60)
        def slow_fn(x):
            time.sleep(0.1)
            return x

        t0 = time.time()
        slow_fn(1)
        t1 = time.time()
        slow_fn(1)
        t2 = time.time()

        first_duration = t1 - t0
        second_duration = t2 - t1
        assert second_duration < first_duration
        assert second_duration < 0.05  # 缓存命中应非常快

    def test_respects_ttl(self):
        call_count = 0

        @cached(ttl=1)
        def ttl_fn(x):
            nonlocal call_count
            call_count += 1
            return x

        ttl_fn(42)
        assert call_count == 1

        time.sleep(1.1)
        ttl_fn(42)
        assert call_count == 2  # TTL 过期后重新执行

    def test_disabled_returns_original_function(self):
        @cached(ttl=60, enabled=False)
        def disabled_fn(x):
            return x * 3

        # enabled=False 时返回原函数，不是 wrapper
        assert disabled_fn(2) == 6
        # 连续调用也应每次执行
        assert disabled_fn(2) == 6
        # 没有缓存相关属性
        assert not hasattr(disabled_fn, "cache_delete")

    def test_does_not_cache_generators(self):
        call_count = 0

        @cached(ttl=60)
        def gen_fn():
            nonlocal call_count
            call_count += 1
            for i in range(3):
                yield i

        # 第一次调用
        list(gen_fn())
        assert call_count == 1

        # 第二次调用——生成器不被缓存，应再次执行
        list(gen_fn())
        assert call_count == 2


# ---------------------------------------------------------------------------
# 手动缓存函数测试
# ---------------------------------------------------------------------------

class TestManualCacheFunctions:
    """cache_get / cache_set / cache_delete / cache_clear / cache_stats"""

    def test_cache_set_and_get(self):
        cache_set("manual_k", "manual_v", ttl=60)
        assert cache_get("manual_k") == "manual_v"

    def test_cache_get_returns_none_for_missing(self):
        assert cache_get("nonexistent_manual") is None

    def test_cache_delete(self):
        cache_set("del_k", "del_v", ttl=60)
        cache_delete("del_k")
        assert cache_get("del_k") is None

    def test_cache_clear(self):
        cache_set("ck1", "cv1", ttl=60)
        cache_set("ck2", "cv2", ttl=60)
        cache_clear()
        assert cache_get("ck1") is None
        assert cache_get("ck2") is None

    def test_cache_stats(self):
        cache_set("sk", "sv", ttl=60)
        cache_get("sk")   # hit
        cache_get("nope") # miss
        stats = cache_stats()
        assert "memory" in stats
        assert "redis" in stats
        # memory 至少有 1 次 hit
        assert stats["memory"]["hits"] >= 1
