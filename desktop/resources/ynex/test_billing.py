"""
计费系统测试
- 用户注册与登录
- 密码哈希与验证
- API Key 管理
- 额度管理
- 余额充值
- 套餐订阅
- 分销商功能
- 计费计算
"""

import os
import sys
import tempfile
import shutil
import unittest
import warnings

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

TEST_DATA_DIR = tempfile.mkdtemp(prefix="test_billing_")


def _setup_test_env():
    os.makedirs(os.path.join(TEST_DATA_DIR, "data"), exist_ok=True)
    original_cwd = os.getcwd()
    os.chdir(TEST_DATA_DIR)
    return original_cwd


def _teardown_test_env(original_cwd):
    os.chdir(original_cwd)
    shutil.rmtree(TEST_DATA_DIR, ignore_errors=True)


class TestPasswordHashing(unittest.TestCase):
    """密码哈希测试"""

    @classmethod
    def setUpClass(cls):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            cls.original_cwd = _setup_test_env()
            import importlib
            import billing
            importlib.reload(billing)
            cls.billing = billing

    @classmethod
    def tearDownClass(cls):
        _teardown_test_env(cls.original_cwd)

    def test_hash_password_has_salt(self):
        _hash_password = self.billing._hash_password
        h1 = _hash_password("mypassword")
        self.assertIn("$", h1)
        parts = h1.split("$")
        self.assertEqual(len(parts), 2)
        self.assertEqual(len(parts[1]), 32)

    def test_hash_password_different_salts(self):
        _hash_password = self.billing._hash_password
        h1 = _hash_password("samepassword")
        h2 = _hash_password("samepassword")
        self.assertNotEqual(h1, h2)

    def test_verify_password_correct(self):
        _hash_password = self.billing._hash_password
        _verify_password = self.billing._verify_password
        h = _hash_password("testpass123")
        self.assertTrue(_verify_password("testpass123", h))

    def test_verify_password_wrong(self):
        _hash_password = self.billing._hash_password
        _verify_password = self.billing._verify_password
        h = _hash_password("correctpass")
        self.assertFalse(_verify_password("wrongpass", h))

    def test_verify_password_empty_input(self):
        _verify_password = self.billing._verify_password
        self.assertFalse(_verify_password("", "invalid"))
        self.assertFalse(_verify_password("test", ""))

    def test_verify_password_invalid_format(self):
        _verify_password = self.billing._verify_password
        self.assertFalse(_verify_password("test", "no_dollar_sign"))


class TestUserRegistration(unittest.TestCase):
    """用户注册测试"""

    @classmethod
    def setUpClass(cls):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            cls.original_cwd = _setup_test_env()
            import importlib
            import billing
            importlib.reload(billing)
            cls.billing = billing

    @classmethod
    def tearDownClass(cls):
        _teardown_test_env(cls.original_cwd)

    def test_register_success(self):
        register_user = self.billing.register_user
        ok, msg = register_user("testuser01", "password123", "test01@example.com")
        self.assertTrue(ok)
        self.assertIn("注册成功", msg)
        self.assertIn("API Key", msg)

    def test_register_duplicate_username(self):
        register_user = self.billing.register_user
        register_user("dupuser", "pass1", "dup1@example.com")
        ok, msg = register_user("dupuser", "pass2", "dup2@example.com")
        self.assertFalse(ok)
        self.assertIn("已被注册", msg)

    def test_register_duplicate_email(self):
        register_user = self.billing.register_user
        register_user("user_a", "pass1", "same@example.com")
        ok, msg = register_user("user_b", "pass2", "same@example.com")
        self.assertFalse(ok)
        self.assertIn("已被注册", msg)

    def test_register_generates_api_key(self):
        register_user = self.billing.register_user
        ok, msg = register_user("user_apikey", "pass123", "apikey@example.com")
        self.assertTrue(ok)
        self.assertIn("yn_", msg)


