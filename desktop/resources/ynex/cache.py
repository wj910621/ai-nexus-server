"""
统一缓存层
支持内存缓存（默认）和 Redis（可选），用于加速高频调用、降低 API 成本。

使用方式：
    from cache import cached

    @cached(ttl=300)
    def expensive_function(x):
        return x * 2
"""

import os
import hashlib
import time
import threading
import functools
from typing import Any, Optional, Callable

from logger import logger


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


class _RedisCache:
    """可选 Redis 缓存后端"""

    def __init__(self, url: str = None):
        self._url = url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self._client = None
        self._hits = 0
        self._misses = 0
        try:
            import redis
            self._client = redis.from_url(self._url, decode_responses=False)
            self._client.ping()
            logger.info(f"Redis 缓存已连接: {self._url}")
        except Exception as e:
            logger.warning(f"Redis 连接失败，回退到内存缓存: {e}")
            self._client = None

    def _key(self, key: str) -> str:
        return f"ynex:cache:{key}"

    def get(self, key: str) -> Optional[Any]:
        if self._client is None:
            return None
        try:
            import json
            raw = self._client.get(self._key(key))
            if raw is None:
                self._misses += 1
                return None
            self._hits += 1
            return json.loads(raw)
        except Exception as e:
            logger.warning(f"Redis get 失败: {e}")
            return None

    def set(self, key: str, value: Any, ttl: int = 300):
        if self._client is None:
            return
        try:
            import json
            self._client.setex(self._key(key), ttl, json.dumps(value, default=str, ensure_ascii=False))
        except Exception as e:
            logger.warning(f"Redis set 失败: {e}")

    def delete(self, key: str):
        if self._client is None:
            return
        try:
            self._client.delete(self._key(key))
        except Exception as e:
            logger.warning(f"Redis delete 失败: {e}")

    def clear(self):
        if self._client is None:
            return
        try:
            for k in self._client.scan_iter(match="ynex:cache:*"):
                self._client.delete(k)
        except Exception as e:
            logger.warning(f"Redis clear 失败: {e}")

    def stats(self) -> dict:
        total = self._hits + self._misses
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self._hits / total, 4) if total else 0.0,
            "backend": "redis" if self._client else "memory",
        }


# 全局缓存实例：优先 Redis，否则内存
_memory_cache = _MemoryCache()
_redis_cache = _RedisCache()


def _make_key(func: Callable, args: tuple, kwargs: dict) -> str:
    """根据函数名和参数生成缓存 key"""
    try:
        key_data = f"{func.__module__}.{func.__qualname__}:{args}:{sorted(kwargs.items())}"
        return hashlib.md5(key_data.encode("utf-8")).hexdigest()
    except Exception:
        # 某些对象无法序列化时 fallback
        return hashlib.md5(str(id(func)).encode()).hexdigest()


def cached(ttl: int = 300, key_func: Callable = None, enabled: bool = True):
    """
    缓存装饰器。

    参数：
        ttl: 缓存有效期（秒），默认 300
        key_func: 自定义 key 生成函数，签名为 (func, args, kwargs) -> str
        enabled: 是否启用缓存
    """
    def decorator(func: Callable) -> Callable:
        if not enabled:
            return func

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = key_func(func, args, kwargs) if key_func else _make_key(func, args, kwargs)

            # 优先读 Redis
            value = _redis_cache.get(cache_key)
            if value is not None:
                return value

            # 再读内存
            value = _memory_cache.get(cache_key)
            if value is not None:
                return value

            # 执行原函数
            result = func(*args, **kwargs)

            # 写入两级缓存（注意：流式生成器不缓存）
            if not isinstance(result, type((x for x in ()))):
                _memory_cache.set(cache_key, result, ttl=ttl)
                _redis_cache.set(cache_key, result, ttl=ttl)

            return result

        # 暴露手动清理接口
        wrapper.cache_delete = lambda *a, **kw: (
            _memory_cache.delete(key_func(func, a, kw) if key_func else _make_key(func, a, kw)),
            _redis_cache.delete(key_func(func, a, kw) if key_func else _make_key(func, a, kw)),
        )
        wrapper.cache_clear = lambda: None  # 装饰器级别无法精确清理
        return wrapper
    return decorator


def cache_get(key: str) -> Optional[Any]:
    """手动读取缓存"""
    value = _redis_cache.get(key)
    if value is not None:
        return value
    return _memory_cache.get(key)


def cache_set(key: str, value: Any, ttl: int = 300):
    """手动写入缓存"""
    _memory_cache.set(key, value, ttl=ttl)
    _redis_cache.set(key, value, ttl=ttl)


def cache_delete(key: str):
    """手动删除缓存"""
    _memory_cache.delete(key)
    _redis_cache.delete(key)


def cache_clear():
    """清空所有缓存"""
    _memory_cache.clear()
    _redis_cache.clear()


def cache_stats() -> dict:
    """获取缓存统计"""
    return {
        "memory": _memory_cache.stats(),
        "redis": _redis_cache.stats(),
    }
