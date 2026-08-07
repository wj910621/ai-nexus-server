"""
积分定价系统测试
覆盖：积分扣减、并发安全、套餐权限、利润率计算、会员订阅、终身版限量
"""

import os
import sys
import time
import tempfile
import threading
import pytest

sys.path.insert(0, os.path.dirname(__file__))

# 使用临时数据库，避免影响真实数据
from pathlib import Path as _Path

import credits_system

_tmpdir = tempfile.mkdtemp(prefix="ynex_test_credits_")
_test_db_path = _Path(_tmpdir) / "credits.db"
credits_system.DB_PATH = _test_db_path

# 重新初始化数据库
credits_system.init_db()


@pytest.fixture(autouse=True)
def clean_db():
    """每个测试前重建数据库"""
    if _test_db_path.exists():
        _test_db_path.unlink()
    credits_system.init_db()
    yield


# ===========================================================================
# 积分核心功能
# ===========================================================================
class TestGetUserCredits:
    def test_new_user_defaults(self):
        uc = credits_system.get_user_credits("new_user")
        assert uc.user_id == "new_user"
        assert uc.credits == 0
        assert uc.plan == "free"
        assert uc.daily_used == 0
        assert uc.total_used == 0


class TestCheckPlanActive:
    def test_free_always_active(self):
        uc = credits_system.UserCredits(
            user_id="u1", credits=0, plan="free",
            plan_expires_at=None, daily_used=0,
            daily_reset_date="", total_used=0, created_at=time.time()
        )
        assert credits_system.check_plan_active(uc) is True

    def test_lifetime_always_active(self):
        uc = credits_system.UserCredits(
            user_id="u2", credits=0, plan="lifetime",
            plan_expires_at=None, daily_used=0,
            daily_reset_date="", total_used=0, created_at=time.time()
        )
        assert credits_system.check_plan_active(uc) is True

    def test_monthly_active_when_not_expired(self):
        uc = credits_system.UserCredits(
            user_id="u3", credits=0, plan="monthly",
            plan_expires_at=time.time() + 86400, daily_used=0,
            daily_reset_date="", total_used=0, created_at=time.time()
        )
        assert credits_system.check_plan_active(uc) is True

    def test_monthly_expired(self):
        uc = credits_system.UserCredits(
            user_id="u4", credits=0, plan="monthly",
            plan_expires_at=time.time() - 86400, daily_used=0,
            daily_reset_date="", total_used=0, created_at=time.time()
        )
        assert credits_system.check_plan_active(uc) is False

    def test_yearly_active_when_not_expired(self):
        uc = credits_system.UserCredits(
            user_id="u5", credits=0, plan="yearly",
            plan_expires_at=time.time() + 86400 * 365, daily_used=0,
            daily_reset_date="", total_used=0, created_at=time.time()
        )
        assert credits_system.check_plan_active(uc) is True


class TestGetAvailableCredits:
    def test_free_user_daily_limit(self):
        uc = credits_system.UserCredits(
            user_id="u1", credits=0, plan="free",
            plan_expires_at=None, daily_used=3,
            daily_reset_date=credits_system._today_str(),
            total_used=0, created_at=time.time()
        )
        available = credits_system.get_available_credits(uc)
        assert available == 10 - 3  # daily_credits=10, daily_used=3

    def test_free_user_daily_reset(self):
        """日期变化后 daily_used 应重置"""
        uc = credits_system.UserCredits(
            user_id="u1", credits=0, plan="free",
            plan_expires_at=None, daily_used=8,
            daily_reset_date="2000-01-01",  # 旧日期
            total_used=0, created_at=time.time()
        )
        available = credits_system.get_available_credits(uc)
        assert available == 10  # 重置后可用 10

    def test_paid_user_uses_credits_field(self):
        uc = credits_system.UserCredits(
            user_id="u1", credits=500, plan="monthly",
            plan_expires_at=time.time() + 86400, daily_used=0,
            daily_reset_date="", total_used=0, created_at=time.time()
        )
        available = credits_system.get_available_credits(uc)
        assert available == 500


