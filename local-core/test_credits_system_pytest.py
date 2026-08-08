"""
pytest 测试文件 - credits_system.py
覆盖：积分定价、模型访问控制、套餐激活、可用积分、扣费/充值、订阅、利润率
"""

import sys
import os
import time
import threading
from datetime import datetime, timedelta

import pytest

# ---------------------------------------------------------------------------
# 确保 local-core 在 sys.path 中
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _redirect_db(tmp_path, monkeypatch):
    """每个测试使用独立的临时数据库。"""
    db_file = tmp_path / "credits.db"
    import credits_system
    monkeypatch.setattr(credits_system, "DB_PATH", db_file)
    credits_system.init_db()
    yield


# ===================================================================
# 1. calculate_credit_cost
# ===================================================================
class TestCalculateCreditCost:
    def test_free_models_return_zero(self):
        """免费模型 cost == 0"""
        import credits_system as cs
        for model in ["ark_dsv4p", "ark_dsv4f", "ark_dsv32", "sf_qwen3_8b",
                      "sf_deepseek_v3_free", "sf_hunyuan_a13b"]:
            assert cs.calculate_credit_cost(model) == 0, f"{model} should be free"

    def test_known_models_return_correct_price(self):
        """已知模型返回 MODEL_CREDIT_PRICES 中定义的价格"""
        import credits_system as cs
        assert cs.calculate_credit_cost("deepseekv3") == 1
        assert cs.calculate_credit_cost("nx_gpt5") == 10
        assert cs.calculate_credit_cost("nx_claude_opus") == 15
        assert cs.calculate_credit_cost("claude4") == 12
        assert cs.calculate_credit_cost("glm4plus") == 1

    def test_unknown_models_return_default_2(self):
        """未知模型（不在 MODEL_CREDIT_PRICES 也不在 MODEL_COSTS）返回默认值 2"""
        import credits_system as cs
        assert cs.calculate_credit_cost("totally_unknown_model_xyz") == 2

    def test_model_in_costs_dynamic_calculation(self):
        """在 MODEL_COSTS 但不在 MODEL_CREDIT_PRICES 中的模型，按成本动态计算"""
        import credits_system as cs
        # qwen3 在 MODEL_CREDIT_PRICES 中 = 2，无法触发动态路径
        # 使用 token 参数触发动态计算（虽然 qwen3 有固定价格，这里验证逻辑分支）
        # 对于一个只在 MODEL_COSTS 不在 MODEL_CREDIT_PRICES 的模型
        # 没有这样的模型存在，所以我们验证免费模型带 token 的路径
        # 火山引擎模型 cost=0, 即使传 token 也返回 0
        assert cs.calculate_credit_cost("ark_dsv4p", 2000, 2000) == 0


# ===================================================================
# 2. can_use_model
# ===================================================================
class TestCanUseModel:
    def test_guest_cannot_use_flagship(self):
        """免费/free 套餐不能使用旗舰模型"""
        import credits_system as cs
        uc = cs.UserCredits(
            user_id="guest", credits=0, plan="free",
            plan_expires_at=None, daily_used=0,
            daily_reset_date="", total_used=0, created_at=time.time(),
        )
        ok, msg = cs.can_use_model(uc, "gpt4o")
        assert ok is False
        assert "升级" in msg

    def test_guest_can_use_free_model(self):
        """免费套餐可以使用 free tier 模型"""
        import credits_system as cs
        uc = cs.UserCredits(
            user_id="guest", credits=0, plan="free",
            plan_expires_at=None, daily_used=0,
            daily_reset_date="", total_used=0, created_at=time.time(),
        )
        ok, msg = cs.can_use_model(uc, "ark_dsv4p")
        assert ok is True

    def test_guest_can_use_standard_model(self):
        """免费套餐可以使用 standard tier 模型"""
        import credits_system as cs
        uc = cs.UserCredits(
            user_id="guest", credits=0, plan="free",
            plan_expires_at=None, daily_used=0,
            daily_reset_date="", total_used=0, created_at=time.time(),
        )
        ok, msg = cs.can_use_model(uc, "deepseekv3")
        assert ok is True

    def test_monthly_can_use_flagship(self):
        """月度套餐可以使用旗舰模型"""
        import credits_system as cs
        uc = cs.UserCredits(
            user_id="u", credits=100, plan="monthly",
            plan_expires_at=time.time() + 86400, daily_used=0,
            daily_reset_date="", total_used=0, created_at=time.time(),
        )
        ok, msg = cs.can_use_model(uc, "gpt4o")
        assert ok is True

    def test_lifetime_can_use_all(self):
        """终身版可以使用所有模型"""
        import credits_system as cs
        uc = cs.UserCredits(
            user_id="u", credits=50000, plan="lifetime",
            plan_expires_at=time.time() + 999999, daily_used=0,
            daily_reset_date="", total_used=0, created_at=time.time(),
        )
        ok, _ = cs.can_use_model(uc, "nx_claude_opus")
        assert ok is True


