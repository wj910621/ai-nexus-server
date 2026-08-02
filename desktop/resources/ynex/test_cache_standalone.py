"""
缓存层独立测试
不依赖项目导入，直接测试核心缓存逻辑
"""

import time
import threading
import hashlib
import functools
from typing import Any, Optional, Callable


class _MemoryCache:
    """线程安全的内存缓存"""

    def __init__(self):
        self._store: dict = {}
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            item = self._store.get(key)
            if item is None:
                self._misses += 1
                return None
            expiry, value = item
            if expiry > 0 and time.time() > expiry:
                del self._store[key]
                self._misses += 1
                return None
            self._hits += 1
            return value

    def set(self, key: str, value: Any, ttl: int = 300):
        with self._lock:
            expiry = time.time() + ttl if ttl > 0 else 0
            self._store[key] = (expiry, value)

    def delete(self, key: str):
        with self._lock:
            self._store.pop(key, None)

    def clear(self):
        with self._lock:
            self._store.clear()

    def stats(self) -> dict:
        with self._lock:
            total = self._hits + self._misses
            return {
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": round(self._hits / total, 4) if total else 0.0,
                "size": len(self._store),
            }


_memory_cache = _MemoryCache()


def _make_key(func: Callable, args: tuple, kwargs: dict) -> str:
    """根据函数名和参数生成缓存 key"""
    try:
        key_data = f"{func.__module__}.{func.__qualname__}:{args}:{sorted(kwargs.items())}"
        return hashlib.md5(key_data.encode("utf-8")).hexdigest()
    except Exception:
        return hashlib.md5(str(id(func)).encode()).hexdigest()


def cached(ttl: int = 300, key_func: Callable = None, enabled: bool = True):
    """缓存装饰器"""
    def decorator(func: Callable) -> Callable:
        if not enabled:
            return func

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = key_func(func, args, kwargs) if key_func else _make_key(func, args, kwargs)

            value = _memory_cache.get(cache_key)
            if value is not None:
                return value

            result = func(*args, **kwargs)

            if not isinstance(result, type((x for x in ()))):
                _memory_cache.set(cache_key, result, ttl=ttl)

            return result

        wrapper.cache_delete = lambda *a, **kw: _memory_cache.delete(
            key_func(func, a, kw) if key_func else _make_key(func, a, kw)
        )
        wrapper.cache_clear = lambda: None
        return wrapper
    return decorator


def cache_get(key: str) -> Optional[Any]:
    """手动读取缓存"""
    return _memory_cache.get(key)


def cache_set(key: str, value: Any, ttl: int = 300):
    """手动写入缓存"""
    _memory_cache.set(key, value, ttl=ttl)


def cache_delete(key: str):
    """手动删除缓存"""
    _memory_cache.delete(key)


def cache_clear():
    """清空所有缓存"""
    _memory_cache.clear()


def cache_stats() -> dict:
    """获取缓存统计"""
    return {"memory": _memory_cache.stats()}


# ============ 测试用例 ============

def test_memory_cache_basic():
    """测试内存缓存基础功能"""
    print("\n=== 测试内存缓存基础 ===")

    cache = _MemoryCache()

    cache.set("key1", "value1", ttl=10)
    assert cache.get("key1") == "value1"

    cache.set("key1", "value1_updated", ttl=10)
    assert cache.get("key1") == "value1_updated"

    cache.delete("key1")
    assert cache.get("key1") is None

    stats = cache.stats()
    assert stats['hits'] >= 1
    assert stats['misses'] >= 1

    print("✅ 内存缓存基础功能正确")


def test_cache_expiration():
    """测试缓存过期机制"""
    print("\n=== 测试缓存过期 ===")

    cache = _MemoryCache()

    cache.set("expire_key", "value", ttl=1)
    assert cache.get("expire_key") == "value"

    time.sleep(1.1)
    assert cache.get("expire_key") is None

    cache.set("permanent", "value", ttl=0)
    time.sleep(0.5)
    assert cache.get("permanent") == "value"

    print("✅ 缓存过期机制正确")


def test_decorator_caching():
    """测试装饰器缓存"""
    print("\n=== 测试装饰器缓存 ===")

    call_count = [0]

    @cached(ttl=2)
    def expensive_func(x, y):
        call_count[0] += 1
        time.sleep(0.05)
        return x * y

    t0 = time.time()
    r1 = expensive_func(3, 4)
    t1 = time.time()
    assert r1 == 12
    assert call_count[0] == 1

    t2 = time.time()
    r2 = expensive_func(3, 4)
    t3 = time.time()
    assert r2 == 12
    assert call_count[0] == 1
    assert t3 - t2 < 0.01

    r3 = expensive_func(3, 5)
    assert r3 == 15
    assert call_count[0] == 2

    print(f"✅ 装饰器缓存正确（调用 {call_count[0]} 次）")


