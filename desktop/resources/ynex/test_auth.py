"""
auth.py 测试
覆盖：
- 角色权限矩阵（OWNER/FAMILY/GUEST）
- create/revoke API Key 全流程
- verify_request：信任 IP 直通、无效 Key 拦截、角色返回
- check_permission / check_tool_access（含 allowed_tools 白名单限制）
- 额度检查 check_api_key_quota 与 record_api_key_usage
- 持久化 _save_keys / _load_keys 的数据格式与兼容
- 初始 Key 文件创建路径

注意：本测试为独立脚本，运行前会替换 logger 与 config，并在临时目录下执行，
      避免污染真实 data/api_keys.json 与默认用户环境。
运行：python3 test_auth.py
"""

import hashlib
import os
import secrets
import sys
import tempfile
import unittest
from unittest import mock

# ---------------------------------------------------------------------------
# mock logger/config，避免 loguru/pydantic_settings 依赖
# ---------------------------------------------------------------------------
_placeholder_logger = mock.MagicMock()
_placeholder_logger.warning = lambda *a, **k: None
_placeholder_logger.info = lambda *a, **k: None
_placeholder_logger.error = lambda *a, **k: None
sys.modules["logger"] = mock.MagicMock(logger=_placeholder_logger)
sys.modules["config"] = mock.MagicMock(settings=mock.MagicMock())

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)