class TestUserLogin(unittest.TestCase):
    """用户登录测试"""

    @classmethod
    def setUpClass(cls):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            cls.original_cwd = _setup_test_env()
            import importlib
            import billing
            importlib.reload(billing)
            cls.billing = billing

    @classmethod
    def tearDownClass(cls):
        _teardown_test_env(cls.original_cwd)

    def test_login_success(self):
        register_user = self.billing.register_user
        login_user = self.billing.login_user
        register_user("loginuser", "mypassword", "login@example.com")
        ok, msg, user_info = login_user("loginuser", "mypassword")
        self.assertTrue(ok)
        self.assertIn("登录成功", msg)
        self.assertIsNotNone(user_info)
        self.assertEqual(user_info["username"], "loginuser")

    def test_login_wrong_password(self):
        register_user = self.billing.register_user
        login_user = self.billing.login_user
        register_user("wrongpass_user", "correctpass", "wrongpass@example.com")
        ok, msg, user_info = login_user("wrongpass_user", "wrongpassword")
        self.assertFalse(ok)
        self.assertIn("用户名或密码错误", msg)
        self.assertIsNone(user_info)

    def test_login_nonexistent_user(self):
        login_user = self.billing.login_user
        ok, msg, user_info = login_user("nobody", "password")
        self.assertFalse(ok)
        self.assertIn("用户名或密码错误", msg)

    def test_login_no_plaintext_password_in_response(self):
        register_user = self.billing.register_user
        login_user = self.billing.login_user
        register_user("nopass_user", "secret123", "nopass@example.com")
        ok, _, user_info = login_user("nopass_user", "secret123")
        self.assertTrue(ok)
        self.assertNotIn("password_hash", user_info)

    def test_login_api_key_prefix_only(self):
        register_user = self.billing.register_user
        login_user = self.billing.login_user
        ok, msg = register_user("prefix_user", "pass123", "prefix@example.com")
        self.assertTrue(ok)
        raw_key = msg.split("API Key: ")[1].split("（")[0]
        ok, _, user_info = login_user("prefix_user", "pass123")
        self.assertTrue(ok)
        self.assertEqual(len(user_info["api_key"]), 8)
        self.assertTrue(raw_key.startswith(user_info["api_key"]))


class TestApiKeyVerification(unittest.TestCase):
    """API Key 验证测试"""

    @classmethod
    def setUpClass(cls):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            cls.original_cwd = _setup_test_env()
            import importlib
            import billing
            importlib.reload(billing)
            cls.billing = billing

    @classmethod
    def tearDownClass(cls):
        _teardown_test_env(cls.original_cwd)

    def test_verify_valid_api_key(self):
        register_user = self.billing.register_user
        verify_api_key = self.billing.verify_api_key
        ok, msg = register_user("verify_user", "pass123", "verify@example.com")
        self.assertTrue(ok)
        raw_key = msg.split("API Key: ")[1].split("（")[0]
        valid, user, err = verify_api_key(raw_key)
        self.assertTrue(valid)
        self.assertIsNotNone(user)
        self.assertEqual(user.username, "verify_user")

    def test_verify_invalid_api_key(self):
        verify_api_key = self.billing.verify_api_key
        valid, user, err = verify_api_key("invalid_key_12345")
        self.assertFalse(valid)
        self.assertIsNone(user)
        self.assertIn("无效的 API Key", err)

    def test_verify_empty_api_key(self):
        verify_api_key = self.billing.verify_api_key
        valid, user, err = verify_api_key("")
        self.assertFalse(valid)
        self.assertIsNone(user)
        self.assertIn("未提供", err)

    def test_verify_hashed_key_not_accepted(self):
        register_user = self.billing.register_user
        _hash_api_key = self.billing._hash_api_key
        verify_api_key = self.billing.verify_api_key
        ok, msg = register_user("hash_user", "pass123", "hash@example.com")
        self.assertTrue(ok)
        raw_key = msg.split("API Key: ")[1].split("（")[0]
        hashed = _hash_api_key(raw_key)
        valid, _, _ = verify_api_key(hashed)
        self.assertFalse(valid)


