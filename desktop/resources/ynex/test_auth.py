"""
认证授权模块测试
- API Key 管理
- 权限矩阵与角色校验
- 信任IP管理
- 额度管理
"""

import os
import sys
import json
import tempfile
import shutil
import unittest
import warnings

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

TEST_DATA_DIR = tempfile.mkdtemp(prefix="test_auth_")


def _setup_test_env():
    """隔离测试环境：重定向 data 目录到临时目录"""
    os.makedirs(os.path.join(TEST_DATA_DIR, "data"), exist_ok=True)
    original_cwd = os.getcwd()
    os.chdir(TEST_DATA_DIR)
    return original_cwd


def _teardown_test_env(original_cwd):
    os.chdir(original_cwd)
    shutil.rmtree(TEST_DATA_DIR, ignore_errors=True)


class TestUserRole(unittest.TestCase):
    """用户角色枚举测试"""

    @classmethod
    def setUpClass(cls):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            cls.original_cwd = _setup_test_env()
            import importlib
            import auth
            importlib.reload(auth)
            cls.auth_module = auth

    @classmethod
    def tearDownClass(cls):
        _teardown_test_env(cls.original_cwd)

    def test_role_values(self):
        UserRole = self.auth_module.UserRole
        self.assertEqual(UserRole.OWNER.value, "owner")
        self.assertEqual(UserRole.FAMILY.value, "family")
        self.assertEqual(UserRole.GUEST.value, "guest")

    def test_role_count(self):
        UserRole = self.auth_module.UserRole
        self.assertEqual(len(list(UserRole)), 3)


class TestRolePermissions(unittest.TestCase):
    """权限矩阵测试"""

    @classmethod
    def setUpClass(cls):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            cls.original_cwd = _setup_test_env()
            import importlib
            import auth
            importlib.reload(auth)
            cls.auth_module = auth

    @classmethod
    def tearDownClass(cls):
        _teardown_test_env(cls.original_cwd)

    def test_owner_has_all_permissions(self):
        UserRole = self.auth_module.UserRole
        check_permission = self.auth_module.check_permission
        perms = [
            "chat", "command", "device_control", "ha_control",
            "reminder", "note_read", "note_write",
            "system_info", "calendar", "email_read", "email_send",
            "browser", "mqtt", "automation_rules",
            "admin_users", "admin_config", "admin_skills",
            "wake_remote", "notify",
        ]
        for p in perms:
            self.assertTrue(check_permission(UserRole.OWNER, p), f"owner 应有 {p} 权限")

    def test_family_lacks_admin_permissions(self):
        UserRole = self.auth_module.UserRole
        check_permission = self.auth_module.check_permission
        self.assertFalse(check_permission(UserRole.FAMILY, "admin_users"))
        self.assertFalse(check_permission(UserRole.FAMILY, "admin_config"))
        self.assertFalse(check_permission(UserRole.FAMILY, "admin_skills"))

    def test_family_has_core_permissions(self):
        UserRole = self.auth_module.UserRole
        check_permission = self.auth_module.check_permission
        for p in ["chat", "command", "device_control", "ha_control",
                  "browser", "note_write", "email_send"]:
            self.assertTrue(check_permission(UserRole.FAMILY, p), f"family 应有 {p} 权限")

    def test_guest_minimal_permissions(self):
        UserRole = self.auth_module.UserRole
        check_permission = self.auth_module.check_permission
        self.assertTrue(check_permission(UserRole.GUEST, "chat"))
        self.assertTrue(check_permission(UserRole.GUEST, "note_read"))
        self.assertTrue(check_permission(UserRole.GUEST, "system_info"))
        self.assertTrue(check_permission(UserRole.GUEST, "notify"))

    def test_guest_lacks_sensitive_permissions(self):
        UserRole = self.auth_module.UserRole
        check_permission = self.auth_module.check_permission
        for p in ["command", "device_control", "ha_control",
                  "note_write", "email_send", "browser",
                  "admin_users", "admin_config"]:
            self.assertFalse(check_permission(UserRole.GUEST, p), f"guest 不应有 {p} 权限")

    def test_invalid_role_has_no_permissions(self):
        check_permission = self.auth_module.check_permission
        self.assertFalse(check_permission("invalid_role", "chat"))