class TestAuth(unittest.TestCase):
    """每个用例都在独立的临时工作目录中执行，保证文件侧隔离。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._cwd = os.getcwd()
        os.chdir(self._tmp.name)
        # 固定 API Key 盐，使哈希在整个测试会话中保持稳定
        os.environ["AUTH_API_KEY_PEPPER"] = "unit-test-pepper"

        # 重新加载 auth 模块以在隔离上下文中使用干净的全局变量
        import importlib
        import auth as _auth_mod
        importlib.reload(_auth_mod)
        self.auth = _auth_mod

    def tearDown(self):
        os.chdir(self._cwd)
        self._tmp.cleanup()

    # ------------------------------------------------------------------
    # 角色权限矩阵
    # ------------------------------------------------------------------
    def test_role_permissions_guest_is_restricted(self):
        GUEST = self.auth.UserRole.GUEST
        self.assertTrue(self.auth.check_permission(GUEST, "chat"))
        self.assertTrue(self.auth.check_permission(GUEST, "note_read"))
        self.assertFalse(self.auth.check_permission(GUEST, "command"))
        self.assertFalse(self.auth.check_permission(GUEST, "device_control"))
        self.assertFalse(self.auth.check_permission(GUEST, "admin_users"))

    def test_role_permissions_family_no_admin(self):
        FAMILY = self.auth.UserRole.FAMILY
        self.assertTrue(self.auth.check_permission(FAMILY, "command"))
        self.assertTrue(self.auth.check_permission(FAMILY, "device_control"))
        self.assertFalse(self.auth.check_permission(FAMILY, "admin_users"))
        self.assertFalse(self.auth.check_permission(FAMILY, "admin_config"))
        self.assertFalse(self.auth.check_permission(FAMILY, "admin_skills"))

    def test_role_permissions_owner_full(self):
        OWNER = self.auth.UserRole.OWNER
        for perm in (
            "chat", "command", "device_control", "ha_control",
            "admin_users", "admin_config", "admin_skills",
            "wake_remote", "email_send",
        ):
            self.assertTrue(
                self.auth.check_permission(OWNER, perm),
                f"OWNER 应具备 {perm} 权限",
            )

    # ------------------------------------------------------------------
    # API Key 生命周期
    # ------------------------------------------------------------------
    def test_create_and_revoke_key(self):
        raw, key_id = self.auth.create_api_key("guest1", self.auth.UserRole.GUEST)
        self.assertTrue(raw)
        self.assertEqual(len(key_id), 8)

        # 元数据可见
        listed = self.auth.list_api_keys()
        self.assertTrue(any(k["id"] == key_id for k in listed))

        # 撤销后消失
        self.assertTrue(self.auth.revoke_api_key(key_id))
        listed2 = self.auth.list_api_keys()
        self.assertFalse(any(k["id"] == key_id for k in listed2))

        # 重复撤销返回 False
        self.assertFalse(self.auth.revoke_api_key(key_id))

    def test_revoked_key_cannot_authenticate(self):
        raw, key_id = self.auth.create_api_key("g1", self.auth.UserRole.GUEST)
        ok, role, err, obj = self.auth.verify_request(raw, "127.0.0.1")
        self.assertTrue(ok)
        self.auth.revoke_api_key(key_id)
        ok2, role2, err2, _ = self.auth.verify_request(raw, "127.0.0.1")
        self.assertFalse(ok2)
        self.assertEqual(err2, "无效的 API Key")

    def test_hash_is_stable(self):
        raw, _ = self.auth.create_api_key("owner", self.auth.UserRole.OWNER)
        h1 = self.auth._hash_key(raw)
        h2 = self.auth._hash_key(raw)
        self.assertEqual(h1, h2, "相同 Key 应产生稳定哈希")

    def test_key_is_hashed_not_stored_plaintext(self):
        raw, key_id = self.auth.create_api_key("g", self.auth.UserRole.GUEST)
        keys_file = self.auth._keys_file()
        self.assertTrue(os.path.exists(keys_file))
        with open(keys_file, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertNotIn(raw, content, "明文 Key 不应出现在持久化文件中")

    # ------------------------------------------------------------------
    # verify_request
    # ------------------------------------------------------------------
    def test_verify_request_missing_key(self):
        ok, role, err, _ = self.auth.verify_request(None, "127.0.0.1")
        self.assertFalse(ok)
        self.assertEqual(err, "缺少 API Key")
        self.assertEqual(role, self.auth.UserRole.GUEST)

    def test_verify_request_invalid_key(self):
        ok, role, err, _ = self.auth.verify_request("not-a-real-key", "127.0.0.1")
        self.assertFalse(ok)
        self.assertEqual(err, "无效的 API Key")

    def test_verify_request_trusted_ip_bypasses_key(self):
        self.auth.add_trusted_ip("10.0.0.7", self.auth.UserRole.OWNER)
        ok, role, err, _ = self.auth.verify_request(None, "10.0.0.7")
        self.assertTrue(ok)
        self.assertEqual(role, self.auth.UserRole.OWNER)
        self.assertIsNone(err)

        self.auth.remove_trusted_ip("10.0.0.7")
        ok2, _, err2, _ = self.auth.verify_request(None, "10.0.0.7")
        self.assertFalse(ok2)
        self.assertEqual(err2, "缺少 API Key")

    # ------------------------------------------------------------------
    # check_tool_access（关键授权逻辑）
    # ------------------------------------------------------------------
    def test_tool_access_guest_denied_unsafe_tools(self):
        GUEST = self.auth.UserRole.GUEST
        # guest 可用：read_notes, chat, get_system_info, notify
        self.assertTrue(self.auth.check_tool_access(GUEST, "read_notes"))
        self.assertTrue(self.auth.check_tool_access(GUEST, "notify"))
        self.assertFalse(self.auth.check_tool_access(GUEST, "control_pc"))
        self.assertFalse(self.auth.check_tool_access(GUEST, "send_email"))
        self.assertFalse(self.auth.check_tool_access(GUEST, "run_browser_task"))

    def test_tool_access_family_allowed_core_tools(self):
        FAMILY = self.auth.UserRole.FAMILY
        self.assertTrue(self.auth.check_tool_access(FAMILY, "control_pc"))
        self.assertTrue(self.auth.check_tool_access(FAMILY, "send_email"))
        self.assertTrue(self.auth.check_tool_access(FAMILY, "run_browser_task"))

    def test_tool_access_owner_full(self):
        OWNER = self.auth.UserRole.OWNER
        self.assertTrue(self.auth.check_tool_access(OWNER, "admin_delete_everything"))

    def test_tool_access_allowed_tools_whitelist_restricts_owner(self):
        OWNER = self.auth.UserRole.OWNER
        # 即使是 owner，若 key 明确限定 allowed_tools，也只能用白名单工具
        self.assertTrue(
            self.auth.check_tool_access(OWNER, "read_notes", allowed_tools=["read_notes"])
        )
        self.assertFalse(
            self.auth.check_tool_access(OWNER, "control_pc", allowed_tools=["read_notes"])
        )

    # ------------------------------------------------------------------
    # 额度检查
    # ------------------------------------------------------------------
    def test_quota_tracks_usage(self):
        raw, key_id = self.auth.create_api_key("q", self.auth.UserRole.FAMILY)
        key_hash = self.auth._hash_key(raw)

        ok, msg = self.auth.check_api_key_quota(key_hash, tokens_needed=5)
        self.assertTrue(ok)

        self.assertTrue(self.auth.record_api_key_usage(key_hash, tokens=99995))
        ok2, msg2 = self.auth.check_api_key_quota(key_hash, tokens_needed=10)
        self.assertFalse(ok2)
        self.assertIn("额度不足", msg2)

    def test_quota_invalid_key(self):
        ok, msg = self.auth.check_api_key_quota("no-such-key", tokens_needed=1)
        self.assertFalse(ok)
        self.assertEqual(msg, "无效的 API Key")

    def test_quota_limit_by_role(self):
        # owner 默认额度 1000000，family 100000
        raw_o, _ = self.auth.create_api_key("o", self.auth.UserRole.OWNER)
        raw_f, _ = self.auth.create_api_key("f", self.auth.UserRole.FAMILY)
        info_o = next(
            (k for k in self.auth.list_api_keys() if k["name"] == "o"), None
        )
        info_f = next(
            (k for k in self.auth.list_api_keys() if k["name"] == "f"), None
        )
        self.assertEqual(info_o["quota_limit"], 1000000)
        self.assertEqual(info_f["quota_limit"], 100000)

    # ------------------------------------------------------------------
    # 持久化：_save_keys / _load_keys
    # ------------------------------------------------------------------
    def test_save_then_load_preserves_data(self):
        raw, key_id = self.auth.create_api_key("persist", self.auth.UserRole.FAMILY)
        self.auth.add_trusted_ip("192.168.1.1", self.auth.UserRole.GUEST)
        # add_trusted_ip 不会立即落盘（需显式调用 save 的生产路径），
        # 这里通过手动写盘模拟生产场景的批量持久化。
        self.auth._save_keys()
        saved_path = self.auth._keys_file()
        self.assertTrue(os.path.exists(saved_path))

        # 清空内存态后重新加载
        import importlib
        import auth as reloaded
        os.chdir(self._tmp.name)
        importlib.reload(reloaded)

        listed = reloaded.list_api_keys()
        self.assertTrue(any(k["id"] == key_id for k in listed))

        ok, _, err, _ = reloaded.verify_request(raw, "127.0.0.1")
        self.assertTrue(ok)

        self.assertIn("192.168.1.1", reloaded._TRUSTED_IPS)

    def test_load_keys_generates_key_id_when_missing(self):
        import json
        data = {
            "keys": [
                {
                    "key_hash": "fake_hash",
                    "role": "guest",
                    "name": "legacy",
                    "created_at": 123.0,
                    "last_used": 0,
                    "allowed_tools": None,
                    "quota_used": 0,
                    "quota_limit": 100000,
                    # 故意缺失 key_id，触发兼容逻辑
                }
            ],
            "trusted_ips": {},
        }
        with open(self.auth._keys_file(), "w", encoding="utf-8") as f:
            json.dump(data, f)

        import importlib
        import auth as reloaded
        os.chdir(self._tmp.name)
        importlib.reload(reloaded)

        listed = reloaded.list_api_keys()
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["name"], "legacy")
        self.assertEqual(len(listed[0]["id"]), 8)


def main():
    runner = unittest.TextTestRunner(verbosity=2)
    unittest.main(testRunner=runner, exit=False, argv=["auth_tests"])


if __name__ == "__main__":
    main()
