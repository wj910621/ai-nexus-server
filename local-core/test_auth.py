"""
认证模块测试
覆盖 API Key 管理、权限校验、信任域管理等核心安全功能
"""

import os
import sys
import time
import tempfile
import shutil
import unittest
from unittest.mock import patch, MagicMock

# 添加模块路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 创建临时数据目录
_test_data_dir = None


def setup_test_env():
    """设置测试环境"""
    global _test_data_dir
    _test_data_dir = tempfile.mkdtemp(prefix="ynex_test_")
    os.makedirs(_test_data_dir, exist_ok=True)
    # 临时设置 AUTH_API_KEY_PEPPER
    os.environ["AUTH_API_KEY_PEPPER"] = "test_pepper_for_unit_tests_12345"


def teardown_test_env():
    """清理测试环境"""
    global _test_data_dir
    if _test_data_dir and os.path.exists(_test_data_dir):
        shutil.rmtree(_test_data_dir)
    if "AUTH_API_KEY_PEPPER" in os.environ:
        del os.environ["AUTH_API_KEY_PEPPER"]


class TestApiKeyManagement(unittest.TestCase):
    """API Key 管理测试"""

    @classmethod
    def setUpClass(cls):
        setup_test_env()
        # 重新导入 auth 模块以使用测试环境
        import importlib
        import auth
        importlib.reload(auth)
        cls.auth = auth

    @classmethod
    def tearDownClass(cls):
        # 清理
        cls.auth._api_keys.clear()
        cls.auth._TRUSTED_IPS.clear()
        teardown_test_env()

    def setUp(self):
        """每个测试前清空状态"""
        self.auth._api_keys.clear()
        self.auth._TRUSTED_IPS.clear()

    def test_create_api_key(self):
        """测试 API Key 创建"""
        raw_key, key_id = self.auth.create_api_key(
            "测试Key", self.auth.UserRole.OWNER
        )

        # 验证返回值
        self.assertIsNotNone(raw_key)
        self.assertIsNotNone(key_id)
        self.assertEqual(len(key_id), 8)  # 8位ID

        # 验证 Key 存储在内存中（哈希形式）
        key_hash = self.auth._hash_key(raw_key)
        self.assertIn(key_hash, self.auth._api_keys)

        # 验证 Key 属性
        api_key_obj = self.auth._api_keys[key_hash]
        self.assertEqual(api_key_obj.name, "测试Key")
        self.assertEqual(api_key_obj.role, self.auth.UserRole.OWNER)
        self.assertEqual(api_key_obj.quota_limit, 1000000)  # owner配额

    def test_create_api_key_with_tools_whitelist(self):
        """测试带工具白名单的 API Key 创建"""
        allowed_tools = ["chat", "get_system_info"]
        raw_key, key_id = self.auth.create_api_key(
            "受限Key", self.auth.UserRole.FAMILY, allowed_tools=allowed_tools
        )

        key_hash = self.auth._hash_key(raw_key)
        api_key_obj = self.auth._api_keys[key_hash]

        self.assertEqual(api_key_obj.allowed_tools, allowed_tools)

    def test_revoke_api_key(self):
        """测试 API Key 撤销"""
        raw_key, key_id = self.auth.create_api_key(
            "待撤销", self.auth.UserRole.GUEST
        )

        # 撤销
        result = self.auth.revoke_api_key(key_id)
        self.assertTrue(result)

        # 验证已删除
        key_hash = self.auth._hash_key(raw_key)
        self.assertNotIn(key_hash, self.auth._api_keys)

        # 再次撤销应返回 False
        result = self.auth.revoke_api_key(key_id)
        self.assertFalse(result)

    def test_revoke_invalid_key_id(self):
        """测试撤销无效的 key_id"""
        result = self.auth.revoke_api_key("invalid123")
        self.assertFalse(result)

    def test_list_api_keys(self):
        """测试列出 API Keys"""
        # 创建多个 Key
        raw1, id1 = self.auth.create_api_key("Key1", self.auth.UserRole.OWNER)
        raw2, id2 = self.auth.create_api_key("Key2", self.auth.UserRole.FAMILY)

        keys = self.auth.list_api_keys()
        self.assertEqual(len(keys), 2)

        # 验证不包含原始密钥
        for k in keys:
            self.assertNotIn("raw", k)
            self.assertIn("id", k)
            self.assertIn("name", k)
            self.assertIn("role", k)

    def test_check_api_key_quota(self):
        """测试额度检查"""
        raw_key, _ = self.auth.create_api_key(
            "额度测试", self.auth.UserRole.FAMILY
        )
        key_hash = self.auth._hash_key(raw_key)

        # 应有充足额度
        ok, err = self.auth.check_api_key_quota(key_hash, 1000)
        self.assertTrue(ok)
        self.assertEqual(err, "")

        # 模拟消耗额度
        api_key_obj = self.auth._api_keys[key_hash]
        api_key_obj.quota_used = api_key_obj.quota_limit - 500

        # 额度不足
        ok, err = self.auth.check_api_key_quota(key_hash, 1000)
        self.assertFalse(ok)
        self.assertIn("额度不足", err)

    def test_record_api_key_usage(self):
        """测试使用量记录"""
        raw_key, _ = self.auth.create_api_key(
            "使用量测试", self.auth.UserRole.OWNER
        )
        key_hash = self.auth._hash_key(raw_key)

        initial_used = self.auth._api_keys[key_hash].quota_used

        result = self.auth.record_api_key_usage(key_hash, 100)
        self.assertTrue(result)

        self.assertEqual(
            self.auth._api_keys[key_hash].quota_used, initial_used + 100
        )

    def test_record_usage_invalid_key(self):
        """测试无效 Key 的使用量记录"""
        result = self.auth.record_api_key_usage("invalid_hash", 100)
        self.assertFalse(result)


