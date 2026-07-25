"""
Y·NEX认证模块测试
测试覆盖：
- API Key管理（创建、验证、撤销）
- 权限校验（OWNER/FAMILY/GUEST三级）
- 工具访问控制
- 配额管理
- 信任IP管理
- 持久化
"""

import os
import json
import tempfile
import unittest
from unittest.mock import patch, MagicMock
import time

# 在导入auth之前设置测试环境
os.environ.setdefault("AUTH_API_KEY_PEPPER", "test_pepper_for_testing_only")

from auth import (
    UserRole,
    ApiKey,
    create_api_key,
    revoke_api_key,
    list_api_keys,
    verify_request,
    check_permission,
    check_tool_access,
    check_api_key_quota,
    record_api_key_usage,
    add_trusted_ip,
    remove_trusted_ip,
    ROLE_PERMISSIONS,
    _hash_key,
    _generate_key,
    _generate_key_id,
    _api_keys,
    _TRUSTED_IPS,
)


class TestApiKeyManagement(unittest.TestCase):
    """API Key管理测试"""

    def setUp(self):
        """测试前清理"""
        # 保存原始状态
        self._original_keys = _api_keys.copy()
        _api_keys.clear()

    def tearDown(self):
        """测试后恢复"""
        _api_keys.clear()
        _api_keys.update(self._original_keys)

    def test_create_api_key(self):
        """测试API Key创建"""
        raw_key, key_id = create_api_key("测试用户", UserRole.FAMILY)

        # 验证返回值
        self.assertIsNotNone(raw_key)
        self.assertEqual(len(key_id), 8)  # 8位ID
        self.assertTrue(len(raw_key) > 32)  # 密钥长度

        # 验证存储
        key_hash = _hash_key(raw_key)
        self.assertIn(key_hash, _api_keys)

        # 验证元数据
        stored_key = _api_keys[key_hash]
        self.assertEqual(stored_key.name, "测试用户")
        self.assertEqual(stored_key.role, UserRole.FAMILY)
        self.assertEqual(stored_key.key_id, key_id)

    def test_create_with_tool_whitelist(self):
        """测试创建带工具白名单的Key"""
        allowed_tools = ["chat", "command"]
        raw_key, key_id = create_api_key("受限用户", UserRole.GUEST, allowed_tools=allowed_tools)

        key_hash = _hash_key(raw_key)
        stored_key = _api_keys[key_hash]
        self.assertEqual(stored_key.allowed_tools, allowed_tools)

    def test_revoke_api_key(self):
        """测试API Key撤销"""
        raw_key, key_id = create_api_key("待撤销用户", UserRole.GUEST)

        # 撤销
        result = revoke_api_key(key_id)
        self.assertTrue(result)

        # 验证已删除
        key_hash = _hash_key(raw_key)
        self.assertNotIn(key_hash, _api_keys)

    def test_revoke_nonexistent_key(self):
        """测试撤销不存在的Key"""
        result = revoke_api_key("notexist")
        self.assertFalse(result)

    def test_list_api_keys(self):
        """测试列出API Keys"""
        raw1, id1 = create_api_key("用户1", UserRole.OWNER)
        raw2, id2 = create_api_key("用户2", UserRole.GUEST)

        keys = list_api_keys()
        self.assertEqual(len(keys), 2)

        # 验证不包含原始密钥
        for key_info in keys:
            self.assertNotIn("raw_key", key_info)
            self.assertIn("id", key_info)
            self.assertIn("name", key_info)
            self.assertIn("role", key_info)

    def test_key_hashing(self):
        """测试密钥哈希"""
        raw_key = "test_key_123"
        hash1 = _hash_key(raw_key)
        hash2 = _hash_key(raw_key)

        # 相同密钥相同哈希
        self.assertEqual(hash1, hash2)
        # 哈希长度正确
        self.assertEqual(len(hash1), 64)  # SHA256 hex