class TestToolAccess(unittest.TestCase):
    """工具访问权限测试"""

    @classmethod
    def setUpClass(cls):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            cls.original_cwd = _setup_test_env()
            import importlib
            import auth
            importlib.reload(auth)
            cls.auth_module = auth

    @classmethod
    def tearDownClass(cls):
        _teardown_test_env(cls.original_cwd)

    def test_owner_can_use_all_tools(self):
        UserRole = self.auth_module.UserRole
        check_tool_access = self.auth_module.check_tool_access
        tools = ["control_pc", "control_ha_device", "write_note",
                 "send_email", "read_webpage", "mqtt_publish"]
        for t in tools:
            self.assertTrue(check_tool_access(UserRole.OWNER, t), f"owner 应能使用 {t}")

    def test_guest_cannot_use_sensitive_tools(self):
        UserRole = self.auth_module.UserRole
        check_tool_access = self.auth_module.check_tool_access
        for t in ["control_pc", "write_note", "send_email", "mqtt_publish"]:
            self.assertFalse(check_tool_access(UserRole.GUEST, t), f"guest 不应使用 {t}")

    def test_allowed_tools_whitelist_restricts_owner(self):
        UserRole = self.auth_module.UserRole
        check_tool_access = self.auth_module.check_tool_access
        allowed = ["chat", "get_system_info"]
        self.assertTrue(check_tool_access(UserRole.OWNER, "chat", allowed_tools=allowed))
        self.assertFalse(check_tool_access(UserRole.OWNER, "control_pc", allowed_tools=allowed))

    def test_allowed_tools_empty_list_denies_all(self):
        UserRole = self.auth_module.UserRole
        check_tool_access = self.auth_module.check_tool_access
        self.assertFalse(check_tool_access(UserRole.OWNER, "chat", allowed_tools=[]))


class TestApiKeyManagement(unittest.TestCase):
    """API Key 管理测试"""

    @classmethod
    def setUpClass(cls):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            cls.original_cwd = _setup_test_env()
            import importlib
            import auth
            importlib.reload(auth)
            cls.auth_module = auth

    @classmethod
    def tearDownClass(cls):
        _teardown_test_env(cls.original_cwd)

    def setUp(self):
        UserRole = self.auth_module.UserRole
        create_api_key = self.auth_module.create_api_key
        list_api_keys = self.auth_module.list_api_keys
        revoke_api_key = self.auth_module.revoke_api_key
        for k in list_api_keys():
            revoke_api_key(k["id"])

    def test_create_api_key_returns_raw_and_id(self):
        UserRole = self.auth_module.UserRole
        create_api_key = self.auth_module.create_api_key
        raw, key_id = create_api_key("test_key", UserRole.OWNER)
        self.assertTrue(len(raw) > 0)
        self.assertTrue(len(key_id) == 8)

    def test_create_api_key_different_roles(self):
        UserRole = self.auth_module.UserRole
        create_api_key = self.auth_module.create_api_key
        list_api_keys = self.auth_module.list_api_keys
        create_api_key("owner_key", UserRole.OWNER)
        create_api_key("family_key", UserRole.FAMILY)
        create_api_key("guest_key", UserRole.GUEST)
        keys = list_api_keys()
        roles = {k["role"] for k in keys}
        self.assertIn("owner", roles)
        self.assertIn("family", roles)
        self.assertIn("guest", roles)

    def test_create_api_key_owner_has_higher_quota(self):
        UserRole = self.auth_module.UserRole
        create_api_key = self.auth_module.create_api_key
        list_api_keys = self.auth_module.list_api_keys
        create_api_key("owner_key", UserRole.OWNER)
        create_api_key("family_key", UserRole.FAMILY)
        keys = {k["role"]: k for k in list_api_keys()}
        self.assertEqual(keys["owner"]["quota_limit"], 1000000)
        self.assertEqual(keys["family"]["quota_limit"], 100000)

    def test_revoke_api_key(self):
        UserRole = self.auth_module.UserRole
        create_api_key = self.auth_module.create_api_key
        list_api_keys = self.auth_module.list_api_keys
        revoke_api_key = self.auth_module.revoke_api_key
        _, key_id = create_api_key("to_revoke", UserRole.GUEST)
        self.assertEqual(len(list_api_keys()), 1)
        result = revoke_api_key(key_id)
        self.assertTrue(result)
        self.assertEqual(len(list_api_keys()), 0)

    def test_revoke_nonexistent_key_returns_false(self):
        revoke_api_key = self.auth_module.revoke_api_key
        result = revoke_api_key("nonexistent")
        self.assertFalse(result)

    def test_list_api_keys_no_plaintext(self):
        UserRole = self.auth_module.UserRole
        create_api_key = self.auth_module.create_api_key
        list_api_keys = self.auth_module.list_api_keys
        raw, _ = create_api_key("test", UserRole.OWNER)
        keys = list_api_keys()
        for k in keys:
            self.assertNotIn(raw, str(k))
            self.assertNotIn("key_hash", k)


