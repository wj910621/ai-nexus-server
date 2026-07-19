"""
Y·NEX计费系统测试
测试目标：验证计费系统的安全性和正确性
- 用户认证与 API Key 管理
- 余额充值与扣费
- 额度管理与使用记录
- 订阅与分销商系统
- 并发安全（防 TOCTOU 竞态）
"""
import os
import sys
import time
import unittest
import tempfile
import threading
from unittest.mock import patch, MagicMock

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class TestUserAuthentication(unittest.TestCase):
    """用户认证测试"""

    def setUp(self):
        """测试前准备"""
        import billing
        from pathlib import Path
        self.temp_dir = tempfile.mkdtemp()
        billing.DB_PATH = Path(os.path.join(self.temp_dir, "test_users.db"))
        billing.init_db()

    def tearDown(self):
        """测试后清理"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_register_user_success(self):
        """测试用户注册成功"""
        from billing import register_user
        
        success, msg = register_user(
            username="testuser001",
            password="SecurePass123!",
            email="test@example.com"
        )
        
        self.assertTrue(success)
        self.assertIn("注册成功", msg)
        self.assertIn("API Key", msg)  # 应返回 API Key

    def test_register_user_duplicate(self):
        """测试重复用户名注册"""
        from billing import register_user
        
        register_user("testuser002", "pass123", "test2@example.com")
        
        # 重复用户名
        success, msg = register_user("testuser002", "pass456", "test3@example.com")
        self.assertFalse(success)
        self.assertIn("已被注册", msg)

    def test_register_user_duplicate_email(self):
        """测试重复邮箱注册"""
        from billing import register_user
        
        register_user("user1", "pass", "same@example.com")
        
        success, msg = register_user("user2", "pass", "same@example.com")
        self.assertFalse(success)

    def test_login_success(self):
        """测试登录成功"""
        from billing import register_user, login_user
        
        register_user("loginuser", "MyPassword123", "login@example.com")
        
        success, msg, user_info = login_user("loginuser", "MyPassword123")
        
        self.assertTrue(success)
        self.assertIsNotNone(user_info)
        self.assertEqual(user_info["username"], "loginuser")
        # 不应返回明文密码
        self.assertNotIn("password_hash", user_info)

    def test_login_wrong_password(self):
        """测试错误密码"""
        from billing import register_user, login_user
        
        register_user("wrongpass", "CorrectPass", "wrong@example.com")
        
        success, msg, user_info = login_user("wrongpass", "WrongPass")
        
        self.assertFalse(success)
        self.assertIsNone(user_info)

    def test_api_key_verification(self):
        """测试 API Key 验证"""
        from billing import register_user, verify_api_key
        
        success, msg = register_user("apikey_user", "pass", "apikey@example.com")
        
        # 从注册消息中提取 API Key
        import re
        match = re.search(r'API Key: (yn_[A-Za-z0-9_-]+)', msg)
        self.assertIsNotNone(match)
        api_key = match.group(1)
        
        # 验证 API Key
        valid, user, error = verify_api_key(api_key)
        self.assertTrue(valid)
        self.assertIsNotNone(user)
        self.assertEqual(user.username, "apikey_user")

    def test_api_key_invalid(self):
        """测试无效 API Key"""
        from billing import verify_api_key
        
        valid, user, error = verify_api_key("yn_invalid_key")
        self.assertFalse(valid)
        self.assertIsNone(user)

    def test_api_key_hash_storage(self):
        """测试 API Key 哈希存储"""
        from billing import register_user, _get_db
        
        success, msg = register_user("hash_user", "pass", "hash@example.com")
        
        # 从数据库直接查询
        import re
        match = re.search(r'API Key: (yn_[A-Za-z0-9_-]+)', msg)
        api_key = match.group(1)
        
        conn = _get_db()
        c = conn.cursor()
        c.execute("SELECT api_key FROM users WHERE username = ?", ("hash_user",))
        row = c.fetchone()
        conn.close()
        
        # 数据库中应存储哈希值，而非明文
        stored_key = row["api_key"]
        self.assertNotEqual(stored_key, api_key)
        self.assertTrue(len(stored_key) > 32)  # 哈希值长度


class TestBalanceManagement(unittest.TestCase):
    """余额管理测试"""

    def setUp(self):
        """测试前准备"""
        import billing
        from pathlib import Path
        self.temp_dir = tempfile.mkdtemp()
        billing.DB_PATH = Path(os.path.join(self.temp_dir, "test_users.db"))
        billing.init_db()
        
        # 注册测试用户
        from billing import register_user
        register_user("balance_user", "pass", "balance@example.com")

    def tearDown(self):
        """测试后清理"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_recharge_balance(self):
        """测试余额充值"""
        from billing import recharge_balance, get_user_info
        
        success, msg = recharge_balance("balance_user", 100.0, "alipay")
        
        self.assertTrue(success)
        self.assertIn("充值成功", msg)
        
        # 验证余额增加
        user_info = get_user_info("balance_user")
        self.assertEqual(user_info["balance"], 10000)  # 单位：分

    def test_recharge_negative_amount(self):
        """测试充值负数金额"""
        from billing import recharge_balance
        
        success, msg = recharge_balance("balance_user", -10.0, "manual")
        
        self.assertFalse(success)
        self.assertIn("大于0", msg)

    def test_recharge_zero_amount(self):
        """测试充值零金额"""
        from billing import recharge_balance
        
        success, msg = recharge_balance("balance_user", 0, "manual")
        
        self.assertFalse(success)


