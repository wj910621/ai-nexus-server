"""请求去重器 - 并发相同请求合并为一次实际调用"""
import asyncio
import hashlib
import json
from typing import Any, Awaitable, Callable


class RequestDeduplicator:
    """请求去重器

    当多个并发请求调用相同函数+参数时，仅执行一次实际调用，
    其他请求通过 asyncio.Future 共享结果。

    适用场景：多个用户同时点 "生成猫娘图"，实际只调一次 Pollinations API。
    """

    def __init__(self) -> None:
        self._in_flight: dict[str, asyncio.Future] = {}
        self._lock = asyncio.Lock()

    def _build_key(
        self,
        func_name: str,
        args: tuple,
        kwargs: dict,
    ) -> str:
        """构建去重键"""
        try:
            args_str = json.dumps(args, default=str, sort_keys=True)
            kwargs_str = json.dumps(kwargs, default=str, sort_keys=True)
        except (TypeError, ValueError):
            args_str = repr(args)
            kwargs_str = repr(sorted(kwargs.items()))
        key_input = f"{func_name}:{args_str}:{kwargs_str}"
        return hashlib.sha256(key_input.encode("utf-8")).hexdigest()

    async def deduplicate(
        self,
        func: Callable[..., Awaitable[Any]],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """去重执行异步函数"""
        key = self._build_key(func.__qualname__, args, kwargs)

        # Critical: only hold the lock while inspecting/inserting the future.
        # Never await the future inside the lock — that would block other
        # waiters from finding the in-flight entry, causing duplicate runs.
        async with self._lock:
            existing = self._in_flight.get(key)
            if existing is not None and not existing.done():
                waiter = existing
            else:
                waiter = None
                future = asyncio.get_event_loop().create_future()
                self._in_flight[key] = future

        if waiter is not None:
            return await asyncio.shield(waiter)

        try:
            result = await func(*args, **kwargs)
            future.set_result(result)
            return result
        except Exception as exc:
            if not future.done():
                future.set_exception(exc)
            raise
        finally:
            async with self._lock:
                self._in_flight.pop(key, None)

    def get_in_flight_count(self) -> int:
        """当前在途请求数（监控用）"""
        return len(self._in_flight)

    async def clear(self) -> None:
        """清空所有在途请求（测试用）"""
        async with self._lock:
            for fut in self._in_flight.values():
                if not fut.done():
                    fut.cancel()
            self._in_flight.clear()


request_deduplicator = RequestDeduplicator()
