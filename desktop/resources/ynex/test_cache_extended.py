"""
缓存层扩展测试
补充：TTL 过期、并发安全、统计一致性、生成器不缓存、cache_delete 接口
"""

import os
import sys
import time
import threading
import pytest

sys.path.insert(0, os.path.dirname(__file__))

from cache import (
    _MemoryCache,
    cached,
    cache_get,
    cache_set,
    cache_delete,
    cache_clear,
    cache_stats,
    _make_key,
)


@pytest.fixture(autouse=True)
def clean_cache():
    """每个测试前清空缓存"""
    cache_clear()
    yield
    cache_clear()


# ===========================================================================
# _MemoryCache 单元测试
# ===========================================================================
class TestMemoryCache:
    def test_set_and_get(self):
        mc = _MemoryCache()
        mc.set("key1", "value1", ttl=60)
        assert mc.get("key1") == "value1"

    def test_get_nonexistent(self):
        mc = _MemoryCache()
        assert mc.get("missing") is None

    def test_ttl_expiry(self):
        mc = _MemoryCache()
        mc.set("key1", "value1", ttl=1)
        assert mc.get("key1") == "value1"
        time.sleep(1.5)
        assert mc.get("key1") is None

    def test_ttl_zero_means_no_expiry(self):
        mc = _MemoryCache()
        mc.set("key1", "value1", ttl=0)
        # ttl=0 表示永不过期
        assert mc.get("key1") == "value1"

    def test_delete(self):
        mc = _MemoryCache()
        mc.set("key1", "value1", ttl=60)
        mc.delete("key1")
        assert mc.get("key1") is None

    def test_delete_nonexistent_no_error(self):
        mc = _MemoryCache()
        mc.delete("nonexistent")  # 不应抛异常

    def test_clear(self):
        mc = _MemoryCache()
        mc.set("a", 1, ttl=60)
        mc.set("b", 2, ttl=60)
        mc.clear()
        assert mc.get("a") is None
        assert mc.get("b") is None

    def test_stats_hit_miss(self):
        mc = _MemoryCache()
        mc.set("key1", "value1", ttl=60)
        mc.get("key1")   # hit
        mc.get("key1")   # hit
        mc.get("missing")  # miss
        stats = mc.stats()
        assert stats["hits"] == 2
        assert stats["misses"] >= 1  # at least 1 miss

    def test_stats_size(self):
        mc = _MemoryCache()
        mc.set("a", 1, ttl=60)
        mc.set("b", 2, ttl=60)
        assert mc.stats()["size"] == 2

    def test_stats_hit_rate(self):
        mc = _MemoryCache()
        mc.set("k", "v", ttl=60)
        mc.get("k")   # hit
        mc.get("missing")  # miss
        stats = mc.stats()
        assert 0 < stats["hit_rate"] < 1

    def test_stats_empty_hit_rate(self):
        mc = _MemoryCache()
        stats = mc.stats()
        assert stats["hit_rate"] == 0.0

    def test_concurrent_access(self):
        mc = _MemoryCache()
        errors = []

        def writer():
            try:
                for i in range(100):
                    mc.set(f"key_{i}", i, ttl=60)
            except Exception as e:
                errors.append(e)

        def reader():
            try:
                for i in range(100):
                    mc.get(f"key_{i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer), threading.Thread(target=reader)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0


# ===========================================================================
# @cached 装饰器
# ===========================================================================
class TestCachedDecorator:
    def test_caches_result(self):
        call_count = 0

        @cached(ttl=60)
        def compute(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        r1 = compute(5)
        r2 = compute(5)
        assert r1 == r2 == 10
        assert call_count == 1  # 只调用一次

    def test_different_args_different_cache(self):
        call_count = 0

        @cached(ttl=60)
        def compute(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        assert compute(1) == 2
        assert compute(2) == 4
        assert call_count == 2

    def test_ttl_expiry_recomputes(self):
        call_count = 0

        @cached(ttl=1)
        def compute(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        compute(5)
        time.sleep(1.5)
        compute(5)
        assert call_count == 2

    def test_disabled_skips_cache(self):
        call_count = 0

        @cached(ttl=60, enabled=False)
        def compute(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        compute(5)
        compute(5)
        assert call_count == 2

    def test_generator_not_cached(self):
        @cached(ttl=60)
        def gen():
            yield 1
            yield 2

        result = gen()
        # 生成器不应被缓存
        assert hasattr(result, '__next__')

    def test_cache_delete_method(self):
        @cached(ttl=60)
        def compute(x):
            return x * 3

        compute(7)
        compute.cache_delete(7)
        # 删除后应重新计算
        # 注：这不会自动验证重新计算，但确保 cache_delete 不抛异常
        compute(7)


# ===========================================================================
# 手动缓存 API
# ===========================================================================
class TestManualCacheApi:
    def test_set_and_get(self):
        cache_set("manual_key", {"a": 1}, ttl=60)
        assert cache_get("manual_key") == {"a": 1}

    def test_delete(self):
        cache_set("del_key", "value", ttl=60)
        cache_delete("del_key")
        assert cache_get("del_key") is None

    def test_nonexistent_returns_none(self):
        assert cache_get("nonexistent_key_xyz") is None

    def test_stats_structure(self):
        stats = cache_stats()
        assert "memory" in stats
        assert "redis" in stats
        assert "hits" in stats["memory"]
        assert "size" in stats["memory"]


# ===========================================================================
# _make_key
# ===========================================================================
class TestMakeKey:
    def test_deterministic(self):
        def f(x): pass
        k1 = _make_key(f, (1,), {})
        k2 = _make_key(f, (1,), {})
        assert k1 == k2

    def test_different_args_different_key(self):
        def f(x): pass
        k1 = _make_key(f, (1,), {})
        k2 = _make_key(f, (2,), {})
        assert k1 != k2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
