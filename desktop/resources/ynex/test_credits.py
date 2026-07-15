"""
积分定价系统测试
覆盖积分扣减、套餐订阅、会员权限、终身版限量等核心功能
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from credits_system import (
    init_db,
    DB_PATH,
    get_user_credits,
    add_credits,
    deduct_credits,
    can_use_model,
    subscribe_plan,
    get_available_credits,
    check_plan_active,
    get_lifetime_sold_count,
    get_lifetime_remaining,
    get_lifetime_current_price,
    get_transactions,
    get_usage_stats,
    get_all_plans,
    calculate_credit_cost,
    calculate_cost_price,
    get_profit_margin,
)


def _cleanup_db():
    if DB_PATH.exists():
        os.remove(DB_PATH)


def main():
    print("=== 积分定价系统测试 ===\n")

    _cleanup_db()
    init_db()

    user_id = "test_user_123"

    # 1. 用户积分获取与初始化
    print("1. 用户积分获取与初始化...")
    uc = get_user_credits(user_id)
    assert uc.user_id == user_id
    assert uc.plan == "free"
    assert uc.credits == 0
    print("  ✓ 新用户默认免费套餐")

    # 2. 积分充值
    print("\n2. 积分充值...")
    success = add_credits(user_id, 100, "测试充值")
    assert success is True
    uc = get_user_credits(user_id)
    assert uc.credits == 100
    print("  ✓ 充值成功")

    # 3. 积分扣减（付费套餐）
    print("\n3. 积分扣减（付费套餐）...")
    subscribe_plan(user_id, "monthly")
    uc = get_user_credits(user_id)
    assert uc.plan == "monthly"
    assert uc.credits >= 1000

    ok, msg, cost = deduct_credits(user_id, "deepseekv3", description="测试扣减")
    assert ok is True
    assert msg == "ok"
    assert cost == 1
    uc = get_user_credits(user_id)
    assert uc.credits == 1099
    print("  ✓ 正常扣减成功")

    ok, msg, cost = deduct_credits(user_id, "deepseekv3", 0, 0, "重复扣减")
    assert ok is True
    assert cost == 1
    print("  ✓ 重复扣减成功")

    # 4. 免费模型不扣积分
    print("\n4. 免费模型不扣积分...")
    ok, msg, cost = deduct_credits(user_id, "ark_dsv4p")
    assert ok is True
    assert msg == "免费模型"
    assert cost == 0
    uc = get_user_credits(user_id)
    assert uc.credits == 1098
    print("  ✓ 免费模型不扣积分")

    # 5. 套餐权限检查
    print("\n5. 套餐权限检查...")
    ok, msg = can_use_model(uc, "deepseekv3")
    assert ok is True
    assert msg == ""

    ok, msg = can_use_model(uc, "gpt4o")
    assert ok is True
    assert msg == ""

    uc_free = get_user_credits("free_user")
    ok, msg = can_use_model(uc_free, "gpt4o")
    assert ok is False
    assert "升级套餐" in msg
    print("  ✓ 套餐权限检查正确")

    # 6. 可用积分查询
    print("\n6. 可用积分查询...")
    available = get_available_credits(uc)
    assert available == 1098
    print("  ✓ 付费套餐可用积分正确")

    available_free = get_available_credits(uc_free)
    assert available_free == 10
    print("  ✓ 免费套餐每日积分正确")

    # 7. 套餐激活状态
    print("\n7. 套餐激活状态...")
    assert check_plan_active(uc) is True
    assert check_plan_active(uc_free) is True

    uc_expired = get_user_credits("expired_user")
    subscribe_plan("expired_user", "monthly")
    uc_expired = get_user_credits("expired_user")
    uc_expired.plan_expires_at = time.time() - 3600

    assert check_plan_active(uc_expired) is False
    print("  ✓ 套餐过期检查正确")

    # 8. 终身版功能
    print("\n8. 终身版功能...")
    sold = get_lifetime_sold_count()
    assert sold == 0

    remaining = get_lifetime_remaining()
    assert remaining == 500

    price = get_lifetime_current_price()
    assert price == 699.0
    print("  ✓ 终身版初始状态正确")

    ok, msg = subscribe_plan("lifetime_user", "lifetime")
    assert ok is True
    assert "终身版" in msg

    sold = get_lifetime_sold_count()
    assert sold == 1

    remaining = get_lifetime_remaining()
    assert remaining == 499
    print("  ✓ 终身版购买成功")

    plans = get_all_plans()
    assert "lifetime" in plans
    assert plans["lifetime"]["sold_count"] == 1
    assert plans["lifetime"]["remaining"] == 499
    print("  ✓ 套餐信息获取正确")

    # 9. 交易记录
    print("\n9. 交易记录...")
    txs = get_transactions(user_id)
    assert len(txs) >= 2
    assert any(t.type == "consume" for t in txs)
    assert any(t.type == "subscription" for t in txs)
    print("  ✓ 交易记录正确")

    # 10. 使用统计
    print("\n10. 使用统计...")
    stats = get_usage_stats(user_id)
    assert "total_calls" in stats
    assert "total_credits_used" in stats
    assert "profit_margin" in stats
    print("  ✓ 使用统计获取正确")

    # 11. 成本与定价计算
    print("\n11. 成本与定价计算...")
    cost = calculate_cost_price("deepseekv3", 2000, 2000)
    assert cost == 0.01
    print(f"  ✓ 成本计算: {cost}")

    credits = calculate_credit_cost("deepseekv3", 2000, 2000)
    assert credits == 1
    print(f"  ✓ 积分定价: {credits}")

    margin = get_profit_margin("deepseekv3")
    assert margin is not None
    assert margin > 0
    print(f"  ✓ 利润率: {margin:.2%}")

    # 12. 积分不足场景
    print("\n12. 积分不足场景...")
    _cleanup_db()
    init_db()

    uc_low = get_user_credits("low_user")
    subscribe_plan("low_user", "monthly")
    uc_low = get_user_credits("low_user")

    for _ in range(1001):
        deduct_credits("low_user", "deepseekv3")
    uc_low = get_user_credits("low_user")

    ok, msg, cost = deduct_credits("low_user", "deepseekv3")
    assert ok is False
    assert "积分不足" in msg
    assert cost == 0
    print("  ✓ 积分不足被拒绝")

    # 13. 免费套餐日限额
    print("\n13. 免费套餐日限额...")
    _cleanup_db()
    init_db()

    uc_free_limit = get_user_credits("free_limit_user")
    for i in range(10):
        ok, msg, cost = deduct_credits("free_limit_user", "glm4plus")
        assert ok is True

    ok, msg, cost = deduct_credits("free_limit_user", "glm4plus")
    assert ok is False
    assert "积分不足" in msg
    print("  ✓ 免费套餐日限额生效")

    print("\n=== 积分定价系统测试完成 ===")


if __name__ == "__main__":
    main()