class TestCanUseModel:
    def test_free_user_can_use_free_model(self):
        uc = credits_system.UserCredits(
            user_id="u1", credits=0, plan="free",
            plan_expires_at=None, daily_used=0,
            daily_reset_date="", total_used=0, created_at=time.time()
        )
        ok, msg = credits_system.can_use_model(uc, "sf_qwen3_8b")
        assert ok is True

    def test_free_user_cannot_use_premium(self):
        uc = credits_system.UserCredits(
            user_id="u1", credits=0, plan="free",
            plan_expires_at=None, daily_used=0,
            daily_reset_date="", total_used=0, created_at=time.time()
        )
        ok, msg = credits_system.can_use_model(uc, "deepseekr1")
        assert ok is False
        assert "升级" in msg

    def test_monthly_user_can_use_premium(self):
        uc = credits_system.UserCredits(
            user_id="u1", credits=100, plan="monthly",
            plan_expires_at=time.time() + 86400, daily_used=0,
            daily_reset_date="", total_used=0, created_at=time.time()
        )
        ok, _ = credits_system.can_use_model(uc, "deepseekr1")
        assert ok is True


# ===========================================================================
# 积分扣减
# ===========================================================================
class TestDeductCredits:
    def test_free_model_no_deduction(self):
        credits_system._ensure_user("test_user")
        ok, msg, cost = credits_system.deduct_credits("test_user", "sf_qwen3_8b")
        assert ok is True
        assert cost == 0

    def test_successful_deduction(self):
        credits_system._ensure_user("pay_user")
        credits_system.add_credits("pay_user", 100, "test recharge")
        ok, msg, cost = credits_system.deduct_credits("pay_user", "deepseekv3")
        assert ok is True
        assert cost == 1

    def test_insufficient_credits(self):
        """积分不足时应被拒绝"""
        credits_system._ensure_user("pay_user2")
        # 给少量积分，但设为 monthly 以跳过套餐权限检查
        credits_system.add_credits("pay_user2", 1, "test")
        conn = credits_system._get_db()
        c = conn.cursor()
        c.execute("UPDATE user_credits SET plan = 'monthly', plan_expires_at = ? WHERE user_id = ?",
                  (time.time() + 86400, "pay_user2"))
        conn.commit()
        conn.close()
        # 请求高积分模型
        ok, msg, cost = credits_system.deduct_credits("pay_user2", "nx_claude_opus")
        assert ok is False
        assert "积分不足" in msg

    def test_free_user_daily_limit_enforcement(self):
        """免费用户每日额度耗尽后应被拒绝"""
        credits_system._ensure_user("free_user")
        # 免费用户每天10积分，每次1积分的模型可以调用10次
        for i in range(10):
            ok, _, _ = credits_system.deduct_credits("free_user", "deepseekv3")
            # 注意: 免费用户的 daily_used 会累积
        # 第11次应失败（超出每日额度）
        ok, msg, _ = credits_system.deduct_credits("free_user", "deepseekv3")
        assert ok is False

    def test_deduct_records_transaction(self):
        credits_system._ensure_user("tx_user")
        credits_system.add_credits("tx_user", 100, "test")
        credits_system.deduct_credits("tx_user", "deepseekv3", description="test tx")
        txs = credits_system.get_transactions("tx_user")
        consume_txs = [t for t in txs if t.type == "consume"]
        assert len(consume_txs) >= 1


class TestAddCredits:
    def test_add_credits(self):
        credits_system._ensure_user("add_user")
        credits_system.add_credits("add_user", 50, "test add")
        uc = credits_system.get_user_credits("add_user")
        assert uc.credits == 50

    def test_add_credits_accumulates(self):
        credits_system._ensure_user("acc_user")
        credits_system.add_credits("acc_user", 30, "first")
        credits_system.add_credits("acc_user", 20, "second")
        uc = credits_system.get_user_credits("acc_user")
        assert uc.credits == 50


# ===========================================================================
# 成本计算
# ===========================================================================
class TestCalculateCreditCost:
    def test_known_model_fixed_price(self):
        assert credits_system.calculate_credit_cost("deepseekv3") == 1
        assert credits_system.calculate_credit_cost("nx_claude_opus") == 15

    def test_free_model_zero_cost(self):
        assert credits_system.calculate_credit_cost("sf_qwen3_8b") == 0

    def test_unknown_model_defaults(self):
        """未知模型应返回默认价格"""
        cost = credits_system.calculate_credit_cost("nonexistent_model")
        assert cost == 2  # 默认值

    def test_dynamic_cost_calculation(self):
        """有 MODEL_COSTS 但无固定价格时应动态计算"""
        # 移除一个模型的固定价格来测试动态计算（模拟）
        cost = credits_system.calculate_credit_cost("qwen3", input_tokens=2000, output_tokens=2000)
        assert cost >= 1  # 至少1积分


