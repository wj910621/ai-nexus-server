"""
auth 模块的综合 pytest 测试文件。

注意事项：
- auth 模块在导入时有模块级副作用（加载 keys、自动创建 owner key、检查 pepper 环境变量），
  因此必须在导入前设置 AUTH_API_KEY_PEPPER 环境变量，并 mock 掉文件 I/O。
- 使用 fixture 管理全局状态（_api_keys, _TRUSTED_IPS），确保测试隔离。
"""

import os
import sys
import time
from unittest.mock import patch, MagicMock

import pytest

# 将 /workspace/local-core 加入 sys.path
sys.path.insert(0, "/workspace/local-core")

# 在导入 auth 之前设置 AUTH_API_KEY_PEPPER，避免 RuntimeWarning
os.environ["AUTH_API_KEY_PEPPER"] = "test-pepper-for-pytest-do-not-use-in-prod"

# mock 掉文件 I/O 相关函数，避免模块导入时执行 _load_keys 和 _save_keys
# 我们在 patch 上下文中导入 auth 模块
with patch("builtins.open", MagicMock()):
    with patch("os.makedirs", MagicMock()):
        import auth


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def isolate_global_state():
    """每个测试前后清空/恢复 auth 模块的全局状态，确保测试隔离。"""
    # 保存原始状态
    original_api_keys = auth._api_keys.copy()
    original_trusted_ips = auth._TRUSTED_IPS.copy()

    # 清空全局状态
    auth._api_keys.clear()
    auth._TRUSTED_IPS.clear()

    yield

    # 恢复原始状态
    auth._api_keys.clear()
    auth._api_keys.update(original_api_keys)
    auth._TRUSTED_IPS.clear()
    auth._TRUSTED_IPS.update(original_trusted_ips)


@pytest.fixture
def mock_save_keys():
    """mock 掉 _save_keys 避免文件写入。"""
    with patch.object(auth, "_save_keys"):
        yield


@pytest.fixture
def owner_key(mock_save_keys):
    """创建一个 OWNER 角色 API Key，返回 (raw_key, ApiKey 对象)。"""
    raw, key_id = auth.create_api_key("test_owner", auth.UserRole.OWNER)
    key_hash = auth._hash_key(raw)
    return raw, auth._api_keys[key_hash]


@pytest.fixture
def family_key(mock_save_keys):
    """创建一个 FAMILY 角色 API Key，返回 (raw_key, ApiKey 对象)。"""
    raw, key_id = auth.create_api_key("test_family", auth.UserRole.FAMILY)
    key_hash = auth._hash_key(raw)
    return raw, auth._api_keys[key_hash]


@pytest.fixture
def guest_key(mock_save_keys):
    """创建一个 GUEST 角色 API Key，返回 (raw_key, ApiKey 对象)。"""
    raw, key_id = auth.create_api_key("test_guest", auth.UserRole.GUEST)
    key_hash = auth._hash_key(raw)
    return raw, auth._api_keys[key_hash]


# ---------------------------------------------------------------------------
# UserRole 枚举测试
# ---------------------------------------------------------------------------

class TestUserRole:
    def test_owner_value(self):
        assert auth.UserRole.OWNER.value == "owner"

    def test_family_value(self):
        assert auth.UserRole.FAMILY.value == "family"

    def test_guest_value(self):
        assert auth.UserRole.GUEST.value == "guest"

    def test_enum_members(self):
        assert set(auth.UserRole.__members__.keys()) == {"OWNER", "FAMILY", "GUEST"}


# ---------------------------------------------------------------------------
# ROLE_PERMISSIONS 测试
# ---------------------------------------------------------------------------

