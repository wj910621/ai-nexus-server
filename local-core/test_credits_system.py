"""
credits_system.py 单元测试
==========================
覆盖范围：
  - init_db：表结构初始化、pricing_config 种子数据
  - get_user_credits / _ensure_user：自动创建用户
  - can_use_model：套餐 tier -> 模型 tier 映射
  - calculate_credit_cost / calculate_cost_price：定价计算
  - deduct_credits：免费模型 / 额度不足 / 并发安全
  - add_credits：充值入账 + 事务记录
  - subscribe_plan：套餐开通、积分发放、过期时间计算
  - lifetime 限量防超卖（BEGIN IMMEDIATE + 原子条件 UPDATE）
  - get_transactions / get_usage_stats / admin_get_stats：统计查询
  - check_lifetime_price_increase / get_lifetime_current_price：终身版涨价
  - 并发扣减：free 套餐 daily_used 不超限，付费套餐 credits 不为负
  - 每日自动重置（_check_daily_reset）
"""

import os
import sys
import time
import shutil
import tempfile
import threading

_ORIG_CWD = os.getcwd()


def _setup():
    tmp = tempfile.mkdtemp(prefix="ynex_credits_test_")
    os.chdir(tmp)
    # 防止 init_db 写入真实 data/credits.db
    from pathlib import Path
    import credits_system as cs
    cs.DB_PATH = Path(tmp) / "credits.db"
    # 重新 init（因为模块 import 时已运行过 init_db，但 DB_PATH 指向旧位置）
    cs.init_db()
    return tmp, cs


def _teardown():
    os.chdir(_ORIG_CWD)


def main():
    tmp, cs = _setup()
    try:
        _run_tests(cs, tmp)
    finally:
        _teardown()


