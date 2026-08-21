"""Provider 故障转移 - 熔断器 + 次级 provider + 降级模式

P2: 扩展 failure_reason 字段，差异化冷却时间
"""
import asyncio
import enum
import logging
import time
from typing import Awaitable, Callable, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(str, enum.Enum):
    CLOSED = "closed"      # 正常，请求通过
    OPEN = "open"          # 熔断，请求拒绝
    HALF_OPEN = "half_open"  # 半开，试探性放行


# P2: 失败原因 → 冷却时间（秒）映射
FAILURE_REASON_COOLDOWN: dict[str, int] = {
    "oom": 300,           # 5min（短期，可能下次内存够）
    "unsupported": 86400,  # 1 day（永久，需重启应用）
    "dependency": 86400,   # 1 day（永久，需安装依赖）
    "timeout": 60,         # 1min（短期，可能是临时负载）
    "unknown": 30,         # 30s（保守）
}
DEFAULT_COOLDOWN = 30


class ProviderFailover:
    """熔断器

    状态机:
        CLOSED --(threshold 连续失败)--> OPEN
        OPEN --(reset_seconds 超时)--> HALF_OPEN (on next can_call)
        HALF_OPEN --(成功)--> CLOSED
        HALF_OPEN --(失败)--> OPEN

    P2: record_failure() 接受 reason 参数，差异化冷却时间。
    """

    def __init__(
        self,
        threshold: int = 5,
        reset_seconds: int = 30,
    ) -> None:
        self.threshold = threshold
        self.reset_seconds = reset_seconds
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time: float = 0.0
        # P2: 失败原因
        self.failure_reason: str = ""

    def can_call(self) -> bool:
        """检查是否可以调用主 provider"""
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            # Check if reset timeout has elapsed
            if time.time() - self.last_failure_time >= self.reset_seconds:
                self.state = CircuitState.HALF_OPEN
                logger.info("Circuit transitioning OPEN → HALF_OPEN")
                return True
            return False
        # HALF_OPEN
        return True

    async def record_success(self) -> None:
        """记录一次成功"""
        self.failure_count = 0
        self.failure_reason = ""  # P2: 清除失败原因
        if self.state in (CircuitState.OPEN, CircuitState.HALF_OPEN):
            self.state = CircuitState.CLOSED
            logger.info("Circuit closing (success recorded)")

    async def record_failure(self, reason: str = "") -> None:
        """记录一次失败

        Args:
            reason: P2 新增。失败原因："oom" / "unsupported" / "dependency" / "timeout" / "" (unknown)
                    不同原因对应不同冷却时间。
        """
        self.failure_count += 1
        self.last_failure_time = time.time()
        self.failure_reason = reason  # P2: 记录失败原因

        # P2: 根据 reason 调整冷却时间
        # 仅在 reason 非空时覆盖 reset_seconds；
        # reason 为空（unknown）时保留 __init__ 中用户设置的 reset_seconds（默认 30）。
        if reason in FAILURE_REASON_COOLDOWN:
            self.reset_seconds = FAILURE_REASON_COOLDOWN[reason]
        elif reason == "":
            # unknown：保留 __init__ 的 reset_seconds（默认 30 = FAILURE_REASON_COOLDOWN["unknown"]）
            pass
        else:
            self.reset_seconds = DEFAULT_COOLDOWN

        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            logger.warning(f"Circuit re-opening (HALF_OPEN failure, reason={reason!r})")
        elif self.failure_count >= self.threshold:
            self.state = CircuitState.OPEN
            logger.warning(
                f"Circuit opening after {self.failure_count} consecutive failures "
                f"(reason={reason!r}, cooldown={self.reset_seconds}s)"
            )

    async def call_with_failover(
        self,
        primary: Callable[..., Awaitable[T]],
        secondary: Optional[Callable[..., Awaitable[T]]] = None,
        *args,
        **kwargs,
    ) -> T:
        """带故障转移的调用"""
        # If circuit is OPEN, skip primary entirely
        if not self.can_call() and secondary is not None:
            logger.info("Circuit OPEN — using secondary provider directly")
            return await secondary(*args, **kwargs)

        # Try primary
        try:
            result = await primary(*args, **kwargs)
            await self.record_success()
            return result
        except Exception as primary_exc:
            # P2: 根据异常类型识别 reason
            reason = _classify_exception(primary_exc)
            await self.record_failure(reason=reason)
            logger.warning(f"Primary failed (reason={reason}): {primary_exc}")
            if secondary is None:
                raise
            # Fall back to secondary
            try:
                return await secondary(*args, **kwargs)
            except Exception as secondary_exc:
                logger.error(f"Secondary also failed: {secondary_exc}")
                raise secondary_exc


def _classify_exception(exc: Exception) -> str:
    """P2: 根据异常类型识别失败原因

    >>> _classify_exception(RuntimeError("out of memory"))
    'oom'
    >>> _classify_exception(ImportError("no module"))
    'dependency'
    >>> _classify_exception(asyncio.TimeoutError())
    'timeout'
    """
    exc_str = str(exc).lower()
    if "out of memory" in exc_str or "oom" in exc_str:
        return "oom"
    if isinstance(exc, (ImportError, ModuleNotFoundError)):
        return "dependency"
    if isinstance(exc, asyncio.TimeoutError):
        return "timeout"
    if "not supported" in exc_str or "unsupported" in exc_str:
        return "unsupported"
    return ""
