"""
积分计费系统测试
- 积分扣减与充值
- 会员套餐管理
- 免费用户日限额
- 模型权限检查
- 定价计算
- 终身版限量与涨价
- 并发安全（原子扣减）
"""

import os
import sys
import tempfile
import shutil
import time
import unittest
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

TEST_DATA_DIR = tempfile.mkdtemp(prefix="test_credits_")


def _setup_test_env():
    os.makedirs(os.path.join(TEST_DATA_DIR, "data"), exist_ok=True)
    original_cwd = os.getcwd()
    os.chdir(TEST_DATA_DIR)
    return original_cwd


def _teardown_test_env(original_cwd):
    os.chdir(original_cwd)
    shutil.rmtree(TEST_DATA_DIR, ignore_errors=True)


class TestInitDb(unittest.TestCase):
    """数据库初始化测试"""

    @classmethod
    def setUpClass(cls):
        cls.original_cwd = _setup_test_env()
        import importlib
        import credits_system
        importlib.reload(credits_system)
        cls.cs = credits_system

    @classmethod
    def tearDownClass(cls):
        _teardown_test_env(cls.original_cwd)

    def test_db_file_created(self):
        self.assertTrue(os.path.exists("data/credits.db"))

    def test_user_credits_default(self):
        get_user_credits = self.cs.get_user_credits
        uc = get_user_credits("new_user_001")
        self.assertEqual(uc.user_id, "new_user_001")
        self.assertEqual(uc.credits, 0)
        self.assertEqual(uc.plan, "free")
        self.assertEqual(uc.daily_used, 0)


class TestAddCredits(unittest.TestCase):
    """积分充值测试"""

    @classmethod
    def setUpClass(cls):
        cls.original_cwd = _setup_test_env()
        import importlib
        import credits_system
        importlib.reload(credits_system)
        cls.cs = credits_system

    @classmethod
    def tearDownClass(cls):
        _teardown_test_env(cls.original_cwd)

    def test_add_credits_increases_balance(self):
        add_credits = self.cs.add_credits
        get_user_credits = self.cs.get_user_credits
        user_id = "add_test_001"
        add_credits(user_id, 100)
        uc = get_user_credits(user_id)
        self.assertEqual(uc.credits, 100)

    def test_add_credits_multiple_times(self):
        add_credits = self.cs.add_credits
        get_user_credits = self.cs.get_user_credits
        user_id = "add_test_002"
        add_credits(user_id, 50)
        add_credits(user_id, 30)
        add_credits(user_id, 20)
        uc = get_user_credits(user_id)
        self.assertEqual(uc.credits, 100)

    def test_add_credits_records_transaction(self):
        add_credits = self.cs.add_credits
        get_transactions = self.cs.get_transactions
        user_id = "add_test_003"
        add_credits(user_id, 200, "测试充值", "recharge")
        txs = get_transactions(user_id)
        self.assertEqual(len(txs), 1)
        self.assertEqual(txs[0].type, "recharge")
        self.assertEqual(txs[0].amount, 200)
        self.assertEqual(txs[0].description, "测试充值")