class TestAuthentication(unittest.TestCase):
    """认证验证测试"""

    def setUp(self):
        _api_keys.clear()
        _TRUSTED_IPS.clear()

    def tearDown(self):
        _api_keys.clear()
        _TRUSTED_IPS.clear()

    def test_verify_valid_key(self):
        """测试有效密钥验证"""
        raw_key, key_id = create_api_key("测试用户", UserRole.FAMILY)

        ok, role, err, api_key_obj = verify_request(raw_key, "192.168.1.100")

        self.assertTrue(ok)
        self.assertEqual(role, UserRole.FAMILY)
        self.assertIsNone(err)
        self.assertIsNotNone(api_key_obj)

    def test_verify_invalid_key(self):
        """测试无效密钥验证"""
        ok, role, err, api_key_obj = verify_request("invalid_key", "192.168.1.100")

        self.assertFalse(ok)
        self.assertEqual(role, UserRole.GUEST)
        self.assertEqual(err, "无效的 API Key")
        self.assertIsNone(api_key_obj)

    def test_verify_missing_key(self):
        """测试缺失密钥验证"""
        ok, role, err, api_key_obj = verify_request(None, "192.168.1.100")

        self.assertFalse(ok)
        self.assertEqual(err, "缺少 API Key")

    def test_trusted_ip_bypass(self):
        """测试信任IP绕过认证"""
        add_trusted_ip("192.168.1.100", UserRole.OWNER)

        ok, role, err, api_key_obj = verify_request(None, "192.168.1.100")

        self.assertTrue(ok)
        self.assertEqual(role, UserRole.OWNER)
        self.assertIsNone(api_key_obj)

    def test_last_used_update(self):
        """测试last_used字段更新"""
        raw_key, _ = create_api_key("测试用户", UserRole.GUEST)
        key_hash = _hash_key(raw_key)

        before = _api_keys[key_hash].last_used
        time.sleep(0.1)

        verify_request(raw_key, "192.168.1.100")
        after = _api_keys[key_hash].last_used

        self.assertGreater(after, before)


class TestPermissionSystem(unittest.TestCase):
    """权限系统测试"""

    def test_role_permissions_exist(self):
        """测试角色权限定义完整"""
        for role in UserRole:
            self.assertIn(role, ROLE_PERMISSIONS)
            self.assertIsInstance(ROLE_PERMISSIONS[role], set)
            self.assertGreater(len(ROLE_PERMISSIONS[role]), 0)

    def test_owner_has_all_permissions(self):
        """测试OWNER拥有所有权限"""
        owner_perms = ROLE_PERMISSIONS[UserRole.OWNER]
        for role in [UserRole.FAMILY, UserRole.GUEST]:
            role_perms = ROLE_PERMISSIONS[role]
            # OWNER权限包含其他角色权限
            self.assertTrue(owner_perms.issuperset(role_perms))

    def test_guest_least_permissions(self):
        """测试GUEST权限最少"""
        guest_perms = ROLE_PERMISSIONS[UserRole.GUEST]
        for role in [UserRole.OWNER, UserRole.FAMILY]:
            role_perms = ROLE_PERMISSIONS[role]
            # GUEST权限最少
            self.assertTrue(role_perms.issuperset(guest_perms))

    def test_check_permission_valid(self):
        """测试权限校验有效"""
        self.assertTrue(check_permission(UserRole.OWNER, "chat"))
        self.assertTrue(check_permission(UserRole.FAMILY, "device_control"))
        self.assertTrue(check_permission(UserRole.GUEST, "note_read"))

    def test_check_permission_invalid(self):
        """测试权限校验无效"""
        self.assertFalse(check_permission(UserRole.GUEST, "device_control"))
        self.assertFalse(check_permission(UserRole.GUEST, "admin_config"))

    def test_check_permission_unknown(self):
        """测试未知权限"""
        self.assertFalse(check_permission(UserRole.OWNER, "nonexistent_permission"))


class TestToolAccessControl(unittest.TestCase):
    """工具访问控制测试"""

    def test_owner_tool_access(self):
        """测试OWNER工具访问"""
        # OWNER有所有工具权限
        self.assertTrue(check_tool_access(UserRole.OWNER, "control_pc"))
        self.assertTrue(check_tool_access(UserRole.OWNER, "admin_users"))

    def test_family_tool_access(self):
        """测试FAMILY工具访问"""
        self.assertTrue(check_tool_access(UserRole.FAMILY, "control_ha_device"))
        self.assertTrue(check_tool_access(UserRole.FAMILY, "set_reminder"))
        # FAMILY在当前实现中有所有工具权限（与OWNER相同）
        # 如果需要限制，应通过allowed_tools白名单实现

    def test_guest_tool_access(self):
        """测试GUEST工具访问"""
        # GUEST仅能访问基础工具
        self.assertTrue(check_tool_access(UserRole.GUEST, "get_system_info"))
        self.assertFalse(check_tool_access(UserRole.GUEST, "control_pc"))
        self.assertFalse(check_tool_access(UserRole.GUEST, "send_email"))

    def test_tool_whitelist_restriction(self):
        """测试工具白名单限制"""
        # 即使OWNER，如果指定了allowed_tools，也受限制
        allowed_tools = ["chat", "get_system_info"]
        self.assertTrue(check_tool_access(UserRole.OWNER, "chat", allowed_tools))
        self.assertFalse(check_tool_access(UserRole.OWNER, "control_pc", allowed_tools))

    def test_guest_with_whitelist(self):
        """测试GUEST加白名单"""
        allowed_tools = ["chat"]
        # GUEST本身没权限的工具，即使白名单有也无效
        self.assertFalse(check_tool_access(UserRole.GUEST, "control_pc", allowed_tools))