class TestQuotaManagement(unittest.TestCase):
    """额度管理测试"""

    def setUp(self):
        """测试前准备"""
        import billing
        from pathlib import Path
        self.temp_dir = tempfile.mkdtemp()
        billing.DB_PATH = Path(os.path.join(self.temp_dir, "test_users.db"))
        billing.init_db()
        
        from billing import register_user
        register_user("quota_user", "pass", "quota@example.com")

    def tearDown(self):
        """测试后清理"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_check_quota_sufficient(self):
        """测试额度充足检查"""
        from billing import check_quota
        
        allowed, msg = check_quota("quota_user", tokens_needed=1000)
        
        self.assertTrue(allowed)

    def test_check_quota_exceeded(self):
        """测试额度超限检查"""
        from billing import check_quota
        
        # 默认额度 100000 tokens
        allowed, msg = check_quota("quota_user", tokens_needed=200000)
        
        self.assertFalse(allowed)
        self.assertIn("已用完", msg)

    def test_deduct_quota(self):
        """测试额度扣减"""
        from billing import deduct_quota, get_user_info
        
        # 扣减额度
        deduct_quota("quota_user", tokens=5000, cost=1.0, charged=2.0)
        
        # 验证使用量增加
        user_info = get_user_info("quota_user")
        self.assertEqual(user_info["quota_used"], 5000)


class TestSubscriptionSystem(unittest.TestCase):
    """订阅系统测试"""

    def setUp(self):
        """测试前准备"""
        import billing
        from pathlib import Path
        self.temp_dir = tempfile.mkdtemp()
        billing.DB_PATH = Path(os.path.join(self.temp_dir, "test_users.db"))
        billing.init_db()
        
        from billing import register_user, recharge_balance
        register_user("sub_user", "pass", "sub@example.com")
        recharge_balance("sub_user", 50.0, "manual")  # 充值 50 元

    def tearDown(self):
        """测试后清理"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_subscribe_pro_success(self):
        """测试订阅专业版"""
        from billing import subscribe_tier, get_user_info
        
        success, msg = subscribe_tier("sub_user", "pro")
        
        self.assertTrue(success)
        self.assertIn("订阅成功", msg)
        
        # 验证用户角色和额度
        user_info = get_user_info("sub_user")
        self.assertEqual(user_info["role"], "pro")
        self.assertEqual(user_info["quota_limit"], 5000000)

    def test_subscribe_insufficient_balance(self):
        """测试余额不足订阅"""
        from billing import subscribe_tier
        
        # 充值 5 元，专业版需 9.9 元
        from billing import recharge_balance
        recharge_balance("sub_user", -45.0, "manual")  # 扣回余额
        
        success, msg = subscribe_tier("sub_user", "pro")
        
        self.assertFalse(success)
        self.assertIn("余额不足", msg)

    def test_subscribe_with_paid_order(self):
        """测试已支付订单订阅"""
        from billing import subscribe_tier, get_user_info
        
        # 模拟已支付订单
        success, msg = subscribe_tier("sub_user", "pro", paid_order_amount=9.9)
        
        self.assertTrue(success)
        
        user_info = get_user_info("sub_user")
        self.assertEqual(user_info["role"], "pro")

    def test_subscribe_invalid_tier(self):
        """测试无效套餐"""
        from billing import subscribe_tier
        
        success, msg = subscribe_tier("sub_user", "invalid_tier")
        
        self.assertFalse(success)
        self.assertIn("不存在", msg)