class TestAuthVerification(unittest.TestCase):
    """认证验证测试"""

    @classmethod
    def setUpClass(cls):
        setup_test_env()
        import importlib
        import auth
        importlib.reload(auth)
        cls.auth = auth

    @classmethod
    def tearDownClass(cls):
        cls.auth._api_keys.clear()
        cls.auth._TRUSTED_IPS.clear()
        teardown_test_env()

    def setUp(self):
        self.auth._api_keys.clear()
        self.auth._TRUSTED_IPS.clear()

    def test_verify_request_valid_key(self):
        """测试有效 API Key 验证"""
        raw_key, _ = self.auth.create_api_key(
            "验证测试", self.auth.UserRole.FAMILY
        )

        ok, role, err, api_key_obj = self.auth.verify_request(raw_key, "192.168.1.100")

        self.assertTrue(ok)
        self.assertEqual(role, self.auth.UserRole.FAMILY)
        self.assertIsNone(err)
        self.assertIsNotNone(api_key_obj)

    def test_verify_request_missing_key(self):
        """测试缺少 API Key"""
        ok, role, err, api_key_obj = self.auth.verify_request(None, "192.168.1.100")

        self.assertFalse(ok)
        self.assertEqual(role, self.auth.UserRole.GUEST)
        self.assertIn("缺少", err)
        self.assertIsNone(api_key_obj)

    def test_verify_request_invalid_key(self):
        """测试无效 API Key"""
        ok, role, err, api_key_obj = self.auth.verify_request(
            "invalid_key_12345", "192.168.1.100"
        )

        self.assertFalse(ok)
        self.assertEqual(role, self.auth.UserRole.GUEST)
        self.assertIn("无效", err)
        self.assertIsNone(api_key_obj)

    def test_verify_request_trusted_ip(self):
        """测试信任 IP 直通"""
        self.auth.add_trusted_ip("192.168.1.50", self.auth.UserRole.OWNER)

        ok, role, err, api_key_obj = self.auth.verify_request(None, "192.168.1.50")

        self.assertTrue(ok)
        self.assertEqual(role, self.auth.UserRole.OWNER)
        self.assertIsNone(err)
        self.assertIsNone(api_key_obj)  # 信任IP不返回API Key对象

    def test_verify_request_updates_last_used(self):
        """测试验证时更新 last_used 时间"""
        raw_key, _ = self.auth.create_api_key(
            "时间测试", self.auth.UserRole.OWNER
        )
        key_hash = self.auth._hash_key(raw_key)

        # 初始 last_used 应为 0 或接近创建时间
        initial_time = self.auth._api_keys[key_hash].last_used

        # 等待一小段时间
        time.sleep(0.1)

        self.auth.verify_request(raw_key, "10.0.0.1")

        # last_used 应被更新
        self.assertGreater(
            self.auth._api_keys[key_hash].last_used, initial_time
        )


