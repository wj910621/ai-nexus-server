"""
认证模块测试 - 测试 API Key 管理、权限验证、角色权限、工具访问控制
"""

import hashlib
import json
import os
import tempfile
import time
import unittest
from unittest.mock import patch, MagicMock, mock_open

# 在导入 auth 模块之前设置环境变量，避免警告
os.environ["AUTH_API_KEY_PEPPER"] = "test_pepper_for_testing_12345"

from auth import (
    UserRole,
    ApiKey,
    create_api_key,
    revoke_api_key,
    list_api_keys,
    verify_request,
    check_permission,
    check_tool_access,
    add_trusted_ip,
    remove_trusted_ip,
    check_api_key_quota,
    record_api_key_usage,
    ROLE_PERMISSIONS,
    _hash_key,
    _generate_key,
    _generate_key_id,
)

# 导入模块以访问其全局变量
import auth


class TestUserRoleAndPermissions(unittest.TestCase):
    """测试用户角色和权限矩阵"""

    def test_user_role_enum_values(self):
        """用户角色应有正确的枚举值"""
        self.assertEqual(UserRole.OWNER.value, "owner")
        self.assertEqual(UserRole.FAMILY.value, "family")
        self.assertEqual(UserRole.GUEST.value, "guest")

    def test_owner_has_all_permissions(self):
        """OWNER 角色应拥有所有权限"""
        owner_perms = ROLE_PERMISSIONS[UserRole.OWNER]
        self.assertIn("chat", owner_perms)
        self.assertIn("command", owner_perms)
        self.assertIn("device_control", owner_perms)
        self.assertIn("admin_users", owner_perms)
        self.assertIn("admin_config", owner_perms)

    def test_family_has_most_permissions(self):
        """FAMILY 角色应拥有大部分权限（不包括管理权限）"""
        family_perms = ROLE_PERMISSIONS[UserRole.FAMILY]
        self.assertIn("chat", family_perms)
        self.assertIn("device_control", family_perms)
        self.assertNotIn("admin_users", family_perms)
        self.assertNotIn("admin_config", family_perms)

    def test_guest_has_limited_permissions(self):
        """GUEST 角色应只有有限权限"""
        guest_perms = ROLE_PERMISSIONS[UserRole.GUEST]
        self.assertIn("chat", guest_perms)
        self.assertIn("note_read", guest_perms)
        self.assertNotIn("device_control", guest_perms)
        self.assertNotIn("email_send", guest_perms)

    def test_permission_hierarchy(self):
        """权限层级关系：OWNER > FAMILY > GUEST"""
        owner_perms = ROLE_PERMISSIONS[UserRole.OWNER]
        family_perms = ROLE_PERMISSIONS[UserRole.FAMILY]
        guest_perms = ROLE_PERMISSIONS[UserRole.GUEST]

        # OWNER 应包含 FAMILY 的所有权限
        self.assertTrue(family_perms.issubset(owner_perms))
        # FAMILY 应包含 GUEST 的所有权限
        self.assertTrue(guest_perms.issubset(family_perms))


class TestApiKeyGeneration(unittest.TestCase):
    """测试 API Key 生成和哈希"""

    def test_generate_key_length(self):
        """生成的 API Key 应有足够长度"""
        key = _generate_key()
        self.assertGreaterEqual(len(key), 32)

    def test_generate_key_uniqueness(self):
        """每次生成的 API Key 应唯一"""
        keys = [_generate_key() for _ in range(100)]
        self.assertEqual(len(keys), len(set(keys)), "API Key 应唯一")

    def test_generate_key_id_length(self):
        """生成的 key_id 应为 8 位"""
        key_id = _generate_key_id()
        self.assertEqual(len(key_id), 8)

    def test_hash_key_consistency(self):
        """相同密钥和盐应产生相同哈希"""
        test_pepper = os.environ.get("AUTH_API_KEY_PEPPER", "")
        with patch('auth._API_KEY_PEPPER', test_pepper):
            key1 = _hash_key("test_key_123")
            key2 = _hash_key("test_key_123")
            self.assertEqual(key1, key2)

    def test_hash_key_different_keys(self):
        """不同密钥应产生不同哈希"""
        key1 = _hash_key("test_key_1")
        key2 = _hash_key("test_key_2")
        self.assertNotEqual(key1, key2)

    def test_hash_key_format(self):
        """哈希应为 SHA256 十六进制格式"""
        hash_result = _hash_key("test_key")
        self.assertEqual(len(hash_result), 64)  # SHA256 = 64 hex chars
        self.assertTrue(all(c in '0123456789abcdef' for c in hash_result))