class TestDeductCredits(unittest.TestCase):
    """积分扣减测试"""

    @classmethod
    def setUpClass(cls):
        cls.original_cwd = _setup_test_env()
        import importlib
        import credits_system
        importlib.reload(credits_system)
        cls.cs = credits_system

    @classmethod
    def tearDownClass(cls):
        _teardown_test_env(cls.original_cwd)

    def test_deduct_from_paid_plan(self):
        add_credits = self.cs.add_credits
        deduct_credits = self.cs.deduct_credits
        get_user_credits = self.cs.get_user_credits
        subscribe_plan = self.cs.subscribe_plan
        user_id = "deduct_test_001"
        subscribe_plan(user_id, "monthly")
        add_credits(user_id, 50)
        ok, msg, cost = deduct_credits(user_id, "deepseekv3", 1000, 1000)
        self.assertTrue(ok)
        self.assertEqual(cost, 1)
        uc = get_user_credits(user_id)
        self.assertEqual(uc.credits, 50 + 1000 - 1)

    def test_deduct_insufficient_credits(self):
        add_credits = self.cs.add_credits
        deduct_credits = self.cs.deduct_credits
        get_user_credits = self.cs.get_user_credits
        subscribe_plan = self.cs.subscribe_plan
        user_id = "deduct_test_002"
        subscribe_plan(user_id, "monthly")
        uc = get_user_credits(user_id)
        remaining = uc.credits
        deduct_credits(user_id, "nx_claude_opus", 1000, 1000)
        while True:
            uc = get_user_credits(user_id)
            if uc.credits < 15:
                break
            deduct_credits(user_id, "nx_claude_opus", 1000, 1000)
        ok, msg, cost = deduct_credits(user_id, "nx_claude_opus", 10000, 10000)
        self.assertFalse(ok)
        self.assertIn("积分不足", msg)
        self.assertEqual(cost, 0)

    def test_deduct_free_model_no_cost(self):
        deduct_credits = self.cs.deduct_credits
        get_user_credits = self.cs.get_user_credits
        user_id = "deduct_test_003"
        ok, msg, cost = deduct_credits(user_id, "sf_qwen3_8b", 1000, 1000)
        self.assertTrue(ok)
        self.assertEqual(cost, 0)
        self.assertIn("免费", msg)

    def test_deduct_records_transaction(self):
        add_credits = self.cs.add_credits
        deduct_credits = self.cs.deduct_credits
        get_transactions = self.cs.get_transactions
        subscribe_plan = self.cs.subscribe_plan
        user_id = "deduct_test_004"
        subscribe_plan(user_id, "monthly")
        add_credits(user_id, 100)
        deduct_credits(user_id, "deepseekv3", 2000, 2000, "测试对话")
        txs = [t for t in get_transactions(user_id) if t.type == "consume"]
        self.assertEqual(len(txs), 1)
        self.assertEqual(txs[0].model, "deepseekv3")
        self.assertIn("测试对话", txs[0].description)


class TestFreePlanDailyLimit(unittest.TestCase):
    """免费套餐日限额测试"""

    @classmethod
    def setUpClass(cls):
        cls.original_cwd = _setup_test_env()
        import importlib
        import credits_system
        importlib.reload(credits_system)
        cls.cs = credits_system

    @classmethod
    def tearDownClass(cls):
        _teardown_test_env(cls.original_cwd)

    def test_free_plan_daily_limit(self):
        deduct_credits = self.cs.deduct_credits
        get_available_credits = self.cs.get_available_credits
        get_user_credits = self.cs.get_user_credits
        user_id = "free_test_001"
        for _ in range(5):
            deduct_credits(user_id, "deepseekv3", 1000, 1000)
        uc = get_user_credits(user_id)
        self.assertEqual(uc.plan, "free")
        self.assertEqual(uc.daily_used, 5)
        available = get_available_credits(uc)
        self.assertEqual(available, 5)

    def test_free_plan_exceeds_daily_limit(self):
        deduct_credits = self.cs.deduct_credits
        get_user_credits = self.cs.get_user_credits
        user_id = "free_test_002"
        for _ in range(10):
            deduct_credits(user_id, "deepseekv3", 1000, 1000)
        ok, msg, cost = deduct_credits(user_id, "deepseekv3", 1000, 1000)
        self.assertFalse(ok)
        self.assertIn("积分不足", msg)

    def test_free_plan_total_used_accumulates(self):
        deduct_credits = self.cs.deduct_credits
        get_user_credits = self.cs.get_user_credits
        user_id = "free_test_003"
        for _ in range(5):
            deduct_credits(user_id, "deepseekv3", 1000, 1000)
        uc = get_user_credits(user_id)
        self.assertEqual(uc.total_used, 5)