class TestQuotaManagement(unittest.TestCase):
    """额度管理测试"""

    @classmethod
    def setUpClass(cls):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            cls.original_cwd = _setup_test_env()
            import importlib
            import billing
            importlib.reload(billing)
            cls.billing = billing

    @classmethod
    def tearDownClass(cls):
        _teardown_test_env(cls.original_cwd)

    def test_check_quota_sufficient(self):
        register_user = self.billing.register_user
        check_quota = self.billing.check_quota
        ok, msg = register_user("quota_user1", "pass123", "quota1@example.com")
        self.assertTrue(ok)
        raw_key = msg.split("API Key: ")[1].split("（")[0]
        _, user, _ = self.billing.verify_api_key(raw_key)
        ok, msg = check_quota(user.id, 1000)
        self.assertTrue(ok)
        self.assertIn("额度充足", msg)

    def test_check_quota_insufficient_but_balance_ok(self):
        register_user = self.billing.register_user
        recharge_balance = self.billing.recharge_balance
        check_quota = self.billing.check_quota
        deduct_quota = self.billing.deduct_quota
        ok, msg = register_user("quota_user2", "pass123", "quota2@example.com")
        self.assertTrue(ok)
        raw_key = msg.split("API Key: ")[1].split("（")[0]
        _, user, _ = self.billing.verify_api_key(raw_key)
        deduct_quota(user.id, 100000, 0, 0)
        recharge_balance(user.id, 10)
        ok, msg = check_quota(user.id, 10000)
        self.assertTrue(ok)
        self.assertIn("余额充足", msg)

    def test_check_quota_insufficient_no_balance(self):
        register_user = self.billing.register_user
        check_quota = self.billing.check_quota
        deduct_quota = self.billing.deduct_quota
        ok, msg = register_user("quota_user3", "pass123", "quota3@example.com")
        self.assertTrue(ok)
        raw_key = msg.split("API Key: ")[1].split("（")[0]
        _, user, _ = self.billing.verify_api_key(raw_key)
        deduct_quota(user.id, 100000, 0, 0)
        ok, msg = check_quota(user.id, 10000)
        self.assertFalse(ok)
        self.assertIn("额度已用完", msg)

    def test_nonexistent_user_quota(self):
        check_quota = self.billing.check_quota
        ok, msg = check_quota("nonexistent_user_id", 1000)
        self.assertFalse(ok)
        self.assertIn("用户不存在", msg)


class TestRechargeBalance(unittest.TestCase):
    """余额充值测试"""

    @classmethod
    def setUpClass(cls):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            cls.original_cwd = _setup_test_env()
            import importlib
            import billing
            importlib.reload(billing)
            cls.billing = billing

    @classmethod
    def tearDownClass(cls):
        _teardown_test_env(cls.original_cwd)

    def test_recharge_positive_amount(self):
        register_user = self.billing.register_user
        recharge_balance = self.billing.recharge_balance
        get_user_info = self.billing.get_user_info
        ok, msg = register_user("recharge_user1", "pass123", "recharge1@example.com")
        self.assertTrue(ok)
        raw_key = msg.split("API Key: ")[1].split("（")[0]
        _, user, _ = self.billing.verify_api_key(raw_key)
        ok, msg = recharge_balance(user.id, 50.0)
        self.assertTrue(ok)
        info = get_user_info(user.id)
        self.assertEqual(info["balance"], 5000)

    def test_recharge_zero_amount_rejected(self):
        register_user = self.billing.register_user
        recharge_balance = self.billing.recharge_balance
        ok, msg = register_user("recharge_user2", "pass123", "recharge2@example.com")
        self.assertTrue(ok)
        raw_key = msg.split("API Key: ")[1].split("（")[0]
        _, user, _ = self.billing.verify_api_key(raw_key)
        ok, msg = recharge_balance(user.id, 0)
        self.assertFalse(ok)
        self.assertIn("大于0", msg)

    def test_recharge_negative_amount_rejected(self):
        register_user = self.billing.register_user
        recharge_balance = self.billing.recharge_balance
        ok, msg = register_user("recharge_user3", "pass123", "recharge3@example.com")
        self.assertTrue(ok)
        raw_key = msg.split("API Key: ")[1].split("（")[0]
        _, user, _ = self.billing.verify_api_key(raw_key)
        ok, msg = recharge_balance(user.id, -10)
        self.assertFalse(ok)


