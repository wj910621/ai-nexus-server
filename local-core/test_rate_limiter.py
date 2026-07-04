"""
限流器测试
"""

from rate_limiter import SlidingWindowLimiter


def main():
    print("=== 限流器测试 ===\n")

    limiter = SlidingWindowLimiter(max_requests=3, burst=1)
    key = "test_client"

    print("1. 正常请求（限制 3 + 突发 1 = 4）...")
    for i in range(5):
        allowed, info = limiter.is_allowed(key)
        print(f"  第 {i+1} 次: allowed={allowed}, remaining={info['remaining']}")

    assert allowed is False, "第 5 次应被限流"
    print("  ✓ 限流触发正确")

    print("\n2. 查询接口不增加计数...")
    info = limiter.get_info(key)
    print(f"  info: {info}")

    print("\n=== 限流器测试完成 ===")


if __name__ == "__main__":
    main()
