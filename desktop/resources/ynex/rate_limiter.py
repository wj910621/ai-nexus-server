"""
API 限流器
基于滑动窗口计数，支持按 IP 和 API Key 限流。
"""

import time
import threading
from collections import defaultdict
from typing import Optional, Tuple

from config import settings
from logger import logger


class SlidingWindowLimiter:
    """
    滑动窗口限流器。
    每个 key 维护一个按分钟划分的时间桶，统计请求数。
    """

    def __init__(self, max_requests: int = 60, window_seconds: int = 60, burst: int = 10):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.burst = burst
        self._buckets: dict = defaultdict(lambda: defaultdict(int))
        self._lock = threading.RLock()

    def _current_bucket(self) -> int:
        return int(time.time() // self.window_seconds)

    def is_allowed(self, key: str) -> Tuple[bool, dict]:
        """
        检查 key 是否允许通过。
        返回 (allowed, info)，info 包含剩余配额和重置时间。
        """
        if not key:
            return True, {}

        now_bucket = self._current_bucket()
        window_start = now_bucket - 1  # 保留两个桶即可覆盖滑动窗口

        with self._lock:
            buckets = self._buckets[key]

            # 清理过期桶
            for bucket in list(buckets.keys()):
                if bucket < window_start:
                    del buckets[bucket]

            # 内存泄漏修复：若该 key 的所有桶都已过期清空，则删除该 key 条目，
            # 避免 _buckets 长期累积永不释放（每个曾访问过的 IP/Key 都会留下空 dict）。
            if not buckets:
                self._buckets.pop(key, None)
                # 重新获取空 buckets 用于计数（本次请求会创建新桶）
                buckets = self._buckets[key]

            # 计算当前窗口内总请求数
            current_count = sum(buckets.values())
            allowed = current_count < (self.max_requests + self.burst)

            if allowed:
                buckets[now_bucket] += 1
                current_count += 1

            remaining = max(0, self.max_requests + self.burst - current_count)
            reset_time = (now_bucket + 1) * self.window_seconds

            info = {
                "limit": self.max_requests + self.burst,
                "remaining": remaining,
                "reset_at": reset_time,
            }
            return allowed, info

    def get_info(self, key: str) -> dict:
        """只查询不增加计数"""
        now_bucket = self._current_bucket()
        window_start = now_bucket - 1
        with self._lock:
            buckets = self._buckets.get(key, {})
            current_count = sum(
                count for bucket, count in buckets.items() if bucket >= window_start
            )
            return {
                "limit": self.max_requests + self.burst,
                "remaining": max(0, self.max_requests + self.burst - current_count),
                "reset_at": (now_bucket + 1) * self.window_seconds,
            }


# 全局限流器
_limiter = None


def get_limiter() -> SlidingWindowLimiter:
    global _limiter
    if _limiter is None:
        _limiter = SlidingWindowLimiter(
            max_requests=settings.rate_limit_requests_per_minute,
            window_seconds=60,
            burst=settings.rate_limit_burst,
        )
    return _limiter


def check_rate_limit(client_id: str) -> Tuple[bool, dict]:
    """检查指定 client_id 是否被限流"""
    if not settings.rate_limit_enabled:
        return True, {"limit": 0, "remaining": 0, "reset_at": 0}
    return get_limiter().is_allowed(client_id)


def get_client_id(request) -> str:
    """
    从请求中提取限流标识：API Key（仅Header） > remote_addr。

    安全策略：
      - API Key 优先：按用户限流，更精确；
      - IP 兜底：使用 remote_addr（TCP 连接真实来源），而非 X-Forwarded-For，
        因为 XFF 可被客户端伪造，攻击者可通过伪造 XFF 绕过基于 IP 的限流。
        若部署在反向代理后，应由代理层（Nginx limit_req）负责 IP 限流。
    注意：禁止从 URL 参数读取 API Key，避免日志泄露。
    """
    api_key = request.headers.get("X-API-Key", "") or request.headers.get("Authorization", "").replace("Bearer ", "")
    if api_key:
        return f"key:{api_key[:32]}"

    ip = request.remote_addr or "unknown"
    return f"ip:{ip}"