class TestRolePermissions:
    def test_owner_has_admin_permissions(self):
        owner_perms = auth.ROLE_PERMISSIONS[auth.UserRole.OWNER]
        assert "admin_users" in owner_perms
        assert "admin_config" in owner_perms
        assert "admin_skills" in owner_perms

    def test_owner_has_all_permissions(self):
        """OWNER 应该拥有所有已定义的权限。"""
        all_perms = set()
        for perms in auth.ROLE_PERMISSIONS.values():
            all_perms |= perms
        owner_perms = auth.ROLE_PERMISSIONS[auth.UserRole.OWNER]
        assert owner_perms == all_perms

    def test_guest_does_not_have_admin_permissions(self):
        guest_perms = auth.ROLE_PERMISSIONS[auth.UserRole.GUEST]
        assert "admin_users" not in guest_perms
        assert "admin_config" not in guest_perms
        assert "admin_skills" not in guest_perms

    def test_guest_does_not_have_command_permission(self):
        guest_perms = auth.ROLE_PERMISSIONS[auth.UserRole.GUEST]
        assert "command" not in guest_perms

    def test_guest_does_not_have_device_control_permission(self):
        guest_perms = auth.ROLE_PERMISSIONS[auth.UserRole.GUEST]
        assert "device_control" not in guest_perms

    def test_guest_has_basic_permissions(self):
        guest_perms = auth.ROLE_PERMISSIONS[auth.UserRole.GUEST]
        assert "chat" in guest_perms
        assert "note_read" in guest_perms
        assert "system_info" in guest_perms
        assert "notify" in guest_perms

    def test_family_has_chat(self):
        family_perms = auth.ROLE_PERMISSIONS[auth.UserRole.FAMILY]
        assert "chat" in family_perms

    def test_family_does_not_have_admin_users(self):
        family_perms = auth.ROLE_PERMISSIONS[auth.UserRole.FAMILY]
        assert "admin_users" not in family_perms

    def test_family_does_not_have_admin_config(self):
        family_perms = auth.ROLE_PERMISSIONS[auth.UserRole.FAMILY]
        assert "admin_config" not in family_perms

    def test_permissions_are_sets(self):
        for role, perms in auth.ROLE_PERMISSIONS.items():
            assert isinstance(perms, set), f"{role} 的权限应该是 set 类型"

    def test_family_is_subset_of_owner(self):
        owner_perms = auth.ROLE_PERMISSIONS[auth.UserRole.OWNER]
        family_perms = auth.ROLE_PERMISSIONS[auth.UserRole.FAMILY]
        assert family_perms.issubset(owner_perms)

    def test_guest_is_subset_of_family(self):
        family_perms = auth.ROLE_PERMISSIONS[auth.UserRole.FAMILY]
        guest_perms = auth.ROLE_PERMISSIONS[auth.UserRole.GUEST]
        assert guest_perms.issubset(family_perms)


# ---------------------------------------------------------------------------
# check_permission 测试
# ---------------------------------------------------------------------------

class TestCheckPermission:
    def test_owner_can_chat(self):
        assert auth.check_permission(auth.UserRole.OWNER, "chat") is True

    def test_owner_can_command(self):
        assert auth.check_permission(auth.UserRole.OWNER, "command") is True

    def test_owner_can_device_control(self):
        assert auth.check_permission(auth.UserRole.OWNER, "device_control") is True

    def test_owner_can_admin_users(self):
        assert auth.check_permission(auth.UserRole.OWNER, "admin_users") is True

    def test_owner_can_admin_config(self):
        assert auth.check_permission(auth.UserRole.OWNER, "admin_config") is True

    def test_owner_can_admin_skills(self):
        assert auth.check_permission(auth.UserRole.OWNER, "admin_skills") is True

    def test_family_can_chat(self):
        assert auth.check_permission(auth.UserRole.FAMILY, "chat") is True

    def test_family_can_command(self):
        assert auth.check_permission(auth.UserRole.FAMILY, "command") is True

    def test_family_cannot_admin_users(self):
        assert auth.check_permission(auth.UserRole.FAMILY, "admin_users") is False

    def test_family_cannot_admin_config(self):
        assert auth.check_permission(auth.UserRole.FAMILY, "admin_config") is False

    def test_family_cannot_admin_skills(self):
        assert auth.check_permission(auth.UserRole.FAMILY, "admin_skills") is False

    def test_guest_can_chat(self):
        assert auth.check_permission(auth.UserRole.GUEST, "chat") is True

    def test_guest_cannot_command(self):
        assert auth.check_permission(auth.UserRole.GUEST, "command") is False

    def test_guest_cannot_device_control(self):
        assert auth.check_permission(auth.UserRole.GUEST, "device_control") is False

    def test_guest_cannot_admin_users(self):
        assert auth.check_permission(auth.UserRole.GUEST, "admin_users") is False

    def test_unknown_permission_returns_false(self):
        assert auth.check_permission(auth.UserRole.OWNER, "nonexistent_perm") is False

    def test_unknown_role_returns_false(self):
        """传入非 UserRole 的值，应返回 False（因为 get 返回空 set）。"""
        assert auth.check_permission("not_a_role", "chat") is False


# ---------------------------------------------------------------------------
# check_tool_access 测试
# ---------------------------------------------------------------------------