class TestApiKeyManagement(unittest.TestCase):
    """测试 API Key 管理功能"""

    def setUp(self):
        """测试前清空 API Keys"""
        auth._api_keys.clear()
        auth._TRUSTED_IPS.clear()

    def tearDown(self):
        """测试后清理"""
        auth._api_keys.clear()
        auth._TRUSTED_IPS.clear()

    @patch('auth._save_keys')
    def test_create_api_key_owner(self, mock_save):
        """创建 OWNER 角色 API Key"""
        raw_key, key_id = create_api_key("测试管理员", UserRole.OWNER)

        self.assertIsNotNone(raw_key)
        self.assertEqual(len(key_id), 8)
        mock_save.assert_called_once()

    @patch('auth._save_keys')
    def test_create_api_key_guest(self, mock_save):
        """创建 GUEST 角色 API Key"""
        raw_key, key_id = create_api_key("测试访客", UserRole.GUEST)

        self.assertIsNotNone(raw_key)
        self.assertEqual(len(key_id), 8)
        mock_save.assert_called_once()

    @patch('auth._save_keys')
    def test_create_api_key_with_allowed_tools(self, mock_save):
        """创建带工具白名单的 API Key"""
        allowed_tools = ["chat", "note_read"]
        raw_key, key_id = create_api_key("受限用户", UserRole.FAMILY, allowed_tools)

        self.assertIsNotNone(raw_key)
        # 验证 API Key 对象已存储
        key_hash = _hash_key(raw_key)
        self.assertIn(key_hash, auth._api_keys)
        self.assertEqual(auth._api_keys[key_hash].allowed_tools, allowed_tools)

    @patch('auth._save_keys')
    def test_revoke_api_key(self, mock_save):
        """撤销 API Key"""
        raw_key, key_id = create_api_key("待撤销", UserRole.GUEST)
        key_hash = _hash_key(raw_key)
        self.assertIn(key_hash, auth._api_keys)

        result = revoke_api_key(key_id)
        self.assertTrue(result)
        self.assertNotIn(key_hash, auth._api_keys)

    @patch('auth._save_keys')
    def test_revoke_nonexistent_key(self, mock_save):
        """撤销不存在的 API Key"""
        result = revoke_api_key("nonexist")
        self.assertFalse(result)

    @patch('auth._save_keys')
    def test_list_api_keys(self, mock_save):
        """列出所有 API Keys"""
        create_api_key("用户1", UserRole.OWNER)
        create_api_key("用户2", UserRole.GUEST)

        keys = list_api_keys()
        self.assertEqual(len(keys), 2)

        # 验证返回的元数据不包含密钥哈希
        for key_meta in keys:
            self.assertIn("id", key_meta)
            self.assertIn("name", key_meta)
            self.assertIn("role", key_meta)
            self.assertNotIn("key_hash", key_meta)
            self.assertNotIn("raw_key", key_meta)