class TestSubscribeTier(unittest.TestCase):
    """套餐订阅测试"""

    @classmethod
    def setUpClass(cls):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            cls.original_cwd = _setup_test_env()
            import importlib
            import billing
            importlib.reload(billing)
            cls.billing = billing

    @classmethod
    def tearDownClass(cls):
        _teardown_test_env(cls.original_cwd)

    def test_subscribe_invalid_tier(self):
        register_user = self.billing.register_user
        subscribe_tier = self.billing.subscribe_tier
        ok, msg = register_user("sub_user1", "pass123", "sub1@example.com")
        self.assertTrue(ok)
        raw_key = msg.split("API Key: ")[1].split("（")[0]
        _, user, _ = self.billing.verify_api_key(raw_key)
        ok, msg = subscribe_tier(user.id, "invalid_tier")
        self.assertFalse(ok)
        self.assertIn("不存在的套餐", msg)

    def test_subscribe_insufficient_balance(self):
        register_user = self.billing.register_user
        subscribe_tier = self.billing.subscribe_tier
        ok, msg = register_user("sub_user2", "pass123", "sub2@example.com")
        self.assertTrue(ok)
        raw_key = msg.split("API Key: ")[1].split("（")[0]
        _, user, _ = self.billing.verify_api_key(raw_key)
        ok, msg = subscribe_tier(user.id, "pro")
        self.assertFalse(ok)
        self.assertIn("余额不足", msg)

    def test_subscribe_with_paid_order(self):
        register_user = self.billing.register_user
        subscribe_tier = self.billing.subscribe_tier
        get_user_info = self.billing.get_user_info
        ok, msg = register_user("sub_user3", "pass123", "sub3@example.com")
        self.assertTrue(ok)
        raw_key = msg.split("API Key: ")[1].split("（")[0]
        _, user, _ = self.billing.verify_api_key(raw_key)
        ok, msg = subscribe_tier(user.id, "pro", paid_order_amount=9.9)
        self.assertTrue(ok)
        self.assertIn("订阅成功", msg)
        info = get_user_info(user.id)
        self.assertEqual(info["role"], "pro")
        self.assertEqual(info["quota_limit"], 5000000)

    def test_subscribe_paid_order_amount_mismatch(self):
        register_user = self.billing.register_user
        subscribe_tier = self.billing.subscribe_tier
        ok, msg = register_user("sub_user4", "pass123", "sub4@example.com")
        self.assertTrue(ok)
        raw_key = msg.split("API Key: ")[1].split("（")[0]
        _, user, _ = self.billing.verify_api_key(raw_key)
        ok, msg = subscribe_tier(user.id, "pro", paid_order_amount=5.0)
        self.assertFalse(ok)
        self.assertIn("不匹配", msg)


class TestRegenerateApiKey(unittest.TestCase):
    """重新生成API Key测试"""

    @classmethod
    def setUpClass(cls):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            cls.original_cwd = _setup_test_env()
            import importlib
            import billing
            importlib.reload(billing)
            cls.billing = billing

    @classmethod
    def tearDownClass(cls):
        _teardown_test_env(cls.original_cwd)

    def test_regenerate_success(self):
        register_user = self.billing.register_user
        regenerate_api_key = self.billing.regenerate_api_key
        verify_api_key = self.billing.verify_api_key
        ok, msg = register_user("regen_user", "pass123", "regen@example.com")
        self.assertTrue(ok)
        old_key = msg.split("API Key: ")[1].split("（")[0]
        _, user, _ = verify_api_key(old_key)
        ok, new_key = regenerate_api_key(user.id)
        self.assertTrue(ok)
        self.assertTrue(new_key.startswith("yn_"))
        valid_old, _, _ = verify_api_key(old_key)
        self.assertFalse(valid_old)
        valid_new, _, _ = verify_api_key(new_key)
        self.assertTrue(valid_new)


class TestCalculateCharge(unittest.TestCase):
    """计费计算测试"""

    @classmethod
    def setUpClass(cls):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            cls.original_cwd = _setup_test_env()
            import importlib
            import billing
            importlib.reload(billing)
            cls.billing = billing

    @classmethod
    def tearDownClass(cls):
        _teardown_test_env(cls.original_cwd)

    def test_unlimited_role_free(self):
        calculate_charge = self.billing.calculate_charge
        self.assertEqual(calculate_charge(1000000, "unlimited"), 0)

    def test_pro_role_charge(self):
        calculate_charge = self.billing.calculate_charge
        charge = calculate_charge(1000000, "pro")
        self.assertEqual(charge, 80)

    def test_user_role_charge(self):
        calculate_charge = self.billing.calculate_charge
        charge = calculate_charge(1000000, "user")
        self.assertEqual(charge, 150)

    def test_agent_role_charge(self):
        calculate_charge = self.billing.calculate_charge
        charge = calculate_charge(1000000, "agent")
        self.assertEqual(charge, 50)

    def test_zero_tokens(self):
        calculate_charge = self.billing.calculate_charge
        self.assertEqual(calculate_charge(0, "user"), 0)


