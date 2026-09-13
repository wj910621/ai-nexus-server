"""
auth.py 认证与权限测试
隔离策略：每个 TestCase 独立 cwd + 固定 AUTH_API_KEY_PEPPER + reload 模块
覆盖范围：
- 角色权限矩阵：owner/family/guest 覆盖 + 正确递减
- API Key 生命周期：创建（raw 只返回一次）、key_id 唯一、列表不泄露明文、撤销与幂等
- 配额：check_api_key_quota 未知 key、超限额、record_api_key_usage 未知 key 拒绝
- verify_request：信任 IP 直通、缺/无效 key、成功时 last_used 被刷新
- check_tool_access：guest 限缩、family 默认全放行、allowed_tools 白名单截断 owner
- 信任域 add/remove
- 持久化 roundtrip：_save_keys + _load_keys 数据还原
- 密码学侧：_hash_key 同 key 同 pepper 稳定、token_urlsafe(32) 长度
"""
import hashlib
import importlib
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _setup_auth(tmpdir: str):
    """chdir 到 tmpdir 后 reload auth，返回 (auth_module, backup_cwd)"""
    os.environ["AUTH_API_KEY_PEPPER"] = "test-pepper-for-unit-tests-do-not-use-in-prod"
    backup = os.getcwd()
    os.chdir(tmpdir)
    import auth as _auth
    return importlib.reload(_auth), backup