class TestCheckToolAccess:
    # --- 无 allowed_tools 白名单 ---

    def test_owner_can_use_control_pc(self):
        assert auth.check_tool_access(auth.UserRole.OWNER, "control_pc") is True

    def test_owner_can_use_any_tool(self):
        """OWNER 默认可以使用任何工具（即使不在 tool_perm_map 中也返回 True）。"""
        assert auth.check_tool_access(auth.UserRole.OWNER, "unknown_tool_xyz") is True

    def test_family_can_use_control_pc(self):
        assert auth.check_tool_access(auth.UserRole.FAMILY, "control_pc") is True

    def test_family_can_use_any_tool(self):
        """FAMILY 默认也可以使用任何工具。"""
        assert auth.check_tool_access(auth.UserRole.FAMILY, "unknown_tool_xyz") is True

    def test_guest_can_use_notify(self):
        assert auth.check_tool_access(auth.UserRole.GUEST, "notify") is True

    def test_guest_cannot_use_control_pc(self):
        """GUEST 没有 device_control 权限，无法使用 control_pc。"""
        assert auth.check_tool_access(auth.UserRole.GUEST, "control_pc") is False

    def test_guest_cannot_use_device_command(self):
        assert auth.check_tool_access(auth.UserRole.GUEST, "device_command") is False

    def test_guest_cannot_use_unknown_tool(self):
        """GUEST 无法使用不在映射表中的工具，且不享受默认放行。"""
        assert auth.check_tool_access(auth.UserRole.GUEST, "unknown_tool_xyz") is False

    def test_guest_can_use_read_notes(self):
        assert auth.check_tool_access(auth.UserRole.GUEST, "read_notes") is True

    def test_guest_can_use_get_system_info(self):
        assert auth.check_tool_access(auth.UserRole.GUEST, "get_system_info") is True

    def test_guest_can_use_get_time(self):
        assert auth.check_tool_access(auth.UserRole.GUEST, "get_time") is True

    # --- 有 allowed_tools 白名单 ---

    def test_owner_restricted_by_allowed_tools(self):
        """即使 OWNER，如果 allowed_tools 不包含该工具，也应被拒绝。"""
        assert auth.check_tool_access(
            auth.UserRole.OWNER, "control_pc", allowed_tools=["chat_only"]
        ) is False

    def test_owner_allowed_tools_permits_tool(self):
        """allowed_tools 包含目标工具时，OWNER 应被允许。"""
        assert auth.check_tool_access(
            auth.UserRole.OWNER, "control_pc", allowed_tools=["control_pc"]
        ) is True

    def test_family_restricted_by_allowed_tools(self):
        assert auth.check_tool_access(
            auth.UserRole.FAMILY, "control_pc", allowed_tools=["chat_only"]
        ) is False

    def test_guest_restricted_by_allowed_tools(self):
        """GUEST 本来就不能用 control_pc，allowed_tools 也无法放行。"""
        assert auth.check_tool_access(
            auth.UserRole.GUEST, "control_pc", allowed_tools=["control_pc"]
        ) is False

    def test_guest_allowed_tools_permits_notify(self):
        """GUEST 有 notify 权限，且 allowed_tools 包含 notify，应被允许。"""
        assert auth.check_tool_access(
            auth.UserRole.GUEST, "notify", allowed_tools=["notify"]
        ) is True

    def test_allowed_tools_none_means_no_restriction(self):
        """allowed_tools=None 表示不受白名单限制。"""
        assert auth.check_tool_access(
            auth.UserRole.OWNER, "control_pc", allowed_tools=None
        ) is True

    def test_allowed_tools_empty_list_blocks_all(self):
        """allowed_tools 为空列表时，任何工具都应被拒绝。"""
        assert auth.check_tool_access(
            auth.UserRole.OWNER, "control_pc", allowed_tools=[]
        ) is False


# ---------------------------------------------------------------------------
# verify_request 测试
# ---------------------------------------------------------------------------