class TestApiKeyQuota(unittest.TestCase):
    """API Key 额度测试"""

    @classmethod
    def setUpClass(cls):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            cls.original_cwd = _setup_test_env()
            import importlib
            import auth
            importlib.reload(auth)
            cls.auth_module = auth

    @classmethod
    def tearDownClass(cls):
        _teardown_test_env(cls.original_cwd)

    def setUp(self):
        UserRole = self.auth_module.UserRole
        create_api_key = self.auth_module.create_api_key
        list_api_keys = self.auth_module.list_api_keys
        revoke_api_key = self.auth_module.revoke_api_key
        for k in list_api_keys():
            revoke_api_key(k["id"])

    def test_quota_check_sufficient(self):
        UserRole = self.auth_module.UserRole
        _hash_key = self.auth_module._hash_key
        create_api_key = self.auth_module.create_api_key
        check_api_key_quota = self.auth_module.check_api_key_quota
        raw, _ = create_api_key("test", UserRole.OWNER)
        key_hash = _hash_key(raw)
        ok, msg = check_api_key_quota(key_hash, 100)
        self.assertTrue(ok)
        self.assertEqual(msg, "")

    def test_quota_check_insufficient(self):
        UserRole = self.auth_module.UserRole
        _hash_key = self.auth_module._hash_key
        create_api_key = self.auth_module.create_api_key
        check_api_key_quota = self.auth_module.check_api_key_quota
        record_api_key_usage = self.auth_module.record_api_key_usage
        raw, _ = create_api_key("test", UserRole.GUEST)
        key_hash = _hash_key(raw)
        record_api_key_usage(key_hash, 99999)
        ok, msg = check_api_key_quota(key_hash, 1000)
        self.assertFalse(ok)
        self.assertIn("额度不足", msg)

    def test_quota_check_invalid_key(self):
        check_api_key_quota = self.auth_module.check_api_key_quota
        ok, msg = check_api_key_quota("invalid_hash", 100)
        self.assertFalse(ok)
        self.assertEqual(msg, "无效的 API Key")

    def test_record_usage_increments_quota(self):
        UserRole = self.auth_module.UserRole
        _hash_key = self.auth_module._hash_key
        create_api_key = self.auth_module.create_api_key
        list_api_keys = self.auth_module.list_api_keys
        record_api_key_usage = self.auth_module.record_api_key_usage
        raw, key_id = create_api_key("test", UserRole.OWNER)
        key_hash = _hash_key(raw)
        record_api_key_usage(key_hash, 5000)
        keys = {k["id"]: k for k in list_api_keys()}
        self.assertEqual(keys[key_id]["quota_used"], 5000)

    def test_record_usage_invalid_key(self):
        record_api_key_usage = self.auth_module.record_api_key_usage
        result = record_api_key_usage("invalid_hash", 100)
        self.assertFalse(result)