class TestCanUseModel(unittest.TestCase):
    """模型权限检查测试"""

    @classmethod
    def setUpClass(cls):
        cls.original_cwd = _setup_test_env()
        import importlib
        import credits_system
        importlib.reload(credits_system)
        cls.cs = credits_system

    @classmethod
    def tearDownClass(cls):
        _teardown_test_env(cls.original_cwd)

    def test_free_plan_cannot_use_premium(self):
        get_user_credits = self.cs.get_user_credits
        can_use_model = self.cs.can_use_model
        user_id = "model_test_001"
        uc = get_user_credits(user_id)
        ok, msg = can_use_model(uc, "deepseekr1")
        self.assertFalse(ok)
        self.assertIn("不支持该模型", msg)

    def test_free_plan_can_use_free_tier(self):
        get_user_credits = self.cs.get_user_credits
        can_use_model = self.cs.can_use_model
        user_id = "model_test_002"
        uc = get_user_credits(user_id)
        ok, msg = can_use_model(uc, "sf_qwen3_8b")
        self.assertTrue(ok)

    def test_monthly_plan_can_use_all_tiers(self):
        get_user_credits = self.cs.get_user_credits
        subscribe_plan = self.cs.subscribe_plan
        can_use_model = self.cs.can_use_model
        user_id = "model_test_003"
        subscribe_plan(user_id, "monthly")
        uc = get_user_credits(user_id)
        for model in ["sf_qwen3_8b", "deepseekv3", "deepseekr1", "nx_gpt5"]:
            ok, _ = can_use_model(uc, model)
            self.assertTrue(ok, f"monthly 应能使用 {model}")


class TestSubscriptionPlans(unittest.TestCase):
    """会员套餐测试"""

    @classmethod
    def setUpClass(cls):
        cls.original_cwd = _setup_test_env()
        import importlib
        import credits_system
        importlib.reload(credits_system)
        cls.cs = credits_system

    @classmethod
    def tearDownClass(cls):
        _teardown_test_env(cls.original_cwd)

    def test_subscribe_monthly(self):
        subscribe_plan = self.cs.subscribe_plan
        get_user_credits = self.cs.get_user_credits
        user_id = "sub_test_001"
        ok, msg = subscribe_plan(user_id, "monthly")
        self.assertTrue(ok)
        self.assertIn("成功开通", msg)
        uc = get_user_credits(user_id)
        self.assertEqual(uc.plan, "monthly")
        self.assertEqual(uc.credits, 1000)
        self.assertIsNotNone(uc.plan_expires_at)
        self.assertGreater(uc.plan_expires_at, time.time())

    def test_subscribe_yearly(self):
        subscribe_plan = self.cs.subscribe_plan
        get_user_credits = self.cs.get_user_credits
        user_id = "sub_test_002"
        ok, msg = subscribe_plan(user_id, "yearly")
        self.assertTrue(ok)
        uc = get_user_credits(user_id)
        self.assertEqual(uc.plan, "yearly")
        self.assertEqual(uc.credits, 15000)

    def test_subscribe_lifetime(self):
        subscribe_plan = self.cs.subscribe_plan
        get_user_credits = self.cs.get_user_credits
        user_id = "sub_test_003"
        ok, msg = subscribe_plan(user_id, "lifetime")
        self.assertTrue(ok)
        uc = get_user_credits(user_id)
        self.assertEqual(uc.plan, "lifetime")
        self.assertEqual(uc.credits, 50000)

    def test_subscribe_invalid_plan(self):
        subscribe_plan = self.cs.subscribe_plan
        ok, msg = subscribe_plan("sub_test_004", "invalid_plan")
        self.assertFalse(ok)
        self.assertIn("套餐不存在", msg)

    def test_check_plan_active_free(self):
        get_user_credits = self.cs.get_user_credits
        check_plan_active = self.cs.check_plan_active
        user_id = "sub_test_005"
        uc = get_user_credits(user_id)
        self.assertTrue(check_plan_active(uc))

    def test_check_plan_active_lifetime(self):
        subscribe_plan = self.cs.subscribe_plan
        get_user_credits = self.cs.get_user_credits
        check_plan_active = self.cs.check_plan_active
        user_id = "sub_test_006"
        subscribe_plan(user_id, "lifetime")
        uc = get_user_credits(user_id)
        self.assertTrue(check_plan_active(uc))