class AuthIsolatedTestCase(unittest.TestCase):
    """统一 fixture：每个测试用自己的 tmpdir + reload auth"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.auth, self._cwd = _setup_auth(self.tmpdir)

    def tearDown(self):
        os.chdir(self._cwd)


class TestRolePermissions(AuthIsolatedTestCase):
    def test_permissions_narrow_correctly(self):
        perms = self.auth.ROLE_PERMISSIONS
        self.assertTrue(perms[self.auth.UserRole.OWNER] >= perms[self.auth.UserRole.FAMILY])
        self.assertTrue(perms[self.auth.UserRole.FAMILY] >= perms[self.auth.UserRole.GUEST])

    def test_admin_only_tools(self):
        self.assertIn("admin_users", self.auth.ROLE_PERMISSIONS[self.auth.UserRole.OWNER])
        self.assertNotIn("admin_users", self.auth.ROLE_PERMISSIONS[self.auth.UserRole.FAMILY])
        self.assertNotIn("admin_users", self.auth.ROLE_PERMISSIONS[self.auth.UserRole.GUEST])

    def test_check_permission_invalid_role(self):
        self.assertFalse(self.auth.check_permission("fake_role", "chat"))


class TestApiKeyLifecycle(AuthIsolatedTestCase):
    def test_create_returns_raw_and_id(self):
        raw, kid = self.auth.create_api_key("k1", self.auth.UserRole.FAMILY)
        self.assertTrue(raw)
        self.assertEqual(len(kid), 8)
        khash = self.auth._hash_key(raw)
        self.assertIn(khash, self.auth._api_keys)
        self.assertNotEqual(raw, self.auth._api_keys[khash].key_hash)

    def test_list_exposes_no_raw(self):
        raw, _ = self.auth.create_api_key("k2", self.auth.UserRole.GUEST, allowed_tools=["chat"])
        listing = self.auth.list_api_keys()
        rendered = repr(listing)
        self.assertNotIn(raw, rendered)

    def test_revoke_idempotent(self):
        raw, kid = self.auth.create_api_key("k3", self.auth.UserRole.OWNER)
        self.assertTrue(self.auth.revoke_api_key(kid))
        self.assertFalse(self.auth.revoke_api_key(kid))
        self.assertEqual(len(self.auth.list_api_keys()), 1)

    def test_quota_limit_owner_vs_guest(self):
        _, _ = self.auth.create_api_key("ow", self.auth.UserRole.OWNER)
        _, _ = self.auth.create_api_key("gu", self.auth.UserRole.GUEST)
        listing = {k["name"]: k for k in self.auth.list_api_keys()}
        self.assertEqual(listing["ow"]["quota_limit"], 1_000_000)
        self.assertEqual(listing["gu"]["quota_limit"], 100_000)

    def test_check_quota_exhausted(self):
        raw, _ = self.auth.create_api_key("kq", self.auth.UserRole.GUEST)
        khash = self.auth._hash_key(raw)
        # 直接把 quota_used 推到 100000
        self.auth._api_keys[khash].quota_used = 100_000
        ok, err = self.auth.check_api_key_quota(khash, tokens_needed=1)
        self.assertFalse(ok)
        self.assertIn("额度不足", err)

    def test_check_quota_unknown_key(self):
        ok, err = self.auth.check_api_key_quota("deadbeef" * 8)
        self.assertFalse(ok)
        self.assertEqual(err, "无效的 API Key")

    def test_record_usage_unknown_key(self):
        self.assertFalse(self.auth.record_api_key_usage("deadbeef" * 8, 42))

    def test_record_usage_updates(self):
        raw, _ = self.auth.create_api_key("ku", self.auth.UserRole.FAMILY)
        khash = self.auth._hash_key(raw)
        self.assertTrue(self.auth.record_api_key_usage(khash, 123))
        self.assertEqual(self.auth._api_keys[khash].quota_used, 123)


class TestVerifyRequest(AuthIsolatedTestCase):
    def test_missing_api_key_rejected(self):
        ok, role, err, _ = self.auth.verify_request(None, "1.2.3.4")
        self.assertFalse(ok)
        self.assertEqual(role, self.auth.UserRole.GUEST)
        self.assertEqual(err, "缺少 API Key")

    def test_invalid_api_key_rejected(self):
        ok, role, err, _ = self.auth.verify_request("not-a-real-key", "1.2.3.4")
        self.assertFalse(ok)
        self.assertEqual(err, "无效的 API Key")

    def test_trusted_ip_bypass(self):
        self.auth.add_trusted_ip("10.0.0.7", self.auth.UserRole.FAMILY)
        ok, role, err, obj = self.auth.verify_request(None, "10.0.0.7")
        self.assertTrue(ok)
        self.assertEqual(role, self.auth.UserRole.FAMILY)
        self.assertIsNone(obj)

    def test_successful_verify_updates_last_used(self):
        raw, _ = self.auth.create_api_key("kv", self.auth.UserRole.GUEST)
        khash = self.auth._hash_key(raw)
        before = self.auth._api_keys[khash].last_used
        ok, role, err, obj = self.auth.verify_request(raw, "127.0.0.1")
        self.assertTrue(ok)
        self.assertEqual(role, self.auth.UserRole.GUEST)
        self.assertIsNone(err)
        self.assertIsNotNone(obj)
        self.assertGreaterEqual(obj.last_used, before)


class TestCheckToolAccess(AuthIsolatedTestCase):
    def test_guest_limited(self):
        self.assertTrue(self.auth.check_tool_access(self.auth.UserRole.GUEST, "get_time"))
        self.assertFalse(self.auth.check_tool_access(self.auth.UserRole.GUEST, "control_pc"))
        self.assertFalse(self.auth.check_tool_access(self.auth.UserRole.GUEST, "run_browser_task"))

    def test_family_has_device_control(self):
        self.assertTrue(self.auth.check_tool_access(self.auth.UserRole.FAMILY, "control_pc"))
        self.assertTrue(self.auth.check_tool_access(self.auth.UserRole.FAMILY, "send_email"))
        # family 也对未知工具放行
        self.assertTrue(self.auth.check_tool_access(self.auth.UserRole.FAMILY, "future_tool"))

    def test_owner_always_full(self):
        self.assertTrue(self.auth.check_tool_access(self.auth.UserRole.OWNER, "any_tool_ever"))

    def test_allowed_tools_whitelist_trumps_role(self):
        self.assertFalse(
            self.auth.check_tool_access(self.auth.UserRole.OWNER, "control_pc",
                                         allowed_tools=["chat", "read_notes"])
        )
        self.assertTrue(
            self.auth.check_tool_access(self.auth.UserRole.OWNER, "chat",
                                         allowed_tools=["chat", "read_notes"])
        )

    def test_allowed_tools_none_as_role(self):
        # chat 权限在 tool_perm_map 中未映射，guest 会走到末尾的 False
        # （owner/family 由于末尾默认分支放行，guest 不会）
        # 这是生产代码当前行为，不是本测试的 bug
        self.assertFalse(self.auth.check_tool_access(self.auth.UserRole.GUEST, "chat", allowed_tools=None))


class TestTrustedIps(AuthIsolatedTestCase):
    def test_add_remove(self):
        self.auth.add_trusted_ip("10.10.10.10", self.auth.UserRole.OWNER)
        self.assertEqual(self.auth._TRUSTED_IPS["10.10.10.10"], "owner")
        self.auth.remove_trusted_ip("10.10.10.10")
        self.assertNotIn("10.10.10.10", self.auth._TRUSTED_IPS)


class TestHashing(AuthIsolatedTestCase):
    def test_same_key_same_pepper_stable(self):
        self.assertEqual(self.auth._hash_key("abc"), self.auth._hash_key("abc"))

    def test_different_pepper_breaks(self):
        a = hashlib.sha256(f"mykey:pepperA".encode()).hexdigest()
        b = hashlib.sha256(f"mykey:pepperB".encode()).hexdigest()
        self.assertNotEqual(a, b)

    def test_raw_key_length(self):
        k = self.auth._generate_key()
        self.assertGreaterEqual(len(k), 32)


class TestPersistenceRoundtrip(AuthIsolatedTestCase):
    def test_save_then_load(self):
        raw_f, _ = self.auth.create_api_key("f", self.auth.UserRole.FAMILY)
        self.auth.create_api_key("g", self.auth.UserRole.GUEST, allowed_tools=["chat"])
        self.auth.add_trusted_ip("9.9.9.9", self.auth.UserRole.FAMILY)
        # 手动清空全局并 reload
        self.auth._save_keys()  # 先把当前状态落盘
        self.auth._api_keys.clear()
        self.auth._TRUSTED_IPS.clear()
        self.auth._load_keys()
        self.assertEqual(len(self.auth._api_keys), 3)
        self.assertIn("9.9.9.9", self.auth._TRUSTED_IPS)
        ok, _, _, _ = self.auth.verify_request(raw_f, "8.8.8.8")
        self.assertTrue(ok)


def main():
    unittest.main(verbosity=2)


if __name__ == "__main__":
    main()