class TestQuotaManagement(unittest.TestCase):
    """配额管理测试"""

    def setUp(self):
        _api_keys.clear()

    def tearDown(self):
        _api_keys.clear()

    def test_quota_check_pass(self):
        """测试配额检查通过"""
        raw_key, _ = create_api_key("测试用户", UserRole.FAMILY)
        key_hash = _hash_key(raw_key)

        ok, err = check_api_key_quota(key_hash, 1000)
        self.assertTrue(ok)
        self.assertEqual(err, "")

    def test_quota_check_fail(self):
        """测试配额不足"""
        raw_key, _ = create_api_key("测试用户", UserRole.FAMILY)
        key_hash = _hash_key(raw_key)

        # 设置已用配额接近限制
        _api_keys[key_hash].quota_used = 99900

        ok, err = check_api_key_quota(key_hash, 1000)
        self.assertFalse(ok)
        self.assertIn("额度不足", err)

    def test_quota_record_usage(self):
        """测试配额记录"""
        raw_key, _ = create_api_key("测试用户", UserRole.FAMILY)
        key_hash = _hash_key(raw_key)

        before = _api_keys[key_hash].quota_used
        result = record_api_key_usage(key_hash, 500)

        self.assertTrue(result)
        self.assertEqual(_api_keys[key_hash].quota_used, before + 500)

    def test_quota_invalid_key(self):
        """测试无效Key配额操作"""
        ok, err = check_api_key_quota("invalid_hash", 100)
        self.assertFalse(ok)
        self.assertIn("无效", err)

        result = record_api_key_usage("invalid_hash", 100)
        self.assertFalse(result)

    def test_owner_higher_quota(self):
        """测试OWNER更高默认配额"""
        _, _ = create_api_key("普通用户", UserRole.FAMILY)
        raw_key, _ = create_api_key("管理员", UserRole.OWNER)

        # OWNER配额应高于FAMILY
        owner_key = _api_keys[_hash_key(raw_key)]
        family_keys = [k for k in _api_keys.values() if k.role == UserRole.FAMILY]
        if family_keys:
            self.assertGreater(owner_key.quota_limit, family_keys[0].quota_limit)


class TestTrustedIpManagement(unittest.TestCase):
    """信任IP管理测试"""

    def setUp(self):
        _TRUSTED_IPS.clear()

    def tearDown(self):
        _TRUSTED_IPS.clear()

    def test_add_trusted_ip(self):
        """测试添加信任IP"""
        add_trusted_ip("192.168.1.100", UserRole.FAMILY)

        self.assertIn("192.168.1.100", _TRUSTED_IPS)
        self.assertEqual(_TRUSTED_IPS["192.168.1.100"], UserRole.FAMILY.value)

    def test_remove_trusted_ip(self):
        """测试移除信任IP"""
        add_trusted_ip("192.168.1.100", UserRole.OWNER)
        remove_trusted_ip("192.168.1.100")

        self.assertNotIn("192.168.1.100", _TRUSTED_IPS)

    def test_remove_nonexistent_ip(self):
        """测试移除不存在的IP"""
        # 不应抛异常
        remove_trusted_ip("192.168.1.999")


class TestKeyGeneration(unittest.TestCase):
    """密钥生成测试"""

    def test_generate_key_uniqueness(self):
        """测试密钥唯一性"""
        keys = set()
        for _ in range(100):
            key = _generate_key()
            self.assertNotIn(key, keys)
            keys.add(key)

    def test_generate_key_id_length(self):
        """测试Key ID长度"""
        for _ in range(10):
            key_id = _generate_key_id()
            self.assertEqual(len(key_id), 8)
            # 验证是hex字符串
            int(key_id, 16)


class TestEdgeCases(unittest.TestCase):
    """边界条件测试"""

    def setUp(self):
        _api_keys.clear()

    def tearDown(self):
        _api_keys.clear()

    def test_empty_key_name(self):
        """测试空密钥名称"""
        # 应该允许，名称只是元数据
        raw_key, key_id = create_api_key("", UserRole.GUEST)
        self.assertIsNotNone(raw_key)

    def test_concurrent_key_operations(self):
        """测试并发密钥操作（基础测试）"""
        # 创建多个Key
        keys = []
        for i in range(10):
            raw, key_id = create_api_key(f"用户{i}", UserRole.FAMILY)
            keys.append((raw, key_id))

        # 验证所有Key有效
        for raw, _ in keys:
            ok, _, _, _ = verify_request(raw, "127.0.0.1")
            self.assertTrue(ok)

    def test_special_characters_in_name(self):
        """测试名称中的特殊字符"""
        special_name = "用户<script>alert(1)</script>"
        raw_key, _ = create_api_key(special_name, UserRole.GUEST)

        # 验证存储（不执行XSS）
        key_hash = _hash_key(raw_key)
        self.assertEqual(_api_keys[key_hash].name, special_name)


if __name__ == "__main__":
    unittest.main(verbosity=2)