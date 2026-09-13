"""
credits_system.py 积分/定价/并发原子性测试
隔离策略：每个 TestCase 独立 cwd + reload 模块，让 init_db 在 tmpdir 下建库
覆盖范围：
- DB 初始化与 WAL 模式
- calculate_credit_cost：免费模型=0、MODEL_CREDIT_PRICES 精确值、未知模型默认 2
- can_use_model：free 套餐拒 premium/flagship、lifetime 全放行、未知 tier 当作 standard
- check_plan_active：monthly/yearly 过期判定、free/lifetime 永活
- get_available_credits + daily reset（跨天模拟）
- deduct_credits：free 套餐 daily_used 原子累加（并发不超 daily_limit）、付费套餐 credits 原子扣减（并发不变负）
- subscribe_plan：lifetime 限量不超卖（并发竞争只允许 1 成功）、过期时间正确、不存在套餐拒绝
- add_credits + get_transactions
- 终身版批次自动推进 + 阶梯涨价
"""
import importlib
import os
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _setup_credits(tmpdir: str):
    backup = os.getcwd()
    os.chdir(tmpdir)
    import credits_system as _m
    return importlib.reload(_m), backup


class CreditsIsolatedTestCase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.mod, self._cwd = _setup_credits(self.tmpdir)

    def tearDown(self):
        os.chdir(self._cwd)


class TestDbInit(CreditsIsolatedTestCase):
    def test_creates_tables(self):
        p = Path(self.tmpdir) / "data" / "credits.db"
        self.assertTrue(p.exists())
        conn = sqlite3.connect(str(p))
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        names = {r[0] for r in rows}
        for t in ["user_credits", "credit_transactions", "lifetime_sales", "pricing_config"]:
            self.assertIn(t, names, f"缺少表 {t}")
        conn.close()

    def test_wal_mode(self):
        conn = self.mod._get_db()
        cur = conn.execute("PRAGMA journal_mode").fetchone()
        self.assertEqual(cur[0].lower(), "wal")
        conn.close()


class TestCreditCost(CreditsIsolatedTestCase):
    def test_free_models(self):
        for m in ["sf_qwen3_8b", "ark_dsv4p", "sf_deepseek_v3_free", "ark_dbs_code"]:
            self.assertEqual(self.mod.calculate_credit_cost(m), 0, f"{m} 应为 0 分")
        # glm4plus 虽然 cost=0，但 MODEL_CREDIT_PRICES 固定为 1
        self.assertEqual(self.mod.calculate_credit_cost("glm4plus"), 1)

    def test_known_fixed_prices(self):
        self.assertEqual(self.mod.calculate_credit_cost("deepseekv3"), 1)
        self.assertEqual(self.mod.calculate_credit_cost("ali_qwen37_max"), 8)
        self.assertEqual(self.mod.calculate_credit_cost("nx_claude_opus"), 15)

    def test_unknown_model_default_two(self):
        self.assertEqual(self.mod.calculate_credit_cost("totally_not_a_real_model_xyz"), 2)

    def test_zero_cost_returns_zero(self):
        self.assertEqual(self.mod.calculate_credit_cost("ark_dsv4p", 10_000, 10_000), 0)


class TestCanUseModel(CreditsIsolatedTestCase):
    def _make_uc(self, plan="free"):
        from credits_system import UserCredits
        return UserCredits(
            user_id="u", credits=0, plan=plan, plan_expires_at=None,
            daily_used=0, daily_reset_date=self.mod._today_str(),
            total_used=0, created_at=time.time(),
        )

    def test_free_plan_limited(self):
        uc = self._make_uc("free")
        self.assertTrue(self.mod.can_use_model(uc, "deepseekv3")[0])  # standard 允许
        self.assertFalse(self.mod.can_use_model(uc, "nx_gpt5")[0])    # flagship 拒绝
        self.assertFalse(self.mod.can_use_model(uc, "ali_qwen37_max")[0])  # premium 拒绝

    def test_lifetime_all_tiers(self):
        uc = self._make_uc("lifetime")
        for m in ["deepseekv3", "ali_qwen37_max", "nx_gpt5", "nx_claude_opus"]:
            self.assertTrue(self.mod.can_use_model(uc, m)[0], f"lifetime 应可用 {m}")

    def test_unknown_model_assumed_standard(self):
        uc = self._make_uc("free")
        self.assertTrue(self.mod.can_use_model(uc, "brand_new_standard_model")[0])


