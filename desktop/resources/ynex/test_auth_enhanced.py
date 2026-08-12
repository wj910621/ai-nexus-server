"""
权限认证模块测试
覆盖：API Key 管理、权限检查、配额控制、信任 IP 管理
"""

import hashlib
import os
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch, MagicMock

# 确保能导入模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import auth
from auth import (
    UserRole,
    ROLE_PERMISSIONS,
    ApiKey,
    create_api_key,
    revoke_api_key,
    list_api_keys,
    check_api_key_quota,
    record_api_key_usage,
    verify_request,
    check_permission,
    check_tool_access,
    require_auth,
    add_trusted_ip,
    remove_trusted_ip,
    _hash_key,
    _generate_key,
)


class TestAPIKeyManagement(unittest.TestCase):
    """API Key 管理测试"""

    def setUp(self):
        """每个测试前清空 API Keys"""
        # 备份原始状态
        auth._api_keys.clear()
        auth._TRUSTED_IPS.clear()
        # 设置临时数据目录
        self.temp_dir = tempfile.mkdtemp(prefix="ynex_auth_test_")
        self.data_dir = os.path.join(self.temp_dir, "data")
        os.makedirs(self.data_dir, exist_ok=True)

    def tearDown(self):
        """清理测试数据"""
        import shutil
        try:
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        except Exception:
            pass
        auth._api_keys.clear()
        auth._TRUSTED_IPS.clear()

    def test_create_api_key(self):
        """测试创建 API Key"""
        raw_key, key_id = create_api_key("测试用户", UserRole.FAMILY)

        # 验证返回值
        self.assertIsNotNone(raw_key)
        self.assertEqual(len(key_id), 8)  # 8位 ID
        self.assertTrue(len(raw_key) > 32)  # 至少32字节

        # 验证 Key 已存储
        key_hash = _hash_key(raw_key)
        self.assertIn(key_hash, auth._api_keys)

        # 验证 Key 属性
        api_key = auth._api_keys[key_hash]
        self.assertEqual(api_key.name, "测试用户")
        self.assertEqual(api_key.role, UserRole.FAMILY)
        self.assertEqual(len(api_key.key_id), 8)

    def test_create_api_key_with_tools_restriction(self):
        """测试创建带工具限制的 API Key"""
        allowed_tools = ["chat", "browser"]
        raw_key, key_id = create_api_key(
            "受限用户",
            UserRole.GUEST,
            allowed_tools=allowed_tools
        )

        key_hash = _hash_key(raw_key)
        api_key = auth._api_keys[key_hash]
        self.assertEqual(api_key.allowed_tools, allowed_tools)

    def test_revoke_api_key(self):
        """测试撤销 API Key"""
        raw_key, key_id = create_api_key("待撤销", UserRole.GUEST)

        # Key 应该存在
        key_hash = _hash_key(raw_key)
        self.assertIn(key_hash, auth._api_keys)

        # 撤销
        result = revoke_api_key(key_id)
        self.assertTrue(result)
        self.assertNotIn(key_hash, auth._api_keys)

    def test_revoke_nonexistent_key(self):
        """测试撤销不存在的 Key"""
        result = revoke_api_key("nonexist")
        self.assertFalse(result)

    def test_list_api_keys(self):
        """测试列出 API Keys"""
        # 创建多个 Key
        raw1, id1 = create_api_key("用户1", UserRole.OWNER)
        raw2, id2 = create_api_key("用户2", UserRole.FAMILY)

        keys = list_api_keys()
        self.assertEqual(len(keys), 2)

        # 验证返回的数据不包含明文 Key
        for key_data in keys:
            self.assertIn("id", key_data)
            self.assertIn("name", key_data)
            self.assertIn("role", key_data)
            self.assertNotIn("key_hash", key_data)
            self.assertNotIn("raw_key", key_data)

    def test_api_key_hashing(self):
        """测试 API Key 哈希"""
        raw1 = _generate_key()
        raw2 = _generate_key()

        # 不同 Key 应产生不同哈希
        hash1 = _hash_key(raw1)
        hash2 = _hash_key(raw2)
        self.assertNotEqual(hash1, hash2)

        # 相同 Key 应产生相同哈希
        hash3 = _hash_key(raw1)
        self.assertEqual(hash1, hash3)

        # 哈希长度应为 64 (SHA256)
        self.assertEqual(len(hash1), 64)