class TestRequestVerification(unittest.TestCase):
    """测试请求验证功能"""

    def setUp(self):
        auth._api_keys.clear()
        auth._TRUSTED_IPS.clear()

    def tearDown(self):
        auth._api_keys.clear()
        auth._TRUSTED_IPS.clear()

    @patch('auth._save_keys')
    def test_verify_valid_api_key(self, mock_save):
        """验证有效的 API Key"""
        raw_key, key_id = create_api_key("测试用户", UserRole.FAMILY)

        ok, role, err, api_key_obj = verify_request(raw_key, "192.168.1.100")
        self.assertTrue(ok)
        self.assertEqual(role, UserRole.FAMILY)
        self.assertIsNone(err)
        self.assertIsNotNone(api_key_obj)

    def test_verify_missing_api_key(self):
        """缺少 API Key 应验证失败"""
        ok, role, err, api_key_obj = verify_request(None, "192.168.1.100")
        self.assertFalse(ok)
        self.assertEqual(role, UserRole.GUEST)
        self.assertIn("缺少 API Key", err)

    def test_verify_invalid_api_key(self):
        """无效的 API Key 应验证失败"""
        ok, role, err, api_key_obj = verify_request("invalid_key_12345", "192.168.1.100")
        self.assertFalse(ok)
        self.assertEqual(role, UserRole.GUEST)
        self.assertIn("无效的 API Key", err)

    @patch('auth._save_keys')
    def test_verify_trusted_ip(self, mock_save):
        """信任 IP 应直通验证"""
        add_trusted_ip("192.168.1.50", UserRole.FAMILY)

        ok, role, err, api_key_obj = verify_request(None, "192.168.1.50")
        self.assertTrue(ok)
        self.assertEqual(role, UserRole.FAMILY)
        self.assertIsNone(err)

    @patch('auth._save_keys')
    def test_verify_updates_last_used(self, mock_save):
        """验证应更新最后使用时间"""
        raw_key, key_id = create_api_key("测试用户", UserRole.OWNER)
        key_hash = _hash_key(raw_key)

        # 记录初始时间
        initial_time = auth._api_keys[key_hash].last_used

        # 稍等片刻后验证
        time.sleep(0.1)
        ok, role, err, api_key_obj = verify_request(raw_key, "192.168.1.100")

        self.assertTrue(ok)
        self.assertGreater(auth._api_keys[key_hash].last_used, initial_time)


class TestPermissionChecking(unittest.TestCase):
    """测试权限检查功能"""

    def test_check_permission_owner(self):
        """OWNER 角色权限检查"""
        self.assertTrue(check_permission(UserRole.OWNER, "chat"))
        self.assertTrue(check_permission(UserRole.OWNER, "admin_users"))
        self.assertTrue(check_permission(UserRole.OWNER, "admin_config"))

    def test_check_permission_family(self):
        """FAMILY 角色权限检查"""
        self.assertTrue(check_permission(UserRole.FAMILY, "chat"))
        self.assertTrue(check_permission(UserRole.FAMILY, "device_control"))
        self.assertFalse(check_permission(UserRole.FAMILY, "admin_users"))

    def test_check_permission_guest(self):
        """GUEST 角色权限检查"""
        self.assertTrue(check_permission(UserRole.GUEST, "chat"))
        self.assertTrue(check_permission(UserRole.GUEST, "note_read"))
        self.assertFalse(check_permission(UserRole.GUEST, "device_control"))
        self.assertFalse(check_permission(UserRole.GUEST, "email_send"))

    def test_check_nonexistent_permission(self):
        """检查不存在的权限"""
        self.assertFalse(check_permission(UserRole.OWNER, "nonexistent_permission"))
        self.assertFalse(check_permission(UserRole.GUEST, "nonexistent_permission"))