class TestVerifyRequest:
    def test_trusted_ip_returns_ip_role(self, mock_save_keys):
        """信任 IP 应直接返回该 IP 对应的角色。"""
        auth.add_trusted_ip("192.168.1.100", auth.UserRole.OWNER)
        ok, role, err, api_key_obj = auth.verify_request(None, "192.168.1.100")
        assert ok is True
        assert role == auth.UserRole.OWNER
        assert err is None
        assert api_key_obj is None

    def test_trusted_ip_family_role(self, mock_save_keys):
        """信任 IP 映射到 FAMILY 角色。"""
        auth.add_trusted_ip("192.168.1.101", auth.UserRole.FAMILY)
        ok, role, err, api_key_obj = auth.verify_request(None, "192.168.1.101")
        assert ok is True
        assert role == auth.UserRole.FAMILY
        assert err is None
        assert api_key_obj is None

    def test_no_api_key_returns_guest_with_error(self):
        """没有 API Key 且不是信任 IP 时，应返回 GUEST 和错误信息。"""
        ok, role, err, api_key_obj = auth.verify_request(None, "10.0.0.1")
        assert ok is False
        assert role == auth.UserRole.GUEST
        assert err == "缺少 API Key"
        assert api_key_obj is None

    def test_invalid_api_key_returns_guest_with_error(self):
        """无效的 API Key 应返回 GUEST 和错误信息。"""
        ok, role, err, api_key_obj = auth.verify_request("invalid_key_value", "10.0.0.1")
        assert ok is False
        assert role == auth.UserRole.GUEST
        assert err == "无效的 API Key"
        assert api_key_obj is None

    def test_valid_owner_api_key(self, owner_key):
        """有效的 OWNER API Key 应认证成功并返回 OWNER 角色。"""
        raw, _ = owner_key
        ok, role, err, api_key_obj = auth.verify_request(raw, "10.0.0.1")
        assert ok is True
        assert role == auth.UserRole.OWNER
        assert err is None
        assert api_key_obj is not None
        assert api_key_obj.role == auth.UserRole.OWNER

    def test_valid_family_api_key(self, family_key):
        """有效的 FAMILY API Key 应认证成功并返回 FAMILY 角色。"""
        raw, _ = family_key
        ok, role, err, api_key_obj = auth.verify_request(raw, "10.0.0.1")
        assert ok is True
        assert role == auth.UserRole.FAMILY
        assert err is None
        assert api_key_obj is not None

    def test_valid_guest_api_key(self, guest_key):
        """有效的 GUEST API Key 应认证成功并返回 GUEST 角色。"""
        raw, _ = guest_key
        ok, role, err, api_key_obj = auth.verify_request(raw, "10.0.0.1")
        assert ok is True
        assert role == auth.UserRole.GUEST
        assert err is None
        assert api_key_obj is not None

    def test_trusted_ip_takes_priority_over_api_key(self, owner_key, mock_save_keys):
        """信任 IP 优先级高于 API Key 验证。"""
        auth.add_trusted_ip("192.168.1.100", auth.UserRole.FAMILY)
        # 即使提供了 OWNER 的 key，信任 IP 映射的是 FAMILY
        raw, _ = owner_key
        ok, role, err, api_key_obj = auth.verify_request(raw, "192.168.1.100")
        assert ok is True
        assert role == auth.UserRole.FAMILY
        assert api_key_obj is None  # 信任 IP 不返回 api_key_obj

    def test_valid_api_key_updates_last_used(self, owner_key):
        """认证成功时应更新 last_used 时间。"""
        raw, api_key_obj = owner_key
        old_last_used = api_key_obj.last_used
        # 确保时间有差异
        time.sleep(0.01)
        auth.verify_request(raw, "10.0.0.1")
        assert api_key_obj.last_used >= old_last_used


# ---------------------------------------------------------------------------
# ApiKey 数据类测试
# ---------------------------------------------------------------------------

class TestApiKey:
    def test_create_api_key_returns_tuple(self, mock_save_keys):
        raw, key_id = auth.create_api_key("test", auth.UserRole.OWNER)
        assert isinstance(raw, str)
        assert isinstance(key_id, str)
        assert len(key_id) == 8  # 8 位 key_id

    def test_create_api_key_stores_in_globals(self, mock_save_keys):
        raw, key_id = auth.create_api_key("test", auth.UserRole.FAMILY)
        key_hash = auth._hash_key(raw)
        assert key_hash in auth._api_keys
        assert auth._api_keys[key_hash].name == "test"
        assert auth._api_keys[key_hash].role == auth.UserRole.FAMILY

    def test_owner_quota_limit(self, mock_save_keys):
        raw, _ = auth.create_api_key("owner_test", auth.UserRole.OWNER)
        key_hash = auth._hash_key(raw)
        assert auth._api_keys[key_hash].quota_limit == 1000000

    def test_non_owner_quota_limit(self, mock_save_keys):
        raw, _ = auth.create_api_key("guest_test", auth.UserRole.GUEST)
        key_hash = auth._hash_key(raw)
        assert auth._api_keys[key_hash].quota_limit == 100000

    def test_create_api_key_with_allowed_tools(self, mock_save_keys):
        raw, _ = auth.create_api_key(
            "restricted", auth.UserRole.OWNER, allowed_tools=["chat", "notify"]
        )
        key_hash = auth._hash_key(raw)
        assert auth._api_keys[key_hash].allowed_tools == ["chat", "notify"]

    def test_create_api_key_without_allowed_tools(self, mock_save_keys):
        raw, _ = auth.create_api_key("unrestricted", auth.UserRole.OWNER)
        key_hash = auth._hash_key(raw)
        assert auth._api_keys[key_hash].allowed_tools is None