class TestVerifyRequest(unittest.TestCase):
    """请求验证测试"""

    @classmethod
    def setUpClass(cls):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            cls.original_cwd = _setup_test_env()
            import importlib
            import auth
            importlib.reload(auth)
            cls.auth_module = auth

    @classmethod
    def tearDownClass(cls):
        _teardown_test_env(cls.original_cwd)

    def setUp(self):
        UserRole = self.auth_module.UserRole
        create_api_key = self.auth_module.create_api_key
        list_api_keys = self.auth_module.list_api_keys
        revoke_api_key = self.auth_module.revoke_api_key
        add_trusted_ip = self.auth_module.add_trusted_ip
        remove_trusted_ip = self.auth_module.remove_trusted_ip
        for k in list_api_keys():
            revoke_api_key(k["id"])
        remove_trusted_ip("192.168.1.100")

    def test_missing_api_key_rejected(self):
        UserRole = self.auth_module.UserRole
        verify_request = self.auth_module.verify_request
        ok, role, err, _ = verify_request(None, "10.0.0.1")
        self.assertFalse(ok)
        self.assertEqual(role, UserRole.GUEST)
        self.assertIn("缺少 API Key", err)

    def test_invalid_api_key_rejected(self):
        UserRole = self.auth_module.UserRole
        verify_request = self.auth_module.verify_request
        ok, role, err, _ = verify_request("invalid_key", "10.0.0.1")
        self.assertFalse(ok)
        self.assertEqual(role, UserRole.GUEST)
        self.assertIn("无效的 API Key", err)

    def test_valid_api_key_accepted(self):
        UserRole = self.auth_module.UserRole
        create_api_key = self.auth_module.create_api_key
        verify_request = self.auth_module.verify_request
        raw, _ = create_api_key("test", UserRole.OWNER)
        ok, role, err, api_key_obj = verify_request(raw, "10.0.0.1")
        self.assertTrue(ok)
        self.assertEqual(role, UserRole.OWNER)
        self.assertIsNone(err)
        self.assertIsNotNone(api_key_obj)

    def test_trusted_ip_bypasses_auth(self):
        UserRole = self.auth_module.UserRole
        add_trusted_ip = self.auth_module.add_trusted_ip
        verify_request = self.auth_module.verify_request
        add_trusted_ip("192.168.1.100", UserRole.FAMILY)
        ok, role, err, _ = verify_request(None, "192.168.1.100")
        self.assertTrue(ok)
        self.assertEqual(role, UserRole.FAMILY)
        self.assertIsNone(err)

    def test_api_key_updates_last_used(self):
        UserRole = self.auth_module.UserRole
        _hash_key = self.auth_module._hash_key
        create_api_key = self.auth_module.create_api_key
        list_api_keys = self.auth_module.list_api_keys
        verify_request = self.auth_module.verify_request
        raw, key_id = create_api_key("test", UserRole.OWNER)
        keys_before = {k["id"]: k for k in list_api_keys()}
        self.assertEqual(keys_before[key_id]["last_used"], 0)
        verify_request(raw, "10.0.0.1")
        keys_after = {k["id"]: k for k in list_api_keys()}
        self.assertGreater(keys_after[key_id]["last_used"], 0)