class TestCreditCostCalculation(unittest.TestCase):
    """定价计算测试"""

    @classmethod
    def setUpClass(cls):
        cls.original_cwd = _setup_test_env()
        import importlib
        import credits_system
        importlib.reload(credits_system)
        cls.cs = credits_system

    @classmethod
    def tearDownClass(cls):
        _teardown_test_env(cls.original_cwd)

    def test_fixed_price_models(self):
        calculate_credit_cost = self.cs.calculate_credit_cost
        self.assertEqual(calculate_credit_cost("deepseekv3"), 1)
        self.assertEqual(calculate_credit_cost("deepseekr1"), 5)
        self.assertEqual(calculate_credit_cost("nx_gpt5"), 10)

    def test_free_models_zero_cost(self):
        calculate_credit_cost = self.cs.calculate_credit_cost
        for model in ["sf_qwen3_8b", "ark_dsv4p", "sf_deepseek_v3_free"]:
            self.assertEqual(calculate_credit_cost(model), 0, f"{model} 应为0积分")

    def test_unknown_model_default(self):
        calculate_credit_cost = self.cs.calculate_credit_cost
        self.assertEqual(calculate_credit_cost("unknown_model_xyz"), 2)

    def test_cost_price_calculation(self):
        calculate_cost_price = self.cs.calculate_cost_price
        cost = calculate_cost_price("deepseekv3", 1000000, 1000000)
        self.assertEqual(cost, 5.0)

    def test_profit_margin(self):
        get_profit_margin = self.cs.get_profit_margin
        margin = get_profit_margin("deepseekv3")
        self.assertIsNotNone(margin)
        self.assertGreater(margin, 0)
        self.assertLess(margin, 1)


class TestLifetimeLimitedSale(unittest.TestCase):
    """终身版限量销售测试"""

    @classmethod
    def setUpClass(cls):
        cls.original_cwd = _setup_test_env()
        import importlib
        import credits_system
        importlib.reload(credits_system)
        cls.cs = credits_system

    @classmethod
    def tearDownClass(cls):
        _teardown_test_env(cls.original_cwd)

    def test_lifetime_remaining(self):
        get_lifetime_remaining = self.cs.get_lifetime_remaining
        remaining = get_lifetime_remaining()
        self.assertGreater(remaining, 0)

    def test_lifetime_sold_count_increments(self):
        subscribe_plan = self.cs.subscribe_plan
        get_lifetime_sold_count = self.cs.get_lifetime_sold_count
        before = get_lifetime_sold_count()
        subscribe_plan("life_test_001", "lifetime")
        after = get_lifetime_sold_count()
        self.assertEqual(after, before + 1)

    def test_lifetime_current_price(self):
        get_lifetime_current_price = self.cs.get_lifetime_current_price
        price = get_lifetime_current_price()
        self.assertEqual(price, 699.0)

    def test_price_increase_after_batch(self):
        check_lifetime_price_increase = self.cs.check_lifetime_price_increase
        get_current_lifetime_batch = self.cs.get_current_lifetime_batch
        get_lifetime_current_price = self.cs.get_lifetime_current_price
        subscribe_plan = self.cs.subscribe_plan
        get_lifetime_sold_count = self.cs.get_lifetime_sold_count
        base_price = self.cs.MEMBERSHIP_PLANS["lifetime"]["price"]
        batch_before = get_current_lifetime_batch()
        for i in range(100):
            subscribe_plan(f"batch_test_{i}", "lifetime")
        increased, new_batch = check_lifetime_price_increase()
        self.assertTrue(increased)
        self.assertEqual(new_batch, batch_before + 1)
        new_price = get_lifetime_current_price()
        self.assertEqual(new_price, base_price * 1.1)


