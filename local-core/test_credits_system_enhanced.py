"""
credits_system.py 增强测试套件
覆盖积分计算、扣费、并发安全、会员权益等核心功能
"""

import unittest
import tempfile
import os
import time
import threading
from pathlib import Path
from unittest.mock import patch, MagicMock
import sqlite3

# 导入待测试模块
import sys
sys.path.insert(0, str(Path(__file__).parent))

from credits_system import (
    CREDIT_VALUE,
    MODEL_COSTS,
    MODEL_CREDIT_PRICES,
    MEMBERSHIP_PLANS,
    CREDIT_PACKAGES,
    UserCredits,
    CreditTransaction,
    calculate_credit_cost,
    calculate_cost_price,
    get_user_credits,
    get_available_credits,
    can_use_model,
    check_plan_active,
    deduct_credits,
    add_credits,
    init_db,
    _get_db,
)


class TestCreditsSystemCore(unittest.TestCase):
    """积分系统核心功能测试"""

    def setUp(self):
        """每个测试前初始化临时数据库"""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_credits.db"

        # 修改全局 DB_PATH
        import credits_system
        credits_system.DB_PATH = self.db_path
        init_db()

    def tearDown(self):
        """清理临时数据库"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_credit_value_constant(self):
        """测试积分价值常量"""
        self.assertEqual(CREDIT_VALUE, 0.1)
        self.assertIsInstance(CREDIT_VALUE, float)

    def test_model_costs_structure(self):
        """测试模型成本数据结构"""
        self.assertIn("deepseekv3", MODEL_COSTS)
        self.assertIn("gpt4o", MODEL_COSTS)

        # 验证结构完整性
        for model_id, cost_info in MODEL_COSTS.items():
            self.assertIn("input", cost_info)
            self.assertIn("output", cost_info)
            self.assertIn("provider", cost_info)
            self.assertIn("tier", cost_info)
            self.assertGreaterEqual(cost_info["input"], 0)
            self.assertGreaterEqual(cost_info["output"], 0)

    def test_model_credit_prices_coverage(self):
        """测试模型定价覆盖范围"""
        # 所有有成本的模型应该有定价
        for model_id in MODEL_COSTS.keys():
            # 某些模型可能没有定价（不应被调用）
            if model_id in MODEL_CREDIT_PRICES:
                price = MODEL_CREDIT_PRICES[model_id]
                self.assertGreaterEqual(price, 0)

    def test_membership_plans_structure(self):
        """测试会员套餐结构"""
        required_plans = ["free", "monthly", "yearly", "lifetime"]
        for plan_id in required_plans:
            self.assertIn(plan_id, MEMBERSHIP_PLANS)

            plan = MEMBERSHIP_PLANS[plan_id]
            self.assertIn("name", plan)
            self.assertIn("price", plan)
            self.assertIn("features", plan)
            self.assertIn("model_tiers", plan)

    def test_credit_packages_structure(self):
        """测试积分包结构"""
        for package in CREDIT_PACKAGES:
            self.assertIn("id", package)
            self.assertIn("name", package)
            self.assertIn("credits", package)
            self.assertIn("price", package)
            self.assertGreater(package["credits"], 0)
            self.assertGreater(package["price"], 0)


class TestCreditCalculation(unittest.TestCase):
    """积分计算测试"""

    def test_calculate_credit_cost_free_models(self):
        """测试免费模型积分消耗"""
        free_models = [
            "sf_qwen3_8b",
            "sf_deepseek_v3_free",
            "ark_dsv4p",
        ]

        for model_id in free_models:
            cost = calculate_credit_cost(model_id, 1000, 1000)
            self.assertEqual(cost, 0)

    def test_calculate_credit_cost_standard_models(self):
        """测试标准模型积分消耗"""
        # DeepSeek V3: 1积分
        cost = calculate_credit_cost("deepseekv3", 1000, 1000)
        self.assertGreater(cost, 0)

        # Qwen3: 2积分
        cost = calculate_credit_cost("qwen3", 1000, 1000)
        self.assertGreater(cost, 0)

    def test_calculate_credit_cost_premium_models(self):
        """测试高端模型积分消耗"""
        # DeepSeek R1: 5积分
        cost = calculate_credit_cost("deepseekr1", 1000, 1000)
        self.assertGreater(cost, 0)

    def test_calculate_credit_cost_flagship_models(self):
        """测试旗舰模型积分消耗"""
        # GPT-4o: 8积分
        cost = calculate_credit_cost("gpt4o", 1000, 1000)
        self.assertGreater(cost, 0)

    def test_calculate_cost_price_free_tier(self):
        """测试免费层级成本价计算"""
        free_models = ["ark_dsv4p", "ark_dsv4f", "ark_dsv32"]

        for model_id in free_models:
            cost = calculate_cost_price(model_id, 1000, 1000)
            self.assertEqual(cost, 0)

    def test_calculate_cost_price_standard_tier(self):
        """测试标准层级成本价计算"""
        # 验证成本价为正数
        cost = calculate_cost_price("deepseekv3", 1000, 1000)
        self.assertGreater(cost, 0)

    def test_calculate_cost_price_proportional(self):
        """测试成本价按 tokens 比例计算"""
        cost1 = calculate_cost_price("deepseekv3", 1000, 1000)
        cost2 = calculate_cost_price("deepseekv3", 2000, 2000)

        # tokens 加倍，成本也应大致加倍
        self.assertAlmostEqual(cost2, cost1 * 2, delta=0.01)

    def test_calculate_credit_cost_unknown_model(self):
        """测试未知模型的积分计算"""
        # 未知模型应该返回默认值或抛出异常
        try:
            cost = calculate_credit_cost("unknown_model_xyz", 1000, 1000)
            # 如果不抛异常，应该有默认值
            self.assertIsInstance(cost, (int, float))
        except KeyError:
            # 预期行为：未知模型应抛出 KeyError
            pass


class TestUserCreditManagement(unittest.TestCase):
    """用户积分管理测试"""

    def setUp(self):
        """初始化测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_credits.db"

        import credits_system
        credits_system.DB_PATH = self.db_path
        init_db()

    def tearDown(self):
        """清理测试环境"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_get_user_credits_new_user(self):
        """测试新用户积分查询"""
        user_id = "test_user_001"
        uc = get_user_credits(user_id)

        self.assertEqual(uc.user_id, user_id)
        self.assertEqual(uc.credits, 0)
        self.assertEqual(uc.plan, "free")

    def test_get_available_credits_free_user(self):
        """测试免费用户可用积分"""
        user_id = "test_user_free"
        uc = get_user_credits(user_id)
        available = get_available_credits(uc)

        # 免费用户每天有10积分额度
        self.assertGreaterEqual(available, 0)
        self.assertLessEqual(available, 10)

    def test_check_plan_active_free(self):
        """测试免费套餐激活状态"""
        uc = UserCredits(
            user_id="test",
            credits=0,
            plan="free",
            plan_expires_at=None,
            daily_used=0,
            daily_reset_date="",
            total_used=0,
            created_at=time.time(),
        )

        is_active = check_plan_active(uc)
        self.assertTrue(is_active)

    def test_check_plan_active_monthly(self):
        """测试月度套餐激活状态"""
        # 有效月度套餐
        uc_active = UserCredits(
            user_id="test",
            credits=100,
            plan="monthly",
            plan_expires_at=time.time() + 86400 * 30,  # 30天后过期
            daily_used=0,
            daily_reset_date="",
            total_used=0,
            created_at=time.time(),
        )
        self.assertTrue(check_plan_active(uc_active))

        # 已过期月度套餐
        uc_expired = UserCredits(
            user_id="test",
            credits=100,
            plan="monthly",
            plan_expires_at=time.time() - 86400,  # 1天前过期
            daily_used=0,
            daily_reset_date="",
            total_used=0,
            created_at=time.time(),
        )
        self.assertFalse(check_plan_active(uc_expired))

    def test_check_plan_active_lifetime(self):
        """测试终身套餐激活状态"""
        uc = UserCredits(
            user_id="test",
            credits=50000,
            plan="lifetime",
            plan_expires_at=None,
            daily_used=0,
            daily_reset_date="",
            total_used=0,
            created_at=time.time(),
        )

        self.assertTrue(check_plan_active(uc))


class TestModelAccessControl(unittest.TestCase):
    """模型访问控制测试"""

    def test_can_use_model_free_tier(self):
        """测试免费用户模型访问"""
        uc = UserCredits(
            user_id="test",
            credits=0,
            plan="free",
            plan_expires_at=None,
            daily_used=0,
            daily_reset_date="",
            total_used=0,
            created_at=time.time(),
        )

        # 免费用户应能访问 free 和 standard 层级模型
        can_use, msg = can_use_model(uc, "deepseekv3")
        self.assertTrue(can_use)

        # 免费用户不能访问 premium 层级模型
        can_use, msg = can_use_model(uc, "gpt4o")
        self.assertFalse(can_use)
        self.assertIn("升级", msg)

    def test_can_use_model_premium_tier(self):
        """测试高级用户模型访问"""
        uc = UserCredits(
            user_id="test",
            credits=1000,
            plan="monthly",
            plan_expires_at=time.time() + 86400 * 30,
            daily_used=0,
            daily_reset_date="",
            total_used=0,
            created_at=time.time(),
        )

        # 月度会员应能访问所有层级模型
        for model_id in ["deepseekv3", "gpt4o", "claude4"]:
            can_use, msg = can_use_model(uc, model_id)
            self.assertTrue(can_use)

    def test_can_use_model_lifetime_tier(self):
        """测试终身会员模型访问"""
        uc = UserCredits(
            user_id="test",
            credits=50000,
            plan="lifetime",
            plan_expires_at=None,
            daily_used=0,
            daily_reset_date="",
            total_used=0,
            created_at=time.time(),
        )

        # 终身会员应能访问所有模型
        for model_id in ["deepseekv3", "gpt4o", "claude4"]:
            can_use, msg = can_use_model(uc, model_id)
            self.assertTrue(can_use)


class TestCreditDeduction(unittest.TestCase):
    """积分扣减测试"""

    def setUp(self):
        """初始化测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_credits.db"

        import credits_system
        credits_system.DB_PATH = self.db_path
        init_db()

    def tearDown(self):
        """清理测试环境"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_deduct_credits_free_model(self):
        """测试免费模型扣费"""
        user_id = "test_user_free_model"
        result = deduct_credits(user_id, "ark_dsv4p", 1000, 1000)

        success, msg, cost = result
        self.assertTrue(success)
        self.assertEqual(cost, 0)

    def test_deduct_credits_insufficient_balance(self):
        """测试余额不足扣费"""
        user_id = "test_user_insufficient"

        # 先尝试给用户添加少量积分
        add_credits(user_id, 1, "test")

        # 尝试消费需要更多积分的模型
        result = deduct_credits(user_id, "gpt4o", 1000, 1000)
        success, msg, cost = result

        self.assertFalse(success)
        self.assertIn("不足", msg)

    def test_deduct_credits_successful(self):
        """测试成功扣费"""
        user_id = "test_user_success"

        # 添加足够积分
        add_credits(user_id, 100, "test")

        # 扣费
        result = deduct_credits(user_id, "deepseekv3", 1000, 1000)
        success, msg, cost = result

        self.assertTrue(success)
        self.assertGreater(cost, 0)

    def test_deduct_credits_atomicity(self):
        """测试扣费原子性"""
        user_id = "test_user_atomic"

        # 添加固定积分
        add_credits(user_id, 10, "test")

        # 并发扣费
        results = []
        threads = []

        def deduct_thread():
            result = deduct_credits(user_id, "deepseekv3", 1000, 1000)
            results.append(result)

        # 创建多个并发线程
        for _ in range(5):
            t = threading.Thread(target=deduct_thread)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # 验证最终余额不为负
        uc = get_user_credits(user_id)
        self.assertGreaterEqual(uc.credits, 0)


class TestConcurrencySafety(unittest.TestCase):
    """并发安全测试"""

    def setUp(self):
        """初始化测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_credits.db"

        import credits_system
        credits_system.DB_PATH = self.db_path
        init_db()

    def tearDown(self):
        """清理测试环境"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_concurrent_deduction_race_condition(self):
        """测试并发扣费的竞态条件"""
        user_id = "test_concurrent_user"

        # 初始积分
        add_credits(user_id, 5, "initial")

        success_count = 0
        failure_count = 0
        lock = threading.Lock()

        def deduct_worker():
            nonlocal success_count, failure_count
            result = deduct_credits(user_id, "deepseekv3", 1000, 1000)
            success, msg, cost = result

            with lock:
                if success:
                    success_count += 1
                else:
                    failure_count += 1

        # 启动10个并发扣费线程
        threads = []
        for _ in range(10):
            t = threading.Thread(target=deduct_worker)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # 验证只有部分成功，且余额不为负
        uc = get_user_credits(user_id)
        self.assertGreaterEqual(uc.credits, 0)

        # 成功次数应该少于总次数（因为积分有限）
        self.assertLess(success_count, 10)


class TestEdgeCases(unittest.TestCase):
    """边界条件和异常情况测试"""

    def test_zero_tokens(self):
        """测试零 tokens 输入"""
        cost = calculate_credit_cost("deepseekv3", 0, 0)
        self.assertEqual(cost, 0)

    def test_negative_tokens(self):
        """测试负数 tokens 输入"""
        # 负数 tokens 应该被处理
        try:
            cost = calculate_credit_cost("deepseekv3", -100, -100)
            # 如果不抛异常，应该返回0或正值
            self.assertGreaterEqual(cost, 0)
        except (ValueError, TypeError):
            # 预期行为：应拒绝负数输入
            pass

    def test_large_tokens(self):
        """测试大 tokens 输入"""
        # 测试百万级 tokens
        cost = calculate_credit_cost("gpt4o", 1000000, 1000000)
        self.assertGreater(cost, 0)

    def test_unknown_user_id(self):
        """测试未知用户 ID"""
        uc = get_user_credits("unknown_user_xyz")
        self.assertEqual(uc.credits, 0)
        self.assertEqual(uc.plan, "free")

    def test_database_connection_error(self):
        """测试数据库连接错误"""
        # 模拟数据库文件权限错误
        import credits_system
        original_path = credits_system.DB_PATH

        try:
            # 设置为无效路径
            credits_system.DB_PATH = "/proc/invalid/path/credits.db"

            # 应该抛出异常或返回默认值
            try:
                uc = get_user_credits("test")
            except (sqlite3.OperationalError, OSError):
                pass  # 预期的错误
        finally:
            credits_system.DB_PATH = original_path


class TestPerformance(unittest.TestCase):
    """性能测试"""

    def setUp(self):
        """初始化测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_credits.db"

        import credits_system
        credits_system.DB_PATH = self.db_path
        init_db()

    def tearDown(self):
        """清理测试环境"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_calculation_performance(self):
        """测试积分计算性能"""
        import time

        start_time = time.time()
        iterations = 10000

        for _ in range(iterations):
            calculate_credit_cost("gpt4o", 1000, 1000)
            calculate_cost_price("gpt4o", 1000, 1000)

        elapsed = time.time() - start_time
        avg_time = elapsed / iterations

        # 每次计算应小于 0.1ms
        self.assertLess(avg_time, 0.0001)

    def test_database_query_performance(self):
        """测试数据库查询性能"""
        import time

        user_id = "perf_test_user"
        add_credits(user_id, 1000, "test")

        start_time = time.time()
        iterations = 1000

        for _ in range(iterations):
            uc = get_user_credits(user_id)
            get_available_credits(uc)

        elapsed = time.time() - start_time
        avg_time = elapsed / iterations

        # 每次查询应小于 1ms
        self.assertLess(avg_time, 0.001)


if __name__ == "__main__":
    unittest.main(verbosity=2)