class TestPlanActive(CreditsIsolatedTestCase):
    def test_free_and_lifetime_always_active(self):
        from credits_system import UserCredits
        now = time.time()
        self.assertTrue(self.mod.check_plan_active(UserCredits("u", 0, "free", None, 0, "", 0, now)))
        self.assertTrue(self.mod.check_plan_active(UserCredits("u", 0, "lifetime", None, 0, "", 0, now)))

    def test_monthly_expired(self):
        from credits_system import UserCredits
        past = time.time() - 3600
        self.assertFalse(self.mod.check_plan_active(
            UserCredits("u", 0, "monthly", past, 0, "", 0, time.time())))

    def test_yearly_active(self):
        from credits_system import UserCredits
        future = time.time() + 3600
        self.assertTrue(self.mod.check_plan_active(
            UserCredits("u", 0, "yearly", future, 0, "", 0, time.time())))


class TestDeductHappyPath(CreditsIsolatedTestCase):
    def test_free_model_zero_cost(self):
        ok, msg, cost = self.mod.deduct_credits("u", "sf_qwen3_8b")
        self.assertTrue(ok)
        self.assertEqual(cost, 0)
        self.assertEqual(msg, "免费模型")

    def test_premium_model_rejected_on_free_plan(self):
        ok, msg, _ = self.mod.deduct_credits("u", "ali_qwen37_max")
        self.assertFalse(ok)
        self.assertIn("升级套餐", msg)

    def test_paid_plan_deduct(self):
        uid = "paid_ok"
        self.mod.subscribe_plan(uid, "monthly")
        ok, msg, cost = self.mod.deduct_credits(uid, "deepseekv3")
        self.assertTrue(ok)
        self.assertEqual(cost, 1)
        uc = self.mod._get_db().execute(
            "SELECT credits FROM user_credits WHERE user_id=?", (uid,)).fetchone()
        self.assertEqual(uc[0], 1000 - 1)

    def test_paid_plan_insufficient(self):
        uid = "paid_tight"
        self.mod.subscribe_plan(uid, "monthly")
        # 连扣 124 次 ali_qwen37_max (8 积分/次) = 992
        for _ in range(124):
            self.mod.deduct_credits(uid, "ali_qwen37_max")
        # 再扣 8 积分会把 credits 降到 0（刚好）或不够
        uc = self.mod._ensure_user(uid)
        needed = 8
        if uc.credits >= needed:
            self.mod.deduct_credits(uid, "ali_qwen37_max")
        # 现在余额必然 < 8
        uc = self.mod._ensure_user(uid)
        self.assertLess(uc.credits, needed)
        ok, msg, _ = self.mod.deduct_credits(uid, "ali_qwen37_max")
        self.assertFalse(ok)
        self.assertIn("积分不足", msg)