class TestConcurrencySafety(unittest.TestCase):
    """并发安全测试"""

    @classmethod
    def setUpClass(cls):
        cls.original_cwd = _setup_test_env()
        import importlib
        import credits_system
        importlib.reload(credits_system)
        cls.cs = credits_system

    @classmethod
    def tearDownClass(cls):
        _teardown_test_env(cls.original_cwd)

    def test_concurrent_deduct_no_negative_balance(self):
        add_credits = self.cs.add_credits
        deduct_credits = self.cs.deduct_credits
        get_user_credits = self.cs.get_user_credits
        subscribe_plan = self.cs.subscribe_plan
        user_id = "concurrency_test_001"
        subscribe_plan(user_id, "monthly")
        add_credits(user_id, 20)
        num_threads = 10
        results = []
        errors = []

        def worker(tid):
            try:
                ok, msg, cost = deduct_credits(user_id, "deepseekv3", 1000, 1000)
                results.append((tid, ok, cost))
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        self.assertEqual(len(errors), 0, f"并发错误: {errors}")
        uc = get_user_credits(user_id)
        self.assertGreaterEqual(uc.credits, 0, "余额不应为负")
        success_count = sum(1 for _, ok, _ in results if ok)
        expected_initial = 20 + 1000
        self.assertEqual(uc.credits + success_count, expected_initial)

    def test_concurrent_free_plan_no_over_limit(self):
        deduct_credits = self.cs.deduct_credits
        get_user_credits = self.cs.get_user_credits
        user_id = "concurrency_test_002"
        num_threads = 15
        results = []

        def worker():
            ok, _, _ = deduct_credits(user_id, "deepseekv3", 1000, 1000)
            results.append(ok)

        threads = [threading.Thread(target=worker) for _ in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        uc = get_user_credits(user_id)
        self.assertLessEqual(uc.daily_used, 10, "免费套餐日使用量不应超限")


class TestUsageStats(unittest.TestCase):
    """使用统计测试"""

    @classmethod
    def setUpClass(cls):
        cls.original_cwd = _setup_test_env()
        import importlib
        import credits_system
        importlib.reload(credits_system)
        cls.cs = credits_system

    @classmethod
    def tearDownClass(cls):
        _teardown_test_env(cls.original_cwd)

    def test_get_usage_stats(self):
        add_credits = self.cs.add_credits
        deduct_credits = self.cs.deduct_credits
        subscribe_plan = self.cs.subscribe_plan
        get_usage_stats = self.cs.get_usage_stats
        user_id = "stats_test_001"
        subscribe_plan(user_id, "monthly")
        add_credits(user_id, 100)
        for _ in range(5):
            deduct_credits(user_id, "deepseekv3", 1000, 1000)
        stats = get_usage_stats(user_id, days=30)
        self.assertEqual(stats["total_calls"], 5)
        self.assertEqual(stats["total_credits_used"], 5)
        self.assertGreater(stats["total_revenue"], 0)
        self.assertIn("profit_margin", stats)
        self.assertEqual(len(stats["by_model"]), 1)

    def test_get_transactions_pagination(self):
        add_credits = self.cs.add_credits
        get_transactions = self.cs.get_transactions
        user_id = "stats_test_002"
        for i in range(15):
            add_credits(user_id, 10, f"充值{i}")
        page1 = get_transactions(user_id, limit=10, offset=0)
        page2 = get_transactions(user_id, limit=10, offset=10)
        self.assertEqual(len(page1), 10)
        self.assertEqual(len(page2), 5)


class TestGetAllPlans(unittest.TestCase):
    """管理员功能测试"""

    @classmethod
    def setUpClass(cls):
        cls.original_cwd = _setup_test_env()
        import importlib
        import credits_system
        importlib.reload(credits_system)
        cls.cs = credits_system

    @classmethod
    def tearDownClass(cls):
        _teardown_test_env(cls.original_cwd)

    def test_get_all_plans(self):
        get_all_plans = self.cs.get_all_plans
        plans = get_all_plans()
        self.assertIn("free", plans)
        self.assertIn("monthly", plans)
        self.assertIn("yearly", plans)
        self.assertIn("lifetime", plans)
        self.assertIn("current_price", plans["lifetime"])
        self.assertIn("sold_count", plans["lifetime"])

    def test_get_credit_packages(self):
        get_credit_packages = self.cs.get_credit_packages
        pkgs = get_credit_packages()
        self.assertGreater(len(pkgs), 0)
        for p in pkgs:
            self.assertIn("id", p)
            self.assertIn("credits", p)
            self.assertIn("price", p)

    def test_admin_get_stats(self):
        subscribe_plan = self.cs.subscribe_plan
        add_credits = self.cs.add_credits
        deduct_credits = self.cs.deduct_credits
        admin_get_stats = self.cs.admin_get_stats
        user_id = "admin_test_001"
        subscribe_plan(user_id, "monthly")
        add_credits(user_id, 100)
        deduct_credits(user_id, "deepseekv3", 1000, 1000)
        stats = admin_get_stats()
        self.assertIn("total_users", stats)
        self.assertIn("total_credits_consumed", stats)
        self.assertIn("profit_margin", stats)
        self.assertIn("plan_distribution", stats)


def main():
    print("=== 积分计费系统测试 ===\n")
    unittest.main(verbosity=2, exit=False)
    print("\n=== 积分计费系统测试完成 ===")


if __name__ == "__main__":
    main()
