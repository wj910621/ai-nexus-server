"""
异步工具测试
"""

import time
from async_utils import run_in_thread, run_in_thread_nonblocking


def slow_task(x):
    time.sleep(0.2)
    return x * 2


def main():
    print("=== 异步工具测试 ===\n")

    print("1. 测试后台线程执行并获取结果...")
    future = run_in_thread(slow_task, 5)
    result = future.result(timeout=5)
    assert result == 10
    print(f"  ✓ 结果: {result}")

    print("\n2. 测试非阻塞执行...")
    start = time.time()
    run_in_thread_nonblocking(slow_task, 3)
    elapsed = time.time() - start
    print(f"  ✓ 提交耗时: {elapsed:.3f}s（应远小于 0.2s）")
    assert elapsed < 0.05

    print("\n=== 异步工具测试完成 ===")


if __name__ == "__main__":
    main()