class TestPermissionSystem(unittest.TestCase):
    """权限系统测试"""

    def test_user_roles(self):
        """测试用户角色"""
        self.assertEqual(UserRole.OWNER.value, "owner")
        self.assertEqual(UserRole.FAMILY.value, "family")
        self.assertEqual(UserRole.GUEST.value, "guest")

    def test_role_permissions(self):
        """测试角色权限矩阵"""
        # Owner 应有所有权限
        owner_perms = ROLE_PERMISSIONS[UserRole.OWNER]
        self.assertIn("admin_users", owner_perms)
        self.assertIn("admin_config", owner_perms)
        self.assertIn("device_control", owner_perms)

        # Family 应有大部分权限，但无管理权限
        family_perms = ROLE_PERMISSIONS[UserRole.FAMILY]
        self.assertIn("device_control", family_perms)
        self.assertNotIn("admin_users", family_perms)
        self.assertNotIn("admin_config", family_perms)

        # Guest 权限最少
        guest_perms = ROLE_PERMISSIONS[UserRole.GUEST]
        self.assertIn("chat", guest_perms)
        self.assertNotIn("device_control", guest_perms)
        self.assertNotIn("email_send", guest_perms)

    def test_check_permission(self):
        """测试权限检查"""
        self.assertTrue(check_permission(UserRole.OWNER, "admin_users"))
        self.assertTrue(check_permission(UserRole.OWNER, "device_control"))

        self.assertFalse(check_permission(UserRole.FAMILY, "admin_users"))
        self.assertTrue(check_permission(UserRole.FAMILY, "device_control"))

        self.assertFalse(check_permission(UserRole.GUEST, "device_control"))
        self.assertTrue(check_permission(UserRole.GUEST, "chat"))

    def test_check_tool_access(self):
        """测试工具访问检查"""
        # GUEST 应能访问基础工具
        self.assertTrue(check_tool_access(UserRole.GUEST, "get_system_info"))
        self.assertFalse(check_tool_access(UserRole.GUEST, "control_pc"))

        # FAMILY 应能访问设备控制工具
        self.assertTrue(check_tool_access(UserRole.FAMILY, "control_pc"))
        self.assertTrue(check_tool_access(UserRole.FAMILY, "control_ha_device"))

        # OWNER 有所有工具权限
        self.assertTrue(check_tool_access(UserRole.OWNER, "admin_users"))

    def test_check_tool_access_with_whitelist(self):
        """测试工具访问白名单限制"""
        # 即使是 OWNER，如果指定了 allowed_tools，也受限制
        allowed = ["chat", "browser"]
        self.assertFalse(check_tool_access(UserRole.OWNER, "control_pc", allowed))
        self.assertTrue(check_tool_access(UserRole.OWNER, "browser", allowed))


class TestQuotaSystem(unittest.TestCase):
    """配额系统测试"""

    def setUp(self):
        auth._api_keys.clear()

    def tearDown(self):
        auth._api_keys.clear()

    def test_quota_check(self):
        """测试配额检查"""
        raw_key, key_id = create_api_key("配额测试", UserRole.FAMILY)
        key_hash = _hash_key(raw_key)

        # 初始配额应充足
        ok, msg = check_api_key_quota(key_hash, 1000)
        self.assertTrue(ok)
        self.assertEqual(msg, "")

    def test_quota_exceeded(self):
        """测试配额超限"""
        raw_key, key_id = create_api_key("配额测试", UserRole.GUEST)
        key_hash = _hash_key(raw_key)

        # 设置低配额
        auth._api_keys[key_hash].quota_limit = 100

        # 尝试使用超过配额
        auth._api_keys[key_hash].quota_used = 90
        ok, msg = check_api_key_quota(key_hash, 20)
        self.assertFalse(ok)
        self.assertIn("额度不足", msg)

    def test_quota_usage_recording(self):
        """测试配额使用记录"""
        raw_key, key_id = create_api_key("配额测试", UserRole.OWNER)
        key_hash = _hash_key(raw_key)

        # 记录使用
        initial_used = auth._api_keys[key_hash].quota_used
        result = record_api_key_usage(key_hash, 500)
        self.assertTrue(result)
        self.assertEqual(
            auth._api_keys[key_hash].quota_used,
            initial_used + 500
        )

    def test_quota_nonexistent_key(self):
        """测试不存在的 Key 配额检查"""
        ok, msg = check_api_key_quota("invalid_hash", 100)
        self.assertFalse(ok)
        self.assertIn("无效", msg)

        result = record_api_key_usage("invalid_hash", 100)
        self.assertFalse(result)