def _run_tests(cs, tmp_dir):
    errors = []

    # ================================
    # 1. DB 初始化
    # ================================
    print("1. 数据库初始化")

    # 直接查询验证表存在 + 种子数据
    import sqlite3
    conn = sqlite3.connect(str(cs.DB_PATH))
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    for expected in ["user_credits", "credit_transactions",
                     "lifetime_sales", "pricing_config"]:
        assert expected in tables, f"缺少表 {expected}"
    sold = conn.execute(
        "SELECT value FROM pricing_config WHERE key='lifetime_sold'"
    ).fetchone()[0]
    batch = conn.execute(
        "SELECT value FROM pricing_config WHERE key='lifetime_batch'"
    ).fetchone()[0]
    assert sold == "0" and batch == "1"
    conn.close()
    print(f"   ✓ 4 张表已创建，lifetime_sold=0, lifetime_batch=1")

    # ================================
    # 2. get_user_credits / _ensure_user
    # ================================
    print("\n2. 用户账户自动创建")
    u = cs.get_user_credits("new-user")
    assert u.credits == 0 and u.plan == "free" and u.total_used == 0
    assert u.daily_used == 0
    print("   ✓ 新用户自动创建，默认 free 套餐")

    # 再次读取相同用户不应创建新记录
    u2 = cs.get_user_credits("new-user")
    assert u2.user_id == u.user_id
    assert abs(u2.created_at - u.created_at) < 1.0  # sqlite REAL 精度容忍
    print("   ✓ 重复读取同一用户返回同一条记录")

    # ================================
    # 3. calculate_credit_cost / calculate_cost_price
    # ================================
    print("\n3. 定价计算")

    # 免费模型 -> 0 积分
    assert cs.calculate_credit_cost("ark_dsv4p", 5000, 5000) == 0
    assert cs.calculate_credit_cost("sf_qwen3_8b", 0, 2000) == 0
    print("   ✓ 免费模型返回 0 积分")

    # 有预定价的模型直接返回
    assert cs.calculate_credit_cost("deepseekv3") == 1
    assert cs.calculate_credit_cost("deepseekr1") == 5
    assert cs.calculate_credit_cost("claude4") == 12
    print("   ✓ 预定价模型返回正确积分")

    # 未知模型 -> 2 积分默认值
    assert cs.calculate_credit_cost("totally_new_model") == 2
    print("   ✓ 未知模型返回默认 2 积分")

    # 成本价为 0 的模型
    assert cs.calculate_cost_price("ark_dsv4p", 10000, 10000) == 0.0
    print("   ✓ free 模型成本价 0.0")

    # 正常模型成本价
    cost = cs.calculate_cost_price("deepseekv3", 2000, 2000)
    # deepseekv3 input=1, output=4 per 1M tokens
    expected = 1 * 2000 / 1_000_000 + 4 * 2000 / 1_000_000
    assert abs(cost - expected) < 1e-8, f"{cost} != {expected}"
    print(f"   ✓ deepseekv3 2K+2K 成本价 {cost:.6f} 元")

    # ================================
    # 4. can_use_model —— 套餐 tier 限制
    # ================================
    print("\n4. 套餐模型权限 can_use_model")

    u = cs.get_user_credits("free-user")
    # free 套餐只能用 free + standard tier
    ok, msg = cs.can_use_model(u, "gpt4o")  # flagship tier
    assert ok is False and "升级套餐" in msg
    print("   ✓ free 套餐被拒 flagship 模型")

    ok, _ = cs.can_use_model(u, "deepseekv3")  # standard tier
    assert ok
    print("   ✓ free 套餐可用 standard 模型")

    # monthly 套餐全部可用
    cs.subscribe_plan("premium-user", "monthly")
    u_prem = cs.get_user_credits("premium-user")
    ok, _ = cs.can_use_model(u_prem, "gpt4o")
    assert ok
    print("   ✓ monthly 套餐可用 flagship 模型")

    # ================================
    # 5. deduct_credits 核心路径
    # ================================
    print("\n5. deduct_credits 核心路径")

    # 5.1 免费模型直接返回成功
    ok, msg, cost = cs.deduct_credits("free-user", "ark_dsv4p", 1000, 1000)
    assert ok and cost == 0 and msg == "免费模型"
    print("   ✓ 免费模型扣减路径直接返回，不消耗额度")

    # 5.2 free 套餐 + standard 模型：每日 10 积分上限
    cs.subscribe_plan("free-daily-user", "free")
    # 第一次扣减成功
    ok, msg, cost = cs.deduct_credits("free-daily-user", "deepseekv3", 0, 0)  # 1 积分
    assert ok and cost == 1
    print("   ✓ free 套餐第一次扣减成功")

    # 连续扣减直到 daily_used 触顶（10 次，每次 1 积分）
    for i in range(9):
        cs.deduct_credits("free-daily-user", "deepseekv3")
    # 第 11 次应该失败
    ok, msg, _ = cs.deduct_credits("free-daily-user", "deepseekv3")
    assert ok is False and ("并发竞争" in msg or "积分不足" in msg), \
        f"第 11 次应失败，实际 ok={ok} msg={msg}"
    print("   ✓ free 套餐连续扣减后触顶被拦截")

    # 5.3 付费套餐：余额不足时被拒
    # 用 yearly（15000 积分）然后人工 UPDATE credits 为 5，更可控
    cs.subscribe_plan("paid-user", "yearly")
    # 直接把 credits 设为 5，跳过赠送的 15000
    import sqlite3 as _s3
    conn = _s3.connect(str(cs.DB_PATH))
    conn.execute("UPDATE user_credits SET credits = 5 WHERE user_id = 'paid-user'")
    conn.commit()
    conn.close()
    # deepseekr1 = 5 积分
    ok, _, _ = cs.deduct_credits("paid-user", "deepseekr1")
    assert ok
    # 再扣 1 积分，余额已空
    ok, msg, _ = cs.deduct_credits("paid-user", "deepseekv3")
    assert ok is False and "积分不足" in msg, f"应为余额不足，实际 ok={ok} msg={msg}"
    print("   ✓ 付费套餐余额耗尽被拦截")

    # ================================
    # 6. add_credits 充值
    # ================================
    print("\n6. add_credits 充值")
    cs.add_credits("recharge-user", amount=100, description="测试充值")
    u = cs.get_user_credits("recharge-user")
    assert u.credits == 100
    print("   ✓ 充值 100 积分入账")

    # 交易记录验证
    txs = cs.get_transactions("recharge-user")
    assert any(t.type == "recharge" and t.amount == 100 for t in txs)
    print(f"   ✓ 充值事务已记录，共 {len(txs)} 条")

    # ================================
    # 7. subscribe_plan —— 套餐开通
    # ================================
    print("\n7. subscribe_plan")

    # 非法套餐
    ok, msg = cs.subscribe_plan("u1", "nonexistent")
    assert ok is False and msg == "套餐不存在"
    print("   ✓ 非法套餐被拒")

    # monthly 开通 + 积分发放
    ok, msg = cs.subscribe_plan("monthly-user", "monthly")
    assert ok
    u = cs.get_user_credits("monthly-user")
    assert u.plan == "monthly"
    assert u.credits == 1000
    assert u.plan_expires_at is not None and u.plan_expires_at > time.time()
    print(f"   ✓ monthly 套餐开通：plan={u.plan}, credits={u.credits}, expires 合理")

    # yearly 积分
    ok, _ = cs.subscribe_plan("yearly-user", "yearly")
    assert ok
    u = cs.get_user_credits("yearly-user")
    assert u.credits == 15000
    print("   ✓ yearly 套餐 15000 积分正确")

    # lifetime 积分 + 限量（先检查剩余量）
    remaining_before = cs.get_lifetime_remaining()
    assert remaining_before == 500  # 从 0 sold 开始
    ok, _ = cs.subscribe_plan("lifetime-user-1", "lifetime")
    assert ok
    assert cs.get_lifetime_sold_count() == 1
    remaining_after = cs.get_lifetime_remaining()
    assert remaining_after == 499
    print("   ✓ lifetime 套餐开通，sold_count 递增，remaining 递减")

    # 积分正确
    u = cs.get_user_credits("lifetime-user-1")
    assert u.plan == "lifetime" and u.credits == 50000
    print("   ✓ lifetime 套餐 50000 积分 + lifetime plan 正确")

    # ================================
    # 8. lifetime 并发防超卖（核心竞态防护）
    # ================================
    print("\n8. lifetime 并发防超卖（原子条件 UPDATE）")
    # 手动将 sold 设置为接近上限，模拟批量并发
    import sqlite3 as _sqlite3
    conn = _sqlite3.connect(str(cs.DB_PATH))
    conn.execute("UPDATE pricing_config SET value = '499' WHERE key='lifetime_sold'")
    conn.commit()
    conn.close()

    results = []
    exceptions = []

    def try_subscribe(i):
        try:
            ok, msg = cs.subscribe_plan(f"race-user-{i}", "lifetime")
            results.append((ok, msg))
        except Exception as e:
            exceptions.append(e)

    # 10 个并发线程，只能有 1 个成功，其他应返回 "终身版已售罄"
    threads = [threading.Thread(target=try_subscribe, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    successes = [r for r in results if r[0]]
    failures = [r for r in results if not r[0]]
    assert not exceptions, f"并发 subscribe 出现异常: {exceptions}"
    assert len(successes) == 1, f"并发只能有 1 个成功，实际 {len(successes)}"
    assert all("售罄" in m for _, m in failures)
    final_sold = cs.get_lifetime_sold_count()
    assert final_sold == 500, f"最终 sold 应为 500，实际 {final_sold}"
    print(f"   ✓ 10 并发仅 1 成功，sold=500，剩余=0，无超卖")

    # ================================
    # 9. 付费套餐积分扣减并发安全（非负余额）
    # ================================
    print("\n9. 付费套餐积分扣减并发安全（不欠账）")
    # 先开通 monthly，再人工设定 credits = 100 避免赠送积分干扰
    cs.subscribe_plan("race-deduct-user", "monthly")
    import sqlite3 as _s3
    conn = _s3.connect(str(cs.DB_PATH))
    conn.execute("UPDATE user_credits SET credits = 100 WHERE user_id = 'race-deduct-user'")
    conn.commit()
    conn.close()

    # 30 个线程同时扣 deepseekv3（standard, 1 积分），每人扣 100 次
    total_success = 0
    total_fail = 0
    exceptions = []

    def deduct_worker():
        nonlocal total_success, total_fail
        try:
            for _ in range(100):
                ok, _, _ = cs.deduct_credits("race-deduct-user", "deepseekv3")
                if ok:
                    total_success += 1
                else:
                    total_fail += 1
        except Exception as e:
            exceptions.append(e)

    threads = [threading.Thread(target=deduct_worker) for _ in range(30)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not exceptions, f"并发扣减出现异常: {exceptions}"
    u = cs.get_user_credits("race-deduct-user")
    # deepseekv3 每次 1 积分，初始 100
    assert u.credits >= 0, f"余额不应为负，实际 {u.credits}"
    assert total_success + total_fail == 30 * 100
    # 原子条件 UPDATE 保证守恒：已成功扣减数 + 剩余余额 = 初始 100
    assert u.credits + total_success == 100, \
        f"余额 + 已扣 ≠ 初始 100：credits={u.credits} total_success={total_success}"
    print(f"   ✓ 30 线程并发扣减后余额非负={u.credits}，total_success={total_success}, total_fail={total_fail}")

    # ================================
    # 10. get_usage_stats / admin_get_stats
    # ================================
    print("\n10. 统计查询")
    stats = cs.get_usage_stats("monthly-user", days=30)
    assert "total_credits_used" in stats
    assert "profit_margin" in stats
    assert "by_model" in stats
    print(f"   ✓ get_usage_stats 返回 {stats['total_credits_used']} 积分消耗")

    admin = cs.admin_get_stats()
    assert "total_users" in admin
    assert "total_profit" in admin
    assert "plan_distribution" in admin
    print(f"   ✓ admin_get_stats: total_users={admin['total_users']}, distribution={admin['plan_distribution']}")

    # ================================
    # 11. lifetime 价格递增逻辑
    # ================================
    print("\n11. lifetime 价格递增")
    # 重置 batch 以测试涨价逻辑
    conn = _sqlite3.connect(str(cs.DB_PATH))
    conn.execute("UPDATE pricing_config SET value = '1' WHERE key='lifetime_batch'")
    conn.execute("UPDATE pricing_config SET value = '100' WHERE key='lifetime_sold'")
    conn.commit()
    conn.close()

    changed, new_batch = cs.check_lifetime_price_increase()
    assert changed is True and new_batch == 2
    price = cs.get_lifetime_current_price()
    expected = cs.MEMBERSHIP_PLANS["lifetime"]["price"] * (1 + 0.1 * (2 - 1))
    assert abs(price - expected) < 1e-6
    print(f"   ✓ batch=2 时 current_price={price:.2f}（699 * 1.1）")

    # ================================
    # 12. daily_used 跨日自动重置（模拟）
    # ================================
    print("\n12. daily_used 跨日重置")
    cs.subscribe_plan("daily-reset-user", "free")
    cs.deduct_credits("daily-reset-user", "deepseekv3")  # +1
    u = cs.get_user_credits("daily-reset-user")
    assert u.daily_used == 1
    # 模拟：改 daily_reset_date 为昨天
    import sqlite3 as _s3
    conn = _s3.connect(str(cs.DB_PATH))
    conn.execute(
        "UPDATE user_credits SET daily_reset_date='2000-01-01' WHERE user_id='daily-reset-user'"
    )
    conn.commit()
    conn.close()
    # 触发 _check_daily_reset：deduct_credits 内部会调用
    cs.deduct_credits("daily-reset-user", "deepseekv3")  # 重置后首次扣，daily_used 先被重置
    u_after = cs.get_user_credits("daily-reset-user")
    assert u_after.daily_used == 1, (
        f"重置后首次 deduct，daily_used 应为 1，实际 {u_after.daily_used}"
    )
    assert u_after.daily_reset_date == time.strftime("%Y-%m-%d")
    print("   ✓ daily_used 跨日自动重置为 0，deduct 后再次累积")

    # ================================
    # 结果
    # ================================
    print("\n" + "=" * 50)
    if errors:
        print(f"❌ 发现 {len(errors)} 个问题：")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("🎉 credits_system.py 全部测试通过")


if __name__ == "__main__":
    main()