# ---------------------------------------------------------------------------
# API Key 管理测试
# ---------------------------------------------------------------------------

class TestApiKeyManagement:
    def test_revoke_api_key(self, mock_save_keys):
        raw, key_id = auth.create_api_key("to_revoke", auth.UserRole.GUEST)
        assert auth.revoke_api_key(key_id) is True
        key_hash = auth._hash_key(raw)
        assert key_hash not in auth._api_keys

    def test_revoke_nonexistent_key(self, mock_save_keys):
        assert auth.revoke_api_key("deadbeef") is False

    def test_list_api_keys(self, mock_save_keys):
        auth.create_api_key("key1", auth.UserRole.OWNER)
        auth.create_api_key("key2", auth.UserRole.GUEST)
        keys = auth.list_api_keys()
        assert len(keys) == 2
        names = {k["name"] for k in keys}
        assert names == {"key1", "key2"}

    def test_check_api_key_quota_sufficient(self, owner_key, mock_save_keys):
        raw, _ = owner_key
        key_hash = auth._hash_key(raw)
        ok, err = auth.check_api_key_quota(key_hash, 1000)
        assert ok is True
        assert err == ""

    def test_check_api_key_quota_insufficient(self, owner_key, mock_save_keys):
        raw, api_key_obj = owner_key
        api_key_obj.quota_used = 999999
        key_hash = auth._hash_key(raw)
        ok, err = auth.check_api_key_quota(key_hash, 1000)
        assert ok is False
        assert "额度不足" in err

    def test_check_api_key_quota_invalid_hash(self, mock_save_keys):
        ok, err = auth.check_api_key_quota("nonexistent_hash", 1000)
        assert ok is False
        assert "无效" in err

    def test_record_api_key_usage(self, owner_key, mock_save_keys):
        raw, api_key_obj = owner_key
        key_hash = auth._hash_key(raw)
        original_used = api_key_obj.quota_used
        assert auth.record_api_key_usage(key_hash, 500) is True
        assert api_key_obj.quota_used == original_used + 500

    def test_record_api_key_usage_invalid_hash(self, mock_save_keys):
        assert auth.record_api_key_usage("nonexistent_hash", 500) is False


# ---------------------------------------------------------------------------
# 信任域管理测试
# ---------------------------------------------------------------------------

class TestTrustedIpManagement:
    def test_add_trusted_ip(self, mock_save_keys):
        auth.add_trusted_ip("192.168.0.1", auth.UserRole.OWNER)
        assert "192.168.0.1" in auth._TRUSTED_IPS
        assert auth._TRUSTED_IPS["192.168.0.1"] == "owner"

    def test_remove_trusted_ip(self, mock_save_keys):
        auth.add_trusted_ip("192.168.0.2", auth.UserRole.FAMILY)
        auth.remove_trusted_ip("192.168.0.2")
        assert "192.168.0.2" not in auth._TRUSTED_IPS

    def test_remove_nonexistent_trusted_ip(self, mock_save_keys):
        """删除不存在的 IP 不应抛异常。"""
        auth.remove_trusted_ip("10.0.0.1")  # 不应抛异常


# ---------------------------------------------------------------------------
# _hash_key 测试
# ---------------------------------------------------------------------------

class TestHashKey:
    def test_hash_key_deterministic(self):
        key = "test_key_123"
        h1 = auth._hash_key(key)
        h2 = auth._hash_key(key)
        assert h1 == h2

    def test_hash_key_different_inputs(self):
        h1 = auth._hash_key("key_a")
        h2 = auth._hash_key("key_b")
        assert h1 != h2

    def test_hash_key_is_sha256_hex(self):
        h = auth._hash_key("some_key")
        assert len(h) == 64  # SHA256 hex 输出长度
        assert all(c in "0123456789abcdef" for c in h)
