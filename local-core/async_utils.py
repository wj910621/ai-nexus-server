"""
异步工具集
把阻塞 IO 任务丢到后台线程池，避免阻塞 Flask 请求线程。
"""

import os
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Any


# 通用后台线程池
_worker_pool = ThreadPoolExecutor(
    max_workers=min(32, (os.cpu_count() or 4) * 2),
    thread_name_prefix="ynex_worker_"
)


def run_in_thread(func: Callable, *args, **kwargs) -> Any:
    """
    在后台线程执行函数并返回 Future 对象。
    调用方可以用 .result(timeout=...) 获取结果。
    """
    return _worker_pool.submit(func, *args, **kwargs)


def run_in_thread_nonblocking(func: Callable, *args, **kwargs):
    """在后台线程执行函数，不等待结果"""
    _worker_pool.submit(func, *args, **kwargs)