class TestAgentSystem(unittest.TestCase):
    """分销商系统测试"""

    def setUp(self):
        """测试前准备"""
        import billing
        from pathlib import Path
        self.temp_dir = tempfile.mkdtemp()
        billing.DB_PATH = Path(os.path.join(self.temp_dir, "test_users.db"))
        billing.init_db()
        
        from billing import register_user, recharge_balance
        register_user("agent_user", "pass", "agent@example.com")
        recharge_balance("agent_user", 2000.0, "manual")  # 充值足够余额

    def tearDown(self):
        """测试后清理"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_create_agent_success(self):
        """测试创建分销商成功"""
        from billing import create_agent_account, get_user_info
        
        success, msg = create_agent_account("agent_user")
        
        self.assertTrue(success)
        self.assertIn("已成为分销商", msg)
        
        # 验证角色和扣费
        user_info = get_user_info("agent_user")
        self.assertEqual(user_info["role"], "agent")
        # 准入费 1000 元
        self.assertEqual(user_info["balance"], 100000)  # 2000 - 1000 = 1000 元

    def test_create_agent_insufficient_balance(self):
        """测试余额不足创建分销商"""
        from billing import create_agent_account, recharge_balance
        
        # 扣回余额
        recharge_balance("agent_user", -1900.0, "manual")
        
        success, msg = create_agent_account("agent_user")
        
        self.assertFalse(success)
        self.assertIn("余额不足", msg)

    def test_create_agent_with_paid_order(self):
        """测试已支付订单创建分销商"""
        from billing import create_agent_account, get_user_info
        
        success, msg = create_agent_account("agent_user", paid_order_amount=1000.0)
        
        self.assertTrue(success)
        
        user_info = get_user_info("agent_user")
        self.assertEqual(user_info["role"], "agent")

    def test_referral_system(self):
        """测试推荐返利系统"""
        from billing import register_user, get_user_info
        
        # 注册分销商
        from billing import create_agent_account, recharge_balance
        register_user("referrer", "pass", "referrer@example.com")
        recharge_balance("referrer", 2000.0, "manual")
        create_agent_account("referrer")
        
        # 注册被推荐用户
        referrer_info = get_user_info("referrer")
        success, msg = register_user(
            "referred_user",
            "pass",
            "referred@example.com",
            referrer_id=referrer_info["id"]
        )
        
        self.assertTrue(success)
        
        # 验证推荐人获得奖励
        referrer_info_after = get_user_info("referrer")
        # 推荐奖励 100 分 = 1 元
        self.assertEqual(referrer_info_after["balance"], 100000 + 100)


class TestConcurrentBilling(unittest.TestCase):
    """并发计费安全测试"""

    def setUp(self):
        """测试前准备"""
        import billing
        from pathlib import Path
        self.temp_dir = tempfile.mkdtemp()
        billing.DB_PATH = Path(os.path.join(self.temp_dir, "test_users.db"))
        billing.init_db()
        
        from billing import register_user, recharge_balance
        register_user("concurrent_user", "pass", "concurrent@example.com")
        recharge_balance("concurrent_user", 100.0, "manual")

    def tearDown(self):
        """测试后清理"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_concurrent_subscribe(self):
        """测试并发订阅（防双扣）"""
        from billing import subscribe_tier, get_user_info
        
        # 余额仅够订阅一次
        results = []
        
        def subscribe_thread():
            success, msg = subscribe_tier("concurrent_user", "pro")
            results.append((success, msg))
        
        threads = [
            threading.Thread(target=subscribe_thread),
            threading.Thread(target=subscribe_thread)
        ]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # 仅一个应成功
        success_count = sum(1 for success, _ in results if success)
        self.assertLessEqual(success_count, 1)
        
        # 验证余额只被扣一次
        user_info = get_user_info("concurrent_user")
        # 如果订阅成功，余额应为 100 - 9.9 = 90.1 元
        # 如果都失败（余额检查失败），余额应为 100 元
        self.assertGreaterEqual(user_info["balance"], 9010)

    def test_concurrent_recharge_and_use(self):
        """测试并发充值和使用"""
        from billing import recharge_balance, record_usage
        
        # 并发充值
        def recharge_thread():
            recharge_balance("concurrent_user", 10.0, "manual")
        
        threads = []
        for _ in range(5):
            threads.append(threading.Thread(target=recharge_thread))
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # 验证总额正确
        from billing import get_user_info
        user_info = get_user_info("concurrent_user")
        # 初始 100 + 5*10 = 150 元
        self.assertEqual(user_info["balance"], 15000)