class TestTrustedIpManagement(unittest.TestCase):
    """信任IP管理测试"""

    @classmethod
    def setUpClass(cls):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            cls.original_cwd = _setup_test_env()
            import importlib
            import auth
            importlib.reload(auth)
            cls.auth_module = auth

    @classmethod
    def tearDownClass(cls):
        _teardown_test_env(cls.original_cwd)

    def setUp(self):
        remove_trusted_ip = self.auth_module.remove_trusted_ip
        remove_trusted_ip("10.0.0.1")
        remove_trusted_ip("192.168.1.1")

    def test_add_and_remove_trusted_ip(self):
        UserRole = self.auth_module.UserRole
        add_trusted_ip = self.auth_module.add_trusted_ip
        remove_trusted_ip = self.auth_module.remove_trusted_ip
        verify_request = self.auth_module.verify_request
        add_trusted_ip("10.0.0.1", UserRole.OWNER)
        ok, role, _, _ = verify_request(None, "10.0.0.1")
        self.assertTrue(ok)
        self.assertEqual(role, UserRole.OWNER)
        remove_trusted_ip("10.0.0.1")
        ok, _, _, _ = verify_request(None, "10.0.0.1")
        self.assertFalse(ok)

    def test_remove_nonexistent_ip_no_error(self):
        remove_trusted_ip = self.auth_module.remove_trusted_ip
        try:
            remove_trusted_ip("999.999.999.999")
        except Exception as e:
            self.fail(f"移除不存在的IP不应抛出异常: {e}")


class TestHashKey(unittest.TestCase):
    """密钥哈希测试"""

    @classmethod
    def setUpClass(cls):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            cls.original_cwd = _setup_test_env()
            import importlib
            import auth
            importlib.reload(auth)
            cls.auth_module = auth

    @classmethod
    def tearDownClass(cls):
        _teardown_test_env(cls.original_cwd)

    def test_hash_is_deterministic(self):
        _hash_key = self.auth_module._hash_key
        h1 = _hash_key("test_key")
        h2 = _hash_key("test_key")
        self.assertEqual(h1, h2)

    def test_hash_differs_for_different_keys(self):
        _hash_key = self.auth_module._hash_key
        h1 = _hash_key("key_a")
        h2 = _hash_key("key_b")
        self.assertNotEqual(h1, h2)

    def test_hash_is_hex_string(self):
        _hash_key = self.auth_module._hash_key
        h = _hash_key("test")
        self.assertEqual(len(h), 64)
        self.assertTrue(all(c in "0123456789abcdef" for c in h))

    def test_generate_key_unique(self):
        _generate_key = self.auth_module._generate_key
        keys = {_generate_key() for _ in range(100)}
        self.assertEqual(len(keys), 100)


class TestPersistence(unittest.TestCase):
    """持久化测试"""

    @classmethod
    def setUpClass(cls):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            cls.original_cwd = _setup_test_env()

    @classmethod
    def tearDownClass(cls):
        _teardown_test_env(cls.original_cwd)

    def test_keys_survive_module_reload(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            import importlib
            import auth
            importlib.reload(auth)
            UserRole = auth.UserRole
            create_api_key = auth.create_api_key
            list_api_keys = auth.list_api_keys
            revoke_api_key = auth.revoke_api_key
            default_keys = list_api_keys()
            for k in default_keys:
                revoke_api_key(k["id"])
            _, key_id = create_api_key("persistent_key", UserRole.FAMILY)
            keys_before = [k for k in list_api_keys() if k["name"] == "persistent_key"]
            self.assertEqual(len(keys_before), 1)
            importlib.reload(auth)
            keys = auth.list_api_keys()
            persistent_keys = [k for k in keys if k["name"] == "persistent_key"]
            self.assertEqual(len(persistent_keys), 1)
            self.assertEqual(persistent_keys[0]["id"], key_id)
            self.assertEqual(persistent_keys[0]["role"], "family")


def main():
    print("=== 认证授权模块测试 ===\n")
    unittest.main(verbosity=2, exit=False)
    print("\n=== 认证授权模块测试完成 ===")


if __name__ == "__main__":
    main()