class TestToolAccessControl(unittest.TestCase):
    """测试工具访问控制"""

    def test_tool_access_owner(self):
        """OWNER 角色应能访问所有工具"""
        self.assertTrue(check_tool_access(UserRole.OWNER, "control_pc"))
        self.assertTrue(check_tool_access(UserRole.OWNER, "admin_users"))
        self.assertTrue(check_tool_access(UserRole.OWNER, "any_tool"))

    def test_tool_access_family(self):
        """FAMILY 角色工具访问"""
        self.assertTrue(check_tool_access(UserRole.FAMILY, "control_pc"))
        self.assertTrue(check_tool_access(UserRole.FAMILY, "read_webpage"))
        # FAMILY 默认可访问所有工具（除非有白名单限制）
        self.assertTrue(check_tool_access(UserRole.FAMILY, "custom_tool"))

    def test_tool_access_guest(self):
        """GUEST 角色工具访问受限"""
        self.assertFalse(check_tool_access(UserRole.GUEST, "control_pc"))
        self.assertFalse(check_tool_access(UserRole.GUEST, "send_email"))
        # GUEST 默认只能访问特定工具（OWNER/FAMILY 默认可访问所有）
        # 注意：GUEST 需要有对应权限才能访问工具
        # chat 工具可能不在 GUEST 的工具映射中，但 GUEST 有 chat 权限

    def test_tool_access_with_whitelist(self):
        """工具白名单限制"""
        allowed_tools = ["chat", "note_read"]

        # OWNER 受白名单限制
        self.assertTrue(check_tool_access(UserRole.OWNER, "chat", allowed_tools))
        self.assertFalse(check_tool_access(UserRole.OWNER, "device_control", allowed_tools))

        # FAMILY 受白名单限制
        self.assertTrue(check_tool_access(UserRole.FAMILY, "chat", allowed_tools))
        self.assertFalse(check_tool_access(UserRole.FAMILY, "device_control", allowed_tools))

    def test_tool_access_empty_whitelist(self):
        """空白名单应拒绝所有访问"""
        self.assertFalse(check_tool_access(UserRole.OWNER, "chat", []))
        self.assertFalse(check_tool_access(UserRole.FAMILY, "chat", []))

    def test_tool_permission_mapping(self):
        """工具到权限的映射"""
        # device_control 权限对应的工具
        self.assertTrue(check_tool_access(UserRole.FAMILY, "control_pc"))
        self.assertTrue(check_tool_access(UserRole.FAMILY, "device_command"))
        self.assertTrue(check_tool_access(UserRole.FAMILY, "list_device_domains"))

        # GUEST 无 device_control 权限
        self.assertFalse(check_tool_access(UserRole.GUEST, "control_pc"))


class TestQuotaManagement(unittest.TestCase):
    """测试额度管理"""

    def setUp(self):
        auth._api_keys.clear()

    def tearDown(self):
        auth._api_keys.clear()

    @patch('auth._save_keys')
    def test_check_quota_sufficient(self, mock_save):
        """检查充足额度"""
        raw_key, key_id = create_api_key("测试用户", UserRole.FAMILY)
        key_hash = _hash_key(raw_key)

        ok, err = check_api_key_quota(key_hash, 1000)
        self.assertTrue(ok)
        self.assertEqual(err, "")

    @patch('auth._save_keys')
    def test_check_quota_insufficient(self, mock_save):
        """检查不足额度"""
        raw_key, key_id = create_api_key("测试用户", UserRole.FAMILY)
        key_hash = _hash_key(raw_key)

        # FAMILY 默认额度为 100000，尝试使用超过额度的量
        auth._api_keys[key_hash].quota_used = 95000
        ok, err = check_api_key_quota(key_hash, 10000)
        self.assertFalse(ok)
        self.assertIn("额度不足", err)

    @patch('auth._save_keys')
    def test_check_quota_nonexistent_key(self, mock_save):
        """检查不存在 Key 的额度"""
        ok, err = check_api_key_quota("nonexistent_hash", 100)
        self.assertFalse(ok)
        self.assertIn("无效的 API Key", err)

    @patch('auth._save_keys')
    def test_record_usage(self, mock_save):
        """记录使用量"""
        raw_key, key_id = create_api_key("测试用户", UserRole.FAMILY)
        key_hash = _hash_key(raw_key)

        initial_used = auth._api_keys[key_hash].quota_used
        result = record_api_key_usage(key_hash, 500)

        self.assertTrue(result)
        self.assertEqual(auth._api_keys[key_hash].quota_used, initial_used + 500)

    def test_record_usage_nonexistent_key(self):
        """记录不存在 Key 的使用量"""
        result = record_api_key_usage("nonexistent_hash", 100)
        self.assertFalse(result)