class TestUsageRecording(unittest.TestCase):
    """使用记录测试"""

    def setUp(self):
        """测试前准备"""
        import billing
        from pathlib import Path
        self.temp_dir = tempfile.mkdtemp()
        billing.DB_PATH = Path(os.path.join(self.temp_dir, "test_users.db"))
        billing.init_db()
        
        from billing import register_user
        success, msg = register_user("usage_user", "pass", "usage@example.com")
        
        # 提取 API Key
        import re
        match = re.search(r'API Key: (yn_[A-Za-z0-9_-]+)', msg)
        self.api_key = match.group(1) if match else None

    def tearDown(self):
        """测试后清理"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_record_usage_normal(self):
        """测试正常使用记录"""
        from billing import record_usage, get_user_info
        
        # 记录使用
        record_usage(
            api_key=self.api_key,
            tokens=1000,
            cost=1.0,
            charged=2.0,
            endpoint="/chat"
        )
        
        # 验证使用量增加
        user_info = get_user_info("usage_user")
        self.assertEqual(user_info["quota_used"], 1000)

    def test_record_usage_exceed_quota(self):
        """测试超出额度扣费"""
        from billing import record_usage, recharge_balance, get_user_info
        
        # 充值余额
        recharge_balance("usage_user", 10.0, "manual")
        
        # 使用超出额度（默认 100000）
        record_usage(
            api_key=self.api_key,
            tokens=200000,
            cost=100.0,
            charged=200.0,
            endpoint="/chat"
        )
        
        # 验证余额被扣减
        user_info = get_user_info("usage_user")
        self.assertLess(user_info["balance"], 1000)  # 原本 10 元


class TestRegenerateAPIKey(unittest.TestCase):
    """重新生成 API Key 测试"""

    def setUp(self):
        """测试前准备"""
        import billing
        from pathlib import Path
        self.temp_dir = tempfile.mkdtemp()
        billing.DB_PATH = Path(os.path.join(self.temp_dir, "test_users.db"))
        billing.init_db()
        
        from billing import register_user
        success, msg = register_user("regen_user", "pass", "regen@example.com")
        
        import re
        match = re.search(r'API Key: (yn_[A-Za-z0-9_-]+)', msg)
        self.original_key = match.group(1) if match else None

    def tearDown(self):
        """测试后清理"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_regenerate_api_key(self):
        """测试重新生成 API Key"""
        from billing import regenerate_api_key, verify_api_key
        
        # 重新生成
        success, new_key = regenerate_api_key("regen_user")
        
        self.assertTrue(success)
        self.assertNotEqual(new_key, self.original_key)
        
        # 新 Key 应有效
        valid, user, _ = verify_api_key(new_key)
        self.assertTrue(valid)
        
        # 旧 Key 应失效
        valid, user, _ = verify_api_key(self.original_key)
        self.assertFalse(valid)


if __name__ == '__main__':
    unittest.main(verbosity=2)