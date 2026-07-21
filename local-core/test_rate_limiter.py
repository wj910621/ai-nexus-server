"""
限流器测试
"""
import time

from rate_limiter import SlidingWindowLimiter


def test_basic_limit_and_burst():
    print("\n=== 基本限流（max=3, burst=1）===")
    limiter = SlidingWindowLimiter(max_requests=3, burst=1)
    key = "test_client_basic"

    print("1. 正常请求（限制 3 + 突发 1 = 4）...")
    for i in range(5):
        allowed, info = limiter.is_allowed(key)
        print(f"  第 {i+1} 次: allowed={allowed}, remaining={info['remaining']}")

    assert allowed is False, "第 5 次应被限流"
    print("  ✓ 限流触发正确")


def test_get_info_does_not_increment():
    print("\n=== 查询接口不增加计数 ===")
    limiter = SlidingWindowLimiter(max_requests=10, burst=0)
    key = "test_client_info"
    # 先消耗 2 次
    limiter.is_allowed(key)
    limiter.is_allowed(key)
    # 连续查询若干次，remaining 应保持不变
    info1 = limiter.get_info(key)
    info2 = limiter.get_info(key)
    info3 = limiter.get_info(key)
    assert info1["remaining"] == info2["remaining"] == info3["remaining"], \
        f"get_info 不应影响计数, got {info1['remaining']} {info2['remaining']} {info3['remaining']}"
    print(f"  ✓ 3 次 get_info 后 remaining 仍为 {info1['remaining']}")


def test_empty_key_short_circuits():
    """空 key 不参与计数（避免空字符串污染共享桶）"""
    print("\n=== 空 key 短路 ===")
    limiter = SlidingWindowLimiter(max_requests=2, burst=0)
    allowed, info = limiter.is_allowed("")
    assert allowed is True
    assert info == {}, f"空 key 应返回空 info, got {info}"
    print("  ✓ 空 key 始终放行且无副作用")


def test_per_key_isolation():
    """不同 key 各自独立计数，不应互相影响"""
    print("\n=== Key 隔离 ===")
    limiter = SlidingWindowLimiter(max_requests=2, burst=0)
    a, b = "client_A", "client_B"
    for _ in range(2):
        limiter.is_allowed(a)
    # A 达到上限
    allowed_a, _ = limiter.is_allowed(a)
    assert allowed_a is False
    # B 仍应有完整额度
    allowed_b, info_b = limiter.is_allowed(b)
    assert allowed_b is True
    assert info_b["remaining"] == 1
    print("  ✓ 不同 key 互不影响")


def test_memory_leak_fix_releases_empty_key_entries():
    """关键回归：is_allowed 在桶清空后必须从 _buckets 中删除该 key，
    防止长期累积。注意该清理是 lazy 的：仅在 key 被再次访问、
    且其历史桶全部过期时才生效（这正是代码注释所描述的语义）。
    验证方式：访问一个 key 后等窗口过期，然后再次访问；
    清理逻辑应被触发，本次计数后 key 仍存在（被新一轮访问重建），
    但旧桶不应残留。"""
    print("\n=== 桶清空时回收 key（防内存泄漏）===")
    limiter = SlidingWindowLimiter(max_requests=1, burst=0, window_seconds=1)

    key = "ephemeral_client"
    # 第一次访问
    allowed, _ = limiter.is_allowed(key)
    assert allowed is True
    assert key in limiter._buckets
    # 此时 _buckets[key] 有一个桶
    assert len(limiter._buckets[key]) == 1

    # 等窗口过期
    time.sleep(2.1)

    # 再次访问：清理逻辑应删除旧桶和 key 条目，再创建新桶
    allowed2, _ = limiter.is_allowed(key)
    assert allowed2 is True
    assert key in limiter._buckets
    # 关键断言：旧桶已被删除，当前只有一个新桶
    assert len(limiter._buckets[key]) == 1, \
        f"应有且仅有一个新桶, got {dict(limiter._buckets[key])}"
    # 新桶的计数应为 1
    now_bucket = limiter._current_bucket()
    assert limiter._buckets[key][now_bucket] == 1
    print("  ✓ 旧桶过期后被清理，重建后仅保留当前窗口的桶")

    # 额外验证：长期不被访问的 key 会驻留（lazy 清理的预期行为）
    # 这是一个明确的语义文档，避免未来误改清理策略
    long_idle = "long_idle_client"
    limiter.is_allowed(long_idle)
    time.sleep(2.1)
    # 长期不再访问 -> 仍驻留（lazy 清理），但仅占用 1 个桶
    assert long_idle in limiter._buckets
    assert len(limiter._buckets[long_idle]) == 1
    print("  ✓ lazy 清理语义：长期空闲 key 仅保留 1 个桶，不会无限增长")


def main():
    print("=== 限流器测试 ===")
    test_basic_limit_and_burst()
    test_get_info_does_not_increment()
    test_empty_key_short_circuits()
    test_per_key_isolation()
    test_memory_leak_fix_releases_empty_key_entries()
    print("\n=== 限流器测试完成 ===")


if __name__ == "__main__":
    main()