class TestAuthenticationVerification(unittest.TestCase):
    """认证验证测试"""

    def setUp(self):
        auth._api_keys.clear()
        auth._TRUSTED_IPS.clear()

    def tearDown(self):
        auth._api_keys.clear()
        auth._TRUSTED_IPS.clear()

    def test_verify_request_valid_key(self):
        """测试有效 API Key 验证"""
        raw_key, key_id = create_api_key("验证测试", UserRole.FAMILY)

        ok, role, err, key_obj = verify_request(raw_key, "192.168.1.100")
        self.assertTrue(ok)
        self.assertEqual(role, UserRole.FAMILY)
        self.assertIsNone(err)
        self.assertIsNotNone(key_obj)

    def test_verify_request_missing_key(self):
        """测试缺少 API Key"""
        ok, role, err, key_obj = verify_request(None, "192.168.1.100")
        self.assertFalse(ok)
        self.assertEqual(role, UserRole.GUEST)
        self.assertIn("缺少", err)

    def test_verify_request_invalid_key(self):
        """测试无效 API Key"""
        ok, role, err, key_obj = verify_request("invalid_key_12345", "192.168.1.100")
        self.assertFalse(ok)
        self.assertEqual(role, UserRole.GUEST)
        self.assertIn("无效", err)

    def test_verify_request_trusted_ip(self):
        """测试信任 IP 直通"""
        add_trusted_ip("192.168.1.200", UserRole.OWNER)

        ok, role, err, key_obj = verify_request(None, "192.168.1.200")
        self.assertTrue(ok)
        self.assertEqual(role, UserRole.OWNER)
        self.assertIsNone(err)
        self.assertIsNone(key_obj)

    def test_verify_request_last_used_update(self):
        """测试最后使用时间更新"""
        raw_key, key_id = create_api_key("时间测试", UserRole.GUEST)
        key_hash = _hash_key(raw_key)
        initial_time = auth._api_keys[key_hash].last_used

        # 验证请求应更新 last_used
        verify_request(raw_key, "127.0.0.1")
        updated_time = auth._api_keys[key_hash].last_used

        self.assertGreater(updated_time, initial_time)


class TestTrustedIPManagement(unittest.TestCase):
    """信任 IP 管理测试"""

    def setUp(self):
        auth._TRUSTED_IPS.clear()

    def tearDown(self):
        auth._TRUSTED_IPS.clear()

    def test_add_trusted_ip(self):
        """测试添加信任 IP"""
        add_trusted_ip("192.168.1.100", UserRole.FAMILY)
        self.assertIn("192.168.1.100", auth._TRUSTED_IPS)
        self.assertEqual(auth._TRUSTED_IPS["192.168.1.100"], "family")

    def test_remove_trusted_ip(self):
        """测试移除信任 IP"""
        add_trusted_ip("192.168.1.100", UserRole.OWNER)
        remove_trusted_ip("192.168.1.100")
        self.assertNotIn("192.168.1.100", auth._TRUSTED_IPS)

    def test_trusted_ip_override(self):
        """测试信任 IP 覆盖"""
        add_trusted_ip("10.0.0.1", UserRole.GUEST)
        add_trusted_ip("10.0.0.1", UserRole.OWNER)  # 覆盖
        self.assertEqual(auth._TRUSTED_IPS["10.0.0.1"], "owner")


class TestConcurrencyAndThreadSafety(unittest.TestCase):
    """并发和线程安全测试"""

    def setUp(self):
        auth._api_keys.clear()

    def tearDown(self):
        auth._api_keys.clear()

    def test_concurrent_key_creation(self):
        """测试并发 Key 创建"""
        errors = []
        created_keys = []

        def create_key_thread(name):
            try:
                for i in range(10):
                    raw, kid = create_api_key(f"{name}_{i}", UserRole.GUEST)
                    created_keys.append((raw, kid))
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=create_key_thread, args=(f"thread_{i}",))
            for i in range(5)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"并发创建失败: {errors}")
        # 应该创建了 50 个 Key
        self.assertEqual(len(created_keys), 50)

    def test_concurrent_quota_update(self):
        """测试并发配额更新"""
        raw_key, key_id = create_api_key("并发测试", UserRole.OWNER)
        key_hash = _hash_key(raw_key)

        errors = []

        def update_quota():
            try:
                for _ in range(100):
                    record_api_key_usage(key_hash, 1)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=update_quota) for _ in range(10)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0)
        # 应该记录了 1000 次使用
        self.assertEqual(auth._api_keys[key_hash].quota_used, 1000)