class TestPermissionChecks(unittest.TestCase):
    """权限检查测试"""

    @classmethod
    def setUpClass(cls):
        setup_test_env()
        import importlib
        import auth
        importlib.reload(auth)
        cls.auth = auth

    @classmethod
    def tearDownClass(cls):
        teardown_test_env()

    def test_check_permission_owner(self):
        """测试 Owner 权限"""
        # Owner 应有所有权限
        for perm in ["chat", "command", "device_control", "admin_users"]:
            self.assertTrue(
                self.auth.check_permission(self.auth.UserRole.OWNER, perm)
            )

    def test_check_permission_guest(self):
        """测试 Guest 权限限制"""
        # Guest 仅基础权限
        self.assertTrue(
            self.auth.check_permission(self.auth.UserRole.GUEST, "chat")
        )
        self.assertTrue(
            self.auth.check_permission(self.auth.UserRole.GUEST, "notify")
        )
        # Guest 无敏感权限
        self.assertFalse(
            self.auth.check_permission(self.auth.UserRole.GUEST, "device_control")
        )
        self.assertFalse(
            self.auth.check_permission(self.auth.UserRole.GUEST, "admin_config")
        )

    def test_check_permission_unknown_role(self):
        """测试未知角色"""
        # 未知角色应返回 False
        self.assertFalse(self.auth.check_permission("unknown_role", "chat"))

    def test_check_tool_access_owner(self):
        """测试 Owner 工具访问"""
        self.assertTrue(
            self.auth.check_tool_access(
                self.auth.UserRole.OWNER, "control_pc"
            )
        )
        self.assertTrue(
            self.auth.check_tool_access(
                self.auth.UserRole.OWNER, "run_browser_task"
            )
        )

    def test_check_tool_access_guest_restricted(self):
        """测试 Guest 工具访问限制"""
        # Guest 无设备控制权限
        self.assertFalse(
            self.auth.check_tool_access(
                self.auth.UserRole.GUEST, "control_pc"
            )
        )
        self.assertFalse(
            self.auth.check_tool_access(
                self.auth.UserRole.GUEST, "mqtt_publish"
            )
        )

    def test_check_tool_access_with_whitelist(self):
        """测试工具白名单限制"""
        allowed_tools = ["chat", "get_system_info"]

        # 即使是 Owner，受白名单限制
        self.assertTrue(
            self.auth.check_tool_access(
                self.auth.UserRole.OWNER, "get_system_info", allowed_tools
            )
        )
        self.assertFalse(
            self.auth.check_tool_access(
                self.auth.UserRole.OWNER, "control_pc", allowed_tools
            )
        )

    def test_check_tool_access_family_full(self):
        """测试 Family 默认工具访问"""
        # Family 默认有全部工具权限（无白名单时）
        self.assertTrue(
            self.auth.check_tool_access(
                self.auth.UserRole.FAMILY, "control_pc"
            )
        )
        self.assertTrue(
            self.auth.check_tool_access(
                self.auth.UserRole.FAMILY, "write_note"
            )
        )


class TestTrustedIpManagement(unittest.TestCase):
    """信任 IP 管理测试"""

    @classmethod
    def setUpClass(cls):
        setup_test_env()
        import importlib
        import auth
        importlib.reload(auth)
        cls.auth = auth

    @classmethod
    def tearDownClass(cls):
        teardown_test_env()

    def setUp(self):
        self.auth._TRUSTED_IPS.clear()

    def test_add_trusted_ip(self):
        """测试添加信任 IP"""
        self.auth.add_trusted_ip("10.0.0.50", self.auth.UserRole.FAMILY)

        self.assertIn("10.0.0.50", self.auth._TRUSTED_IPS)
        self.assertEqual(
            self.auth._TRUSTED_IPS["10.0.0.50"], "family"
        )

    def test_remove_trusted_ip(self):
        """测试移除信任 IP"""
        self.auth.add_trusted_ip("10.0.0.51", self.auth.UserRole.OWNER)
        self.auth.remove_trusted_ip("10.0.0.51")

        self.assertNotIn("10.0.0.51", self.auth._TRUSTED_IPS)

    def test_remove_nonexistent_ip(self):
        """测试移除不存在的 IP（不应报错）"""
        self.auth.remove_trusted_ip("10.0.0.99")  # 无操作


class TestHashFunctions(unittest.TestCase):
    """哈希函数测试"""

    @classmethod
    def setUpClass(cls):
        setup_test_env()
        import importlib
        import auth
        importlib.reload(auth)
        cls.auth = auth

    @classmethod
    def tearDownClass(cls):
        teardown_test_env()

    def test_hash_key_consistency(self):
        """测试哈希一致性"""
        key = "test_api_key_12345"
        hash1 = self.auth._hash_key(key)
        hash2 = self.auth._hash_key(key)

        self.assertEqual(hash1, hash2)
        self.assertEqual(len(hash1), 64)  # SHA256 hex

    def test_hash_key_different_keys(self):
        """测试不同 Key 产生不同哈希"""
        key1 = "key_one"
        key2 = "key_two"

        hash1 = self.auth._hash_key(key1)
        hash2 = self.auth._hash_key(key2)

        self.assertNotEqual(hash1, hash2)

    def test_generate_key_id_length(self):
        """测试 Key ID 生成长度"""
        for _ in range(10):
            key_id = self.auth._generate_key_id()
            self.assertEqual(len(key_id), 8)

    def test_generate_key_randomness(self):
        """测试 Key 生成的随机性"""
        keys = [self.auth._generate_key() for _ in range(10)]
        # 所有 Key 应不同
        self.assertEqual(len(set(keys)), 10)


def run_tests():
    """运行测试"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestApiKeyManagement))
    suite.addTests(loader.loadTestsFromTestCase(TestAuthVerification))
    suite.addTests(loader.loadTestsFromTestCase(TestPermissionChecks))
    suite.addTests(loader.loadTestsFromTestCase(TestTrustedIpManagement))
    suite.addTests(loader.loadTestsFromTestCase(TestHashFunctions))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)