class TestAgentFunctionality(unittest.TestCase):
    """分销商功能测试"""

    @classmethod
    def setUpClass(cls):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            cls.original_cwd = _setup_test_env()
            import importlib
            import billing
            importlib.reload(billing)
            cls.billing = billing

    @classmethod
    def tearDownClass(cls):
        _teardown_test_env(cls.original_cwd)

    def test_get_referral_link(self):
        get_referral_link = self.billing.get_referral_link
        link = get_referral_link("test_agent_id")
        self.assertIn("ref=test_agent_id", link)
        self.assertTrue(link.startswith("https://"))

    def test_register_with_agent_referrer(self):
        register_user = self.billing.register_user
        get_user_info = self.billing.get_user_info
        create_agent_account = self.billing.create_agent_account
        ok, msg = register_user("agent_creator", "pass123", "agent_creator@example.com", None)
        self.assertTrue(ok)
        raw_key = msg.split("API Key: ")[1].split("（")[0]
        _, agent_user, _ = self.billing.verify_api_key(raw_key)
        ok, msg = create_agent_account(agent_user.id, paid_order_amount=1000.0)
        self.assertTrue(ok)
        ok, msg = register_user("referred_user", "pass123", "referred@example.com", agent_user.id)
        self.assertTrue(ok)
        raw_key2 = msg.split("API Key: ")[1].split("（")[0]
        _, ref_user, _ = self.billing.verify_api_key(raw_key2)
        info = get_user_info(ref_user.id)
        self.assertEqual(info["referrer_id"], agent_user.id)

    def test_agent_stats(self):
        get_agent_stats = self.billing.get_agent_stats
        stats = get_agent_stats("nonexistent_agent")
        self.assertIn("total_referrals", stats)
        self.assertIn("total_earned", stats)
        self.assertIn("settled_earned", stats)


class TestUserInfo(unittest.TestCase):
    """用户信息测试"""

    @classmethod
    def setUpClass(cls):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            cls.original_cwd = _setup_test_env()
            import importlib
            import billing
            importlib.reload(billing)
            cls.billing = billing

    @classmethod
    def tearDownClass(cls):
        _teardown_test_env(cls.original_cwd)

    def test_get_user_info_existing(self):
        register_user = self.billing.register_user
        get_user_info = self.billing.get_user_info
        ok, msg = register_user("info_user", "pass123", "info@example.com")
        self.assertTrue(ok)
        raw_key = msg.split("API Key: ")[1].split("（")[0]
        _, user, _ = self.billing.verify_api_key(raw_key)
        info = get_user_info(user.id)
        self.assertIsNotNone(info)
        self.assertEqual(info["username"], "info_user")
        self.assertEqual(info["email"], "info@example.com")
        self.assertIn("api_key_prefix", info)
        self.assertIn("key_exists", info)
        self.assertNotIn("password_hash", info)

    def test_get_user_info_nonexistent(self):
        get_user_info = self.billing.get_user_info
        info = get_user_info("nonexistent")
        self.assertIsNone(info)

    def test_api_key_prefix_length(self):
        register_user = self.billing.register_user
        get_user_info = self.billing.get_user_info
        ok, msg = register_user("prefix_test", "pass123", "prefix_test@example.com")
        self.assertTrue(ok)
        raw_key = msg.split("API Key: ")[1].split("（")[0]
        _, user, _ = self.billing.verify_api_key(raw_key)
        info = get_user_info(user.id)
        self.assertEqual(len(info["api_key_prefix"]), 8)
        self.assertTrue(raw_key.startswith(info["api_key_prefix"]))


def main():
    print("=== 计费系统测试 ===\n")
    unittest.main(verbosity=2, exit=False)
    print("\n=== 计费系统测试完成 ===")


if __name__ == "__main__":
    main()