class TestEdgeCasesAndBoundaryConditions(unittest.TestCase):
    """边界条件和极端情况测试"""

    def setUp(self):
        auth._api_keys.clear()

    def test_empty_key_name(self):
        """测试空名称 Key"""
        raw, kid = create_api_key("", UserRole.GUEST)
        self.assertIsNotNone(raw)
        self.assertEqual(len(kid), 8)

    def test_long_key_name(self):
        """测试长名称 Key"""
        long_name = "a" * 1000
        raw, kid = create_api_key(long_name, UserRole.OWNER)
        self.assertEqual(auth._api_keys[_hash_key(raw)].name, long_name)

    def test_special_characters_in_name(self):
        """测试名称中的特殊字符"""
        special_name = "用户<script>alert(1)</script>"
        raw, kid = create_api_key(special_name, UserRole.GUEST)
        self.assertIsNotNone(raw)

    def test_tool_access_with_none_allowed_tools(self):
        """测试 allowed_tools=None 时的工具访问"""
        # None 表示不限制
        self.assertTrue(check_tool_access(UserRole.OWNER, "any_tool", None))
        self.assertTrue(check_tool_access(UserRole.FAMILY, "device_control", None))

    def test_empty_allowed_tools_list(self):
        """测试空工具白名单"""
        # 空列表应拒绝所有工具
        self.assertFalse(check_tool_access(UserRole.OWNER, "any_tool", []))

    def test_key_id_uniqueness(self):
        """测试 Key ID 唯一性"""
        key_ids = set()
        for _ in range(1000):
            _, kid = create_api_key("test", UserRole.GUEST)
            key_ids.add(kid)

        # 应该全部唯一（碰撞概率极低）
        self.assertEqual(len(key_ids), 1000)

    def test_quota_boundary(self):
        """测试配额边界值"""
        raw, kid = create_api_key("边界测试", UserRole.GUEST)
        key_hash = _hash_key(raw)
        auth._api_keys[key_hash].quota_limit = 100

        # 刚好到边界
        auth._api_keys[key_hash].quota_used = 99
        ok, _ = check_api_key_quota(key_hash, 1)
        self.assertTrue(ok)

        # 超过边界
        auth._api_keys[key_hash].quota_used = 100
        ok, msg = check_api_key_quota(key_hash, 1)
        self.assertFalse(ok)

    def test_negative_quota_usage(self):
        """测试负配额使用"""
        raw, kid = create_api_key("负数测试", UserRole.OWNER)
        key_hash = _hash_key(raw)

        # 尝试记录负使用（应该被允许，逻辑由调用方控制）
        result = record_api_key_usage(key_hash, -100)
        self.assertTrue(result)
        # 配额应该减少
        self.assertLess(auth._api_keys[key_hash].quota_used, 0)


def run_tests():
    """运行所有测试"""
    import unittest

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestAPIKeyManagement))
    suite.addTests(loader.loadTestsFromTestCase(TestPermissionSystem))
    suite.addTests(loader.loadTestsFromTestCase(TestQuotaSystem))
    suite.addTests(loader.loadTestsFromTestCase(TestAuthenticationVerification))
    suite.addTests(loader.loadTestsFromTestCase(TestTrustedIPManagement))
    suite.addTests(loader.loadTestsFromTestCase(TestConcurrencyAndThreadSafety))
    suite.addTests(loader.loadTestsFromTestCase(TestEdgeCasesAndBoundaryConditions))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "=" * 60)
    print("权限认证模块测试结果")
    print("=" * 60)
    print(f"运行测试: {result.testsRun}")
    print(f"成功: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"失败: {len(result.failures)}")
    print(f"错误: {len(result.errors)}")

    return result.wasSuccessful()


if __name__ == "__main__":
    import sys
    success = run_tests()
    sys.exit(0 if success else 1)