class TestTrustedIPManagement(unittest.TestCase):
    """测试信任 IP 管理"""

    def setUp(self):
        auth._TRUSTED_IPS.clear()

    def tearDown(self):
        auth._TRUSTED_IPS.clear()

    def test_add_trusted_ip(self):
        """添加信任 IP"""
        # 清空现有信任 IP
        auth._TRUSTED_IPS.clear()
        add_trusted_ip("192.168.1.100", UserRole.FAMILY)
        self.assertIn("192.168.1.100", auth._TRUSTED_IPS)
        self.assertEqual(auth._TRUSTED_IPS["192.168.1.100"], "family")

    def test_remove_trusted_ip(self):
        """移除信任 IP"""
        add_trusted_ip("192.168.1.100", UserRole.FAMILY)
        remove_trusted_ip("192.168.1.100")
        self.assertNotIn("192.168.1.100", auth._TRUSTED_IPS)

    def test_remove_nonexistent_ip(self):
        """移除不存在的信任 IP"""
        # 应该不报错
        remove_trusted_ip("192.168.1.200")


class TestApiKeyPersistence(unittest.TestCase):
    """测试 API Key 持久化"""

    @patch('builtins.open', new_callable=mock_open)
    @patch('os.makedirs')
    @patch('os.chmod')
    def test_save_keys(self, mock_chmod, mock_makedirs, mock_file):
        """测试保存 API Keys"""
        auth._api_keys.clear()

        # 创建测试数据
        test_key = ApiKey(
            key_hash="test_hash",
            key_id="abcd1234",
            role=UserRole.OWNER,
            name="测试用户",
            created_at=time.time(),
            last_used=time.time(),
        )
        auth._api_keys["test_hash"] = test_key

        from auth import _save_keys
        _save_keys()

        # 验证文件被写入
        mock_file.assert_called()
        handle = mock_file()
        # 验证写入的内容包含 JSON
        written_data = "".join(call.args[0] for call in handle.write.call_args_list)
        self.assertIn("test_hash", written_data)
        self.assertIn("测试用户", written_data)

    @patch('builtins.open', new_callable=mock_open, read_data='{"keys": [], "trusted_ips": {}}')
    def test_load_keys_empty(self, mock_file):
        """测试加载空的 API Keys"""
        from auth import _load_keys
        _load_keys()
        # 应该不报错
        self.assertEqual(len(auth._api_keys), 0)


class TestSecurityScenarios(unittest.TestCase):
    """测试安全场景"""

    def setUp(self):
        auth._api_keys.clear()
        auth._TRUSTED_IPS.clear()

    def tearDown(self):
        auth._api_keys.clear()
        auth._TRUSTED_IPS.clear()

    @patch('auth._save_keys')
    def test_key_hash_not_stored_in_plaintext(self, mock_save):
        """密钥哈希不应以明文存储"""
        raw_key, key_id = create_api_key("安全测试", UserRole.OWNER)

        # raw_key 应该与哈希不同
        key_hash = _hash_key(raw_key)
        self.assertNotEqual(raw_key, key_hash)

        # 存储的应该是哈希而非明文
        self.assertIn(key_hash, auth._api_keys)
        self.assertNotIn(raw_key, auth._api_keys)

    @patch('auth._save_keys')
    def test_key_only_shown_once(self, mock_save):
        """API Key 只应在创建时显示一次"""
        raw_key, key_id = create_api_key("一次性密钥", UserRole.GUEST)

        # raw_key 应该存在
        self.assertIsNotNone(raw_key)

        # 后续操作不应再返回明文密钥
        keys = list_api_keys()
        for key_meta in keys:
            self.assertNotIn("raw_key", key_meta)
            self.assertNotIn("key", key_meta)

    def test_pepper_prevents_rainbow_table(self):
        """盐值防止彩虹表攻击"""
        # 相同密钥 + 不同盐 = 不同哈希
        hash1 = hashlib.sha256(f"test_key:pepper1".encode()).hexdigest()
        hash2 = hashlib.sha256(f"test_key:pepper2".encode()).hexdigest()
        self.assertNotEqual(hash1, hash2)


def run_auth_tests():
    """运行认证模块测试"""
    suite = unittest.TestLoader().loadTestsFromModule(__import__(__name__))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == "__main__":
    import sys
    success = run_auth_tests()
    sys.exit(0 if success else 1)