class TestCalculateCostPrice:
    def test_known_model(self):
        cost = credits_system.calculate_cost_price("deepseekv3", 1_000_000, 1_000_000)
        assert cost == 5.0  # input=1, output=4

    def test_unknown_model(self):
        cost = credits_system.calculate_cost_price("nonexistent", 1000, 1000)
        assert cost == 0.0

    def test_zero_tokens(self):
        cost = credits_system.calculate_cost_price("deepseekv3", 0, 0)
        assert cost == 0.0


class TestGetProfitMargin:
    def test_known_model(self):
        margin = credits_system.get_profit_margin("deepseekv3")
        assert margin is not None
        assert 0 < margin < 1

    def test_free_model_with_zero_cost(self):
        margin = credits_system.get_profit_margin("ark_dsv4p")
        assert margin == 1.0  # 零成本 = 100% 利润

    def test_unknown_model(self):
        margin = credits_system.get_profit_margin("nonexistent")
        assert margin is None


# ===========================================================================
# 会员订阅
# ===========================================================================
class TestSubscribePlan:
    def test_subscribe_monthly(self):
        credits_system._ensure_user("sub_user")
        ok, msg = credits_system.subscribe_plan("sub_user", "monthly")
        assert ok is True
        uc = credits_system.get_user_credits("sub_user")
        assert uc.plan == "monthly"
        assert uc.credits == 1000  # monthly 给 1000 积分

    def test_subscribe_yearly(self):
        credits_system._ensure_user("year_user")
        ok, _ = credits_system.subscribe_plan("year_user", "yearly")
        assert ok is True
        uc = credits_system.get_user_credits("year_user")
        assert uc.plan == "yearly"
        assert uc.credits == 15000

    def test_subscribe_nonexistent_plan(self):
        ok, msg = credits_system.subscribe_plan("user1", "nonexistent")
        assert ok is False
        assert "不存在" in msg

    def test_lifetime_limit_enforcement(self):
        """终身版售罄后不应再出售"""
        # 设置 lifetime_sold 接近限额
        conn = credits_system._get_db()
        c = conn.cursor()
        # 将 lifetime_sold 设为 total_limit - 1
        limit = credits_system.MEMBERSHIP_PLANS["lifetime"]["total_limit"]
        c.execute("UPDATE pricing_config SET value = ? WHERE key = 'lifetime_sold'",
                  (str(limit - 1),))
        conn.commit()
        conn.close()

        # 下一个应成功
        credits_system._ensure_user("lt_user_1")
        ok1, _ = credits_system.subscribe_plan("lt_user_1", "lifetime")
        assert ok1 is True

        # 再下一个应失败（售罄）
        credits_system._ensure_user("lt_user_2")
        ok2, msg2 = credits_system.subscribe_plan("lt_user_2", "lifetime")
        assert ok2 is False
        assert "售罄" in msg2


# ===========================================================================
# 终身版定价
# ===========================================================================
class TestLifetimePricing:
    def test_base_price(self):
        price = credits_system.get_lifetime_current_price()
        assert price == credits_system.MEMBERSHIP_PLANS["lifetime"]["price"]

    def test_remaining_count(self):
        remaining = credits_system.get_lifetime_remaining()
        assert remaining > 0
        assert remaining <= credits_system.MEMBERSHIP_PLANS["lifetime"]["total_limit"]


# ===========================================================================
# 并发扣减安全
# ===========================================================================
class TestConcurrentDeduction:
    def test_concurrent_deductions_no_overdraft(self):
        """并发扣减不应导致积分余额为负"""
        user_id = "concurrent_user"
        credits_system._ensure_user(user_id)
        # 给 5 积分
        credits_system.add_credits(user_id, 5, "test")

        errors = []
        results = []

        def deduct():
            try:
                ok, msg, cost = credits_system.deduct_credits(
                    user_id, "deepseekv3"  # 1 积分/次
                )
                results.append(ok)
            except Exception as e:
                errors.append(e)

        # 发起 10 个并发扣减请求，只有5个应该成功
        threads = [threading.Thread(target=deduct) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"并发错误: {errors}"

        # 验证余额不为负
        uc = credits_system.get_user_credits(user_id)
        assert uc.credits >= 0, f"余额不应为负: {uc.credits}"


# ===========================================================================
# 交易记录
# ===========================================================================
class TestTransactions:
    def test_get_transactions_empty(self):
        txs = credits_system.get_transactions("no_such_user")
        assert txs == []

    def test_transactions_recorded(self):
        credits_system._ensure_user("tx_user")
        credits_system.add_credits("tx_user", 100, "充值")
        credits_system.deduct_credits("tx_user", "deepseekv3")
        txs = credits_system.get_transactions("tx_user")
        assert len(txs) >= 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