class TestConcurrencyFreePlan(CreditsIsolatedTestCase):
    """
    关键 TOCTOU 防护验证：
    free 套餐 daily_limit 条件下，多线程并发 deduct_credits 最终 daily_used 必须 <= daily_limit。
    """

    def test_free_daily_cap_not_exceeded_under_contention(self):
        limit = self.mod.MEMBERSHIP_PLANS["free"]["daily_credits"]
        N_REQUESTS = 80
        successes = [0]
        fails = [0]
        lock = threading.Lock()

        self.mod._ensure_user("free_u")  # 预创建，避免 _ensure_user 的 race
        def worker():
            try:
                ok, _, _ = self.mod.deduct_credits("free_u", "deepseekv3")
                with lock:
                    if ok:
                        successes[0] += 1
                    else:
                        fails[0] += 1
            except Exception:
                with lock:
                    fails[0] += 1

        threads = [threading.Thread(target=worker) for _ in range(N_REQUESTS)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(successes[0], limit,
                         f"应恰好 {limit} 次成功，实际 {successes[0]}")
        uc = self.mod._get_db().execute(
            "SELECT daily_used FROM user_credits WHERE user_id='free_u'").fetchone()
        self.assertEqual(uc[0], limit, f"daily_used 应等于 {limit}，实际 {uc[0]}")


class TestConcurrencyPaidPlan(CreditsIsolatedTestCase):
    def test_paid_balance_not_below_zero(self):
        uid = "paid_concurrent"
        self.mod.subscribe_plan(uid, "monthly")  # credits=1000
        # ali_qwen37_max = 8
        N_THREADS = 160  # 160 * 8 = 1280 > 1000
        successes = [0]
        lock = threading.Lock()

        def worker():
            try:
                ok, _, _ = self.mod.deduct_credits(uid, "ali_qwen37_max")
                with lock:
                    if ok:
                        successes[0] += 1
            except Exception:
                pass

        threads = [threading.Thread(target=worker) for _ in range(N_THREADS)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        uc = self.mod._get_db().execute(
            "SELECT credits FROM user_credits WHERE user_id=?", (uid,)).fetchone()
        self.assertGreaterEqual(uc[0], 0, f"credits 不能为负，实际 {uc[0]}")
        self.assertEqual(successes[0], 125,
                         f"应恰好 125 次成功（1000/8），实际 {successes[0]}")


class TestSubscribeLifetimeAtomic(CreditsIsolatedTestCase):
    def test_overall_atomic_limit(self):
        limit = self.mod.MEMBERSHIP_PLANS["lifetime"]["total_limit"]
        # 先把 lifetime_sold 推到 limit - 1
        self.mod._get_db().execute(
            "UPDATE pricing_config SET value=? WHERE key='lifetime_sold'",
            (str(limit - 1),)).connection.commit()
        N = 5
        wins = [0]
        lock = threading.Lock()

        def worker(i):
            ok, _ = self.mod.subscribe_plan(f"race_user_{i}", "lifetime")
            with lock:
                if ok:
                    wins[0] += 1

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(N)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(wins[0], 1,
                         f"lifetime 并发订阅只能成功 1 个，实际 {wins[0]}")
        self.assertEqual(self.mod.get_lifetime_sold_count(), limit)

    def test_expiration_times(self):
        before = time.time()
        self.mod.subscribe_plan("u_m", "monthly")
        uc = self.mod._ensure_user("u_m")
        self.assertAlmostEqual(uc.plan_expires_at - before, 30 * 24 * 3600, delta=10)

        self.mod.subscribe_plan("u_y", "yearly")
        uc = self.mod._ensure_user("u_y")
        self.assertAlmostEqual(uc.plan_expires_at - before, 365 * 24 * 3600, delta=10)

    def test_nonexistent_plan(self):
        ok, msg = self.mod.subscribe_plan("x", "totally_plan")
        self.assertFalse(ok)
        self.assertEqual(msg, "套餐不存在")


class TestDailyReset(CreditsIsolatedTestCase):
    def test_daily_limit_resets_after_day_rollover(self):
        self.mod.deduct_credits("u", "deepseekv3")  # 用掉 1
        # 模拟昨天
        yday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        self.mod._get_db().execute(
            "UPDATE user_credits SET daily_reset_date=?, daily_used=? WHERE user_id=?",
            (yday, 9, "u")).connection.commit()
        uc = self.mod.get_user_credits("u")
        self.mod._check_daily_reset(uc)
        self.assertEqual(uc.daily_used, 0)
        # 数据库同步
        uc2 = self.mod._ensure_user("u")
        self.assertEqual(uc2.daily_used, 0)


class TestTransactions(CreditsIsolatedTestCase):
    def test_add_and_list(self):
        self.mod.add_credits("t1", 100, "测试充值")
        self.mod.deduct_credits("t1", "deepseekv3")
        txs = self.mod.get_transactions("t1")
        self.assertGreaterEqual(len(txs), 2)
        self.assertEqual(txs[0].type, "consume")
        self.assertEqual(txs[1].type, "recharge")


class TestLifetimePricing(CreditsIsolatedTestCase):
    def test_batch_price_increase(self):
        base = self.mod.MEMBERSHIP_PLANS["lifetime"]["price"]
        rate = self.mod.MEMBERSHIP_PLANS["lifetime"]["price_increase_rate"]
        self.assertEqual(self.mod.get_lifetime_current_price(), base)
        # 先卖 100 份 -> batch 2
        for i in range(100):
            self.mod.subscribe_plan(f"batch_u_{i}", "lifetime")
        changed, batch = self.mod.check_lifetime_price_increase()
        self.assertTrue(changed)
        self.assertEqual(batch, 2)
        expected = base * (1 + rate)
        self.assertAlmostEqual(self.mod.get_lifetime_current_price(), expected, places=2)


def main():
    unittest.main(verbosity=2)


if __name__ == "__main__":
    main()
