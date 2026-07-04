"""
Y·NEX性能优化与错误处理模块
提供：限流、缓存、监控、重试、统一错误处理、优雅降级
"""

import time
import threading
import functools
import hashlib
import json
from collections import defaultdict, deque
from typing import Dict, List, Any, Callable, Optional
from logger import logger


# =============================================================================
# API 限流（滑动窗口限流）
# =============================================================================

class RateLimiter:
    """滑动窗口限流器"""

    def __init__(self, max_requests: int = 60, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: Dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def is_allowed(self, key: str) -> bool:
        """检查是否允许请求"""
        now = time.time()
        window_start = now - self.window_seconds

        with self._lock:
            dq = self._requests[key]
            # 清理过期请求
            while dq and dq[0] < window_start:
                dq.popleft()

            if len(dq) >= self.max_requests:
                return False

            dq.append(now)
            return True

    def get_remaining(self, key: str) -> int:
        """获取剩余请求数"""
        now = time.time()
        window_start = now - self.window_seconds

        with self._lock:
            dq = self._requests.get(key, deque())
            while dq and dq[0] < window_start:
                dq.popleft()
            return max(0, self.max_requests - len(dq))


# 全局限流器
_api_limiter = RateLimiter(max_requests=120, window_seconds=60)
_chat_limiter = RateLimiter(max_requests=30, window_seconds=60)


def get_api_limiter() -> RateLimiter:
    return _api_limiter


def get_chat_limiter() -> RateLimiter:
    return _chat_limiter


# =============================================================================
# 响应缓存
# =============================================================================

class ResponseCache:
    """简单的内存响应缓存（LRU）"""

    def __init__(self, max_size: int = 1000, ttl: int = 300):
        self.max_size = max_size
        self.ttl = ttl
        self._cache: Dict[str, tuple] = {}
        self._access_order: List[str] = []
        self._lock = threading.Lock()

    def _make_key(self, *args, **kwargs) -> str:
        """生成缓存键"""
        key_data = json.dumps({"args": str(args), "kwargs": sorted(kwargs.items())}, sort_keys=True)
        return hashlib.md5(key_data.encode()).hexdigest()

    def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        with self._lock:
            if key in self._cache:
                value, expire_at = self._cache[key]
                if time.time() < expire_at:
                    # 移到末尾（最近使用）
                    if key in self._access_order:
                        self._access_order.remove(key)
                    self._access_order.append(key)
                    return value
                else:
                    # 过期删除
                    del self._cache[key]
                    if key in self._access_order:
                        self._access_order.remove(key)
        return None

    def set(self, key: str, value: Any):
        """设置缓存"""
        with self._lock:
            if key in self._cache:
                if key in self._access_order:
                    self._access_order.remove(key)
            elif len(self._cache) >= self.max_size:
                # 淘汰最久未使用
                oldest = self._access_order.pop(0)
                self._cache.pop(oldest, None)

            self._cache[key] = (value, time.time() + self.ttl)
            self._access_order.append(key)

    def clear(self):
        """清空缓存"""
        with self._lock:
            self._cache.clear()
            self._access_order.clear()

    def invalidate_pattern(self, pattern: str):
        """按模式失效缓存"""
        with self._lock:
            keys_to_delete = [k for k in self._cache if pattern in k]
            for k in keys_to_delete:
                del self._cache[k]
                if k in self._access_order:
                    self._access_order.remove(k)


# 全局缓存
_weather_cache = ResponseCache(max_size=100, ttl=1800)  # 天气缓存 30 分钟
_knowledge_cache = ResponseCache(max_size=500, ttl=3600)  # 知识库缓存 1 小时


def get_weather_cache() -> ResponseCache:
    return _weather_cache


def get_knowledge_cache() -> ResponseCache:
    return _knowledge_cache


def cached(cache: ResponseCache, key_prefix: str = ""):
    """缓存装饰器"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = f"{key_prefix}:{func.__name__}:"
            cache_key += hashlib.md5(
                json.dumps({"args": [str(a) for a in args], "kwargs": sorted(kwargs.items())}, sort_keys=True).encode()
            ).hexdigest()

            cached_result = cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"缓存命中: {func.__name__}")
                return cached_result

            result = func(*args, **kwargs)
            cache.set(cache_key, result)
            return result
        return wrapper
    return decorator


# =============================================================================
# 性能监控
# =============================================================================

class PerformanceMonitor:
    """API 性能监控器"""

    def __init__(self):
        self._stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "count": 0,
            "total_time": 0.0,
            "min_time": float("inf"),
            "max_time": 0.0,
            "errors": 0,
        })
        self._lock = threading.Lock()
        self._start_time = time.time()

    def record(self, endpoint: str, duration: float, error: bool = False):
        """记录请求耗时"""
        with self._lock:
            stats = self._stats[endpoint]
            stats["count"] += 1
            stats["total_time"] += duration
            stats["min_time"] = min(stats["min_time"], duration)
            stats["max_time"] = max(stats["max_time"], duration)
            if error:
                stats["errors"] += 1

    def get_stats(self) -> Dict[str, Any]:
        """获取统计数据"""
        with self._lock:
            result = {}
            total_requests = 0
            total_errors = 0
            for endpoint, stats in self._stats.items():
                count = stats["count"]
                avg_time = stats["total_time"] / count if count > 0 else 0
                result[endpoint] = {
                    "count": count,
                    "avg_time": round(avg_time, 4),
                    "min_time": round(stats["min_time"], 4) if stats["min_time"] != float("inf") else 0,
                    "max_time": round(stats["max_time"], 4),
                    "errors": stats["errors"],
                    "error_rate": round(stats["errors"] / count if count > 0 else 0, 4),
                }
                total_requests += count
                total_errors += stats["errors"]

            return {
                "endpoints": result,
                "total_requests": total_requests,
                "total_errors": total_errors,
                "uptime": round(time.time() - self._start_time, 2),
                "error_rate": round(total_errors / total_requests if total_requests > 0 else 0, 4),
            }

    def reset(self):
        """重置统计"""
        with self._lock:
            self._stats.clear()
            self._start_time = time.time()


# 全局监控器
_monitor = PerformanceMonitor()


def get_monitor() -> PerformanceMonitor:
    return _monitor


def monitor_endpoint(endpoint_name: str = None):
    """性能监控装饰器"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            name = endpoint_name or func.__name__
            start = time.time()
            error = False
            try:
                return func(*args, **kwargs)
            except Exception:
                error = True
                raise
            finally:
                duration = time.time() - start
                _monitor.record(name, duration, error)
        return wrapper
    return decorator


# =============================================================================
# 重试机制
# =============================================================================

def retry(max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0,
          exceptions: tuple = (Exception,)):
    """
    重试装饰器
    max_retries: 最大重试次数
    delay: 初始延迟（秒）
    backoff: 延迟倍增系数
    exceptions: 需要重试的异常类型
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        logger.warning(f"重试 {attempt + 1}/{max_retries}: {func.__name__} - {e}")
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(f"重试失败 {max_retries} 次后仍失败: {func.__name__} - {e}")

            raise last_exception
        return wrapper
    return decorator


# =============================================================================
# 统一错误处理
# =============================================================================

class AppError(Exception):
    """应用错误基类"""
    def __init__(self, message: str, code: int = 400, details: Any = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error": self.message,
            "code": self.code,
            "details": self.details,
        }


class ValidationError(AppError):
    """参数验证错误"""
    def __init__(self, message: str, details: Any = None):
        super().__init__(message, code=400, details=details)


class AuthenticationError(AppError):
    """认证错误"""
    def __init__(self, message: str = "认证失败"):
        super().__init__(message, code=401)


class PermissionError(AppError):
    """权限错误"""
    def __init__(self, message: str = "权限不足"):
        super().__init__(message, code=403)


class NotFoundError(AppError):
    """资源不存在错误"""
    def __init__(self, message: str = "资源不存在"):
        super().__init__(message, code=404)


class RateLimitError(AppError):
    """限流错误"""
    def __init__(self, message: str = "请求过于频繁，请稍后再试"):
        super().__init__(message, code=429)


def handle_exception(e: Exception) -> tuple:
    """统一异常处理，返回 (response_dict, status_code)"""
    if isinstance(e, AppError):
        return e.to_dict(), e.code
    elif isinstance(e, ValueError):
        return {"error": str(e), "code": 400}, 400
    elif isinstance(e, TimeoutError):
        return {"error": "请求超时", "code": 408}, 408
    elif isinstance(e, (ConnectionError, IOError)):
        return {"error": "连接错误", "code": 503}, 503
    else:
        logger.error(f"未处理的异常: {type(e).__name__}: {e}")
        return {"error": "服务器内部错误", "code": 500}, 500


# =============================================================================
# 优雅降级
# =============================================================================

class CircuitBreaker:
    """断路器模式 - 防止级联失败"""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 30):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._state = self.CLOSED
        self._failure_count = 0
        self._last_failure_time = 0
        self._lock = threading.Lock()

    def call(self, func: Callable, fallback: Callable = None, *args, **kwargs):
        """调用函数，带熔断保护"""
        with self._lock:
            if self._state == self.OPEN:
                if time.time() - self._last_failure_time > self.recovery_timeout:
                    self._state = self.HALF_OPEN
                    logger.info("断路器半开，尝试恢复")
                else:
                    if fallback:
                        return fallback(*args, **kwargs)
                    raise Exception("断路器已打开，服务降级")

        try:
            result = func(*args, **kwargs)
            with self._lock:
                if self._state == self.HALF_OPEN:
                    self._state = self.CLOSED
                    self._failure_count = 0
                    logger.info("断路器已关闭，服务恢复")
            return result
        except Exception as e:
            with self._lock:
                self._failure_count += 1
                self._last_failure_time = time.time()
                if self._failure_count >= self.failure_threshold and self._state == self.CLOSED:
                    self._state = self.OPEN
                    logger.warning(f"断路器打开，失败次数: {self._failure_count}")
            if fallback:
                return fallback(*args, **kwargs)
            raise

    @property
    def state(self) -> str:
        return self._state

    def reset(self):
        """重置断路器"""
        with self._lock:
            self._state = self.CLOSED
            self._failure_count = 0
            self._last_failure_time = 0


# 全局断路器
_llm_circuit = CircuitBreaker(failure_threshold=3, recovery_timeout=60)
_api_circuit = CircuitBreaker(failure_threshold=5, recovery_timeout=30)


def get_llm_circuit() -> CircuitBreaker:
    return _llm_circuit


def get_api_circuit() -> CircuitBreaker:
    return _api_circuit


# =============================================================================
# 内存优化
# =============================================================================

class MemoryOptimizer:
    """内存优化器 - 定期清理大对象"""

    def __init__(self):
        self._large_objects: List[tuple] = []
        self._lock = threading.Lock()

    def register_large_object(self, obj: Any, cleanup_callback: Callable = None):
        """注册大对象，定期清理"""
        with self._lock:
            self._large_objects.append((obj, cleanup_callback, time.time()))

    def cleanup(self):
        """手动触发清理"""
        import gc
        count = gc.collect()
        logger.debug(f"GC 内存优化: 回收了 {count} 个对象")
        return count

    def start_background_cleanup(self, interval: int = 300):
        """启动后台定期清理"""
        def _loop():
            while True:
                time.sleep(interval)
                try:
                    self.cleanup()
                except Exception as e:
                    logger.error(f"后台内存清理异常: {e}")

        t = threading.Thread(target=_loop, daemon=True, name="memory-optimizer")
        t.start()
        logger.info("内存优化器已启动")


_memory_optimizer = MemoryOptimizer()


def get_memory_optimizer() -> MemoryOptimizer:
    return _memory_optimizer