def test_cache_statistics():
    """测试缓存统计"""
    print("\n=== 测试缓存统计 ===")

    cache_clear()

    cache_set("stat_key1", "value1", ttl=10)
    cache_set("stat_key2", "value2", ttl=10)

    cache_get("stat_key1")
    cache_get("stat_key2")
    cache_get("nonexistent_key")

    stats = cache_stats()
    assert stats['memory']['hits'] >= 2
    assert stats['memory']['misses'] >= 1

    print(f"✅ 缓存统计正确（hits={stats['memory']['hits']}, misses={stats['memory']['misses']}）")


def test_concurrent_cache_access():
    """测试并发缓存访问"""
    print("\n=== 测试并发缓存访问 ===")

    cache = _MemoryCache()
    errors = []

    def writer(thread_id):
        try:
            for i in range(100):
                cache.set(f"key_{thread_id}_{i}", f"value_{i}", ttl=10)
        except Exception as e:
            errors.append(f"Writer {thread_id}: {e}")

    def reader(thread_id):
        try:
            for i in range(100):
                cache.get(f"key_{thread_id}_{i}")
        except Exception as e:
            errors.append(f"Reader {thread_id}: {e}")

    threads = []
    for i in range(5):
        threads.append(threading.Thread(target=writer, args=(i,)))
        threads.append(threading.Thread(target=reader, args=(i,)))

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0, f"并发错误: {errors}"

    print(f"✅ 并发访问安全（执行 {len(threads)} 线程）")


def test_manual_cache_operations():
    """测试手动缓存操作"""
    print("\n=== 测试手动缓存操作 ===")

    cache_clear()

    complex_data = {
        "name": "测试",
        "values": [1, 2, 3],
        "nested": {"key": "value"}
    }
    cache_set("complex_key", complex_data, ttl=10)

    result = cache_get("complex_key")
    assert result == complex_data

    cache_set("complex_key", {"updated": True}, ttl=10)
    assert cache_get("complex_key") == {"updated": True}

    cache_delete("complex_key")
    assert cache_get("complex_key") is None

    print("✅ 手动缓存操作正确")


def test_cache_clear():
    """测试缓存清空"""
    print("\n=== 测试缓存清空 ===")

    cache = _MemoryCache()

    for i in range(10):
        cache.set(f"key_{i}", f"value_{i}", ttl=10)

    stats_before = cache.stats()
    assert stats_before['size'] == 10

    cache.clear()

    stats_after = cache.stats()
    assert stats_after['size'] == 0

    for i in range(10):
        assert cache.get(f"key_{i}") is None

    print("✅ 缓存清空正确")


def test_key_generation():
    """测试缓存 Key 生成"""
    print("\n=== 测试 Key 生成 ===")

    def sample_func(a, b, c=None):
        pass

    key1 = _make_key(sample_func, (1, 2), {"c": 3})
    key2 = _make_key(sample_func, (1, 2), {"c": 3})
    assert key1 == key2

    key3 = _make_key(sample_func, (1, 3), {"c": 3})
    assert key1 != key3

    assert len(key1) == 32

    print(f"✅ Key 生成正确（{key1}）")


def test_disabled_caching():
    """测试禁用缓存"""
    print("\n=== 测试禁用缓存 ===")

    call_count = [0]

    @cached(ttl=10, enabled=False)
    def no_cache_func(x):
        call_count[0] += 1
        return x * 2

    r1 = no_cache_func(5)
    r2 = no_cache_func(5)

    assert r1 == r2 == 10
    assert call_count[0] == 2

    print("✅ 禁用缓存正确")


def test_generator_not_cached():
    """测试生成器不被缓存"""
    print("\n=== 测试生成器不缓存 ===")

    call_count = [0]

    @cached(ttl=10)
    def generator_func():
        call_count[0] += 1
        for i in range(3):
            yield i

    result1 = list(generator_func())
    result2 = list(generator_func())

    assert result1 == result2 == [0, 1, 2]
    assert call_count[0] == 2

    print("✅ 生成器不缓存正确")


def test_large_data_caching():
    """测试大数据缓存"""
    print("\n=== 测试大数据缓存 ===")

    large_data = {"data": list(range(10000))}

    cache_set("large_key", large_data, ttl=10)
    result = cache_get("large_key")

    assert result == large_data
    assert len(result["data"]) == 10000

    print(f"✅ 大数据缓存正确（{len(result['data'])} 项）")


def main():
    print("=" * 60)
    print("  缓存层独立测试")
    print("=" * 60)

    test_memory_cache_basic()
    test_cache_expiration()
    test_decorator_caching()
    test_cache_statistics()
    test_concurrent_cache_access()
    test_manual_cache_operations()
    test_cache_clear()
    test_key_generation()
    test_disabled_caching()
    test_generator_not_cached()
    test_large_data_caching()

    print("\n" + "=" * 60)
    print("🎉 所有缓存测试通过")
    print("=" * 60)


if __name__ == "__main__":
    main()