# ===================================================================
# 3. check_plan_active
# ===================================================================
class TestCheckPlanActive:
    def test_free_is_always_active(self):
        """免费套餐始终激活"""
        import credits_system as cs
        uc = cs.UserCredits(
            user_id="u", credits=0, plan="free",
            plan_expires_at=None, daily_used=0,
            daily_reset_date="", total_used=0, created_at=time.time(),
        )
        assert cs.check_plan_active(uc) is True

    def test_lifetime_is_always_active(self):
        """终身版始终激活"""
        import credits_system as cs
        uc = cs.UserCredits(
            user_id="u", credits=100, plan="lifetime",
            plan_expires_at=None, daily_used=0,
            daily_reset_date="", total_used=0, created_at=time.time(),
        )
        assert cs.check_plan_active(uc) is True

    def test_expired_monthly_not_active(self):
        """过期月度套餐不激活"""
        import credits_system as cs
        uc = cs.UserCredits(
            user_id="u", credits=100, plan="monthly",
            plan_expires_at=time.time() - 3600,  # 1小时前过期
            daily_used=0, daily_reset_date="",
            total_used=0, created_at=time.time(),
        )
        assert cs.check_plan_active(uc) is False

    def test_active_monthly_is_active(self):
        """未过期月度套餐激活"""
        import credits_system as cs
        uc = cs.UserCredits(
            user_id="u", credits=100, plan="monthly",
            plan_expires_at=time.time() + 86400,  # 1天后过期
            daily_used=0, daily_reset_date="",
            total_used=0, created_at=time.time(),
        )
        assert cs.check_plan_active(uc) is True

    def test_expired_yearly_not_active(self):
        """过期年度套餐不激活"""
        import credits_system as cs
        uc = cs.UserCredits(
            user_id="u", credits=100, plan="yearly",
            plan_expires_at=time.time() - 86400,
            daily_used=0, daily_reset_date="",
            total_used=0, created_at=time.time(),
        )
        assert cs.check_plan_active(uc) is False


# ===================================================================
# 4. get_available_credits
# ===================================================================
class TestGetAvailableCredits:
    def test_free_plan_daily_limit(self):
        """免费套餐返回每日限额减去已用"""
        import credits_system as cs
        today = datetime.now().strftime("%Y-%m-%d")
        uc = cs.UserCredits(
            user_id="u", credits=0, plan="free",
            plan_expires_at=None, daily_used=3,
            daily_reset_date=today, total_used=0, created_at=time.time(),
        )
        available = cs.get_available_credits(uc)
        # daily_credits=10, daily_used=3 -> 7
        assert available == 7

    def test_free_plan_daily_exhausted(self):
        """免费套餐每日额度用尽"""
        import credits_system as cs
        today = datetime.now().strftime("%Y-%m-%d")
        uc = cs.UserCredits(
            user_id="u", credits=0, plan="free",
            plan_expires_at=None, daily_used=10,
            daily_reset_date=today, total_used=0, created_at=time.time(),
        )
        assert cs.get_available_credits(uc) == 0

    def test_paid_plan_returns_credits(self):
        """付费套餐直接返回 credits 余额"""
        import credits_system as cs
        uc = cs.UserCredits(
            user_id="u", credits=500, plan="monthly",
            plan_expires_at=time.time() + 86400, daily_used=0,
            daily_reset_date="", total_used=0, created_at=time.time(),
        )
        assert cs.get_available_credits(uc) == 500

    def test_free_plan_daily_reset_on_new_day(self):
        """跨天时 daily_used 应被重置"""
        import credits_system as cs
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        uc = cs.UserCredits(
            user_id="u", credits=0, plan="free",
            plan_expires_at=None, daily_used=10,
            daily_reset_date=yesterday, total_used=0, created_at=time.time(),
        )
        available = cs.get_available_credits(uc)
        # 新的一天，daily_used 被重置为 0，可用 = 10
        assert available == 10


# ===================================================================
# 5. deduct_credits
# ===================================================================
class TestDeductCredits:
    def test_insufficient_credits_returns_false(self):
        """积分不足时应拒绝扣费"""
        import credits_system as cs
        # 先确保用户存在且为 free plan
        cs._ensure_user("u_poor")
        # free plan 每日 10 积分，deepseekv3 = 1 积分，扣 10 次后应失败
        for _ in range(10):
            cs.deduct_credits("u_poor", "deepseekv3")
        ok, msg, cost = cs.deduct_credits("u_poor", "deepseekv3")
        assert ok is False

    def test_free_model_costs_zero(self):
        """免费模型扣 0 积分"""
        import credits_system as cs
        cs._ensure_user("u_free_model")
        ok, msg, cost = cs.deduct_credits("u_free_model", "ark_dsv4p")
        assert ok is True
        assert cost == 0

    def test_successful_deduct(self):
        """正常扣费成功"""
        import credits_system as cs
        cs._ensure_user("u_deduct_ok")
        ok, msg, cost = cs.deduct_credits("u_deduct_ok", "deepseekv3")
        assert ok is True
        assert cost == 1

    def test_concurrent_safety(self):
        """并发扣费安全性：余额不足时不应出现负数"""
        import credits_system as cs
        user_id = "u_concurrent"
        # 设置用户为 monthly，给 5 积分
        cs._ensure_user(user_id)
        conn = cs._get_db()
        c = conn.cursor()
        c.execute("UPDATE user_credits SET plan='monthly', credits=5, plan_expires_at=? WHERE user_id=?",
                  (time.time() + 86400, user_id))
        conn.commit()
        conn.close()

        # deepseekr1 = 5 积分，并发 10 次只应有 1 次成功
        results = []
        barrier = threading.Barrier(10)

        def try_deduct():
            barrier.wait()
            ok, msg, cost = cs.deduct_credits(user_id, "deepseekr1")
            results.append(ok)

        threads = [threading.Thread(target=try_deduct) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 只有 1 次应成功（5积分 / 5积分 = 1次）
        success_count = sum(1 for r in results if r)
        assert success_count == 1

        # 确认余额没有变负
        uc = cs.get_user_credits(user_id)
        assert uc.credits >= 0


# ===================================================================
# 6. add_credits
# ===================================================================
class TestAddCredits:
    def test_increases_user_credits(self):
        """充值增加用户积分"""
        import credits_system as cs
        cs._ensure_user("u_add")
        uc_before = cs.get_user_credits("u_add")
        before = uc_before.credits

        ok = cs.add_credits("u_add", 100, "测试充值")
        assert ok is True

        uc_after = cs.get_user_credits("u_add")
        assert uc_after.credits == before + 100

    def test_add_zero_credits(self):
        """充值 0 不改变余额"""
        import credits_system as cs
        cs._ensure_user("u_add0")
        uc_before = cs.get_user_credits("u_add0")
        before = uc_before.credits

        cs.add_credits("u_add0", 0)
        uc_after = cs.get_user_credits("u_add0")
        assert uc_after.credits == before


# ===================================================================
# 7. subscribe_plan
# ===================================================================
class TestSubscribePlan:
    def test_invalid_plan_returns_error(self):
        """无效套餐返回错误"""
        import credits_system as cs
        cs._ensure_user("u_bad_plan")
        ok, msg = cs.subscribe_plan("u_bad_plan", "nonexistent_plan")
        assert ok is False
        assert "不存在" in msg

    def test_monthly_subscription(self):
        """月度订阅成功"""
        import credits_system as cs
        cs._ensure_user("u_monthly")
        ok, msg = cs.subscribe_plan("u_monthly", "monthly")
        assert ok is True
        uc = cs.get_user_credits("u_monthly")
        assert uc.plan == "monthly"
        assert uc.plan_expires_at is not None
        assert uc.credits == 1000  # price_credits

    def test_lifetime_sold_out_protection(self):
        """终身版售罄保护：售出达到 total_limit 后拒绝新购买"""
        import credits_system as cs
        # lifetime total_limit = 500
        # 先将 lifetime_sold 设置为 500
        conn = cs._get_db()
        c = conn.cursor()
        c.execute("UPDATE pricing_config SET value = '500' WHERE key = 'lifetime_sold'")
        conn.commit()
        conn.close()

        cs._ensure_user("u_late")
        ok, msg = cs.subscribe_plan("u_late", "lifetime")
        assert ok is False
        assert "售罄" in msg

    def test_free_plan_subscription(self):
        """开通免费套餐"""
        import credits_system as cs
        cs._ensure_user("u_free_sub")
        # 先给用户一个月度套餐
        conn = cs._get_db()
        c = conn.cursor()
        c.execute("UPDATE user_credits SET plan='monthly', plan_expires_at=? WHERE user_id=?",
                  (time.time() + 86400, "u_free_sub"))
        conn.commit()
        conn.close()

        ok, msg = cs.subscribe_plan("u_free_sub", "free")
        assert ok is True
        uc = cs.get_user_credits("u_free_sub")
        assert uc.plan == "free"


# ===================================================================
# 8. get_profit_margin
# ===================================================================
class TestGetProfitMargin:
    def test_known_model_returns_margin(self):
        """已知模型返回正确的利润率"""
        import credits_system as cs
        margin = cs.get_profit_margin("deepseekv3")
        assert margin is not None
        assert 0 < margin < 1  # 利润率在 0-1 之间

    def test_flagship_model_margin(self):
        """旗舰模型利润率在合理范围内"""
        import credits_system as cs
        margin = cs.get_profit_margin("gpt4o")
        assert margin is not None
        assert 0.4 < margin < 0.8  # 大致范围

    def test_unknown_model_returns_none(self):
        """未知模型返回 None"""
        import credits_system as cs
        assert cs.get_profit_margin("unknown_model") is None

    def test_free_model_with_zero_cost(self):
        """成本为 0 的免费模型利润率为 1.0"""
        import credits_system as cs
        margin = cs.get_profit_margin("ark_dsv4p")
        assert margin == 1.0

    def test_free_model_with_nonzero_cost(self):
        """价格为 0 但成本非 0 的模型返回 None（无法计算利润率）"""
        import credits_system as cs
        # sf_deepseek_v3_free: price=0, cost=(input=1, output=4) nonzero
        margin = cs.get_profit_margin("sf_deepseek_v3_free")
        assert margin is None
