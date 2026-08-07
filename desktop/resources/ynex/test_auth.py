"""
权限认证模块测试
覆盖：API Key 创建/撤销/验证、权限矩阵、角色工具访问控制、额度检查
"""

import os
import sys
import time
import pytest

sys.path.insert(0, os.path.dirname(__file__))

# 防止 auth 模块加载时写文件到真实 data 目录
os.environ.setdefault("AUTH_API_KEY_PEPPER", "test_pepper_for_unit_tests_12345")

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
    add_trusted_ip,
    remove_trusted_ip,
    _hash_key,
    _api_keys,
)


@pytest.fixture(autouse=True)
def clean_api_keys():
    """每个测试前清空 API Key 存储，避免测试间污染"""
    _api_keys.clear()
    # 清理信任 IP
    auth._TRUSTED_IPS.clear()
    yield
    _api_keys.clear()
    auth._TRUSTED_IPS.clear()


# ===========================================================================
# 哈希函数
# ===========================================================================
class TestHashKey:
    def test_deterministic(self):
        """相同输入应产生相同哈希"""
        h1 = _hash_key("test_key")
        h2 = _hash_key("test_key")
        assert h1 == h2

    def test_different_keys_different_hashes(self):
        """不同输入应产生不同哈希"""
        h1 = _hash_key("key_a")
        h2 = _hash_key("key_b")
        assert h1 != h2

    def test_hash_is_sha256_hex(self):
        """哈希应为 64 字符的十六进制字符串"""
        h = _hash_key("test")
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)


# ===========================================================================
# API Key 管理
# ===========================================================================
class TestCreateApiKey:
    def test_create_returns_raw_and_id(self):
        raw, key_id = create_api_key("test", UserRole.OWNER)
        assert isinstance(raw, str)
        assert len(raw) > 0
        assert isinstance(key_id, str)
        assert len(key_id) == 8  # 8 位 key_id

    def test_create_stores_key(self):
        raw, key_id = create_api_key("test", UserRole.FAMILY)
        key_hash = _hash_key(raw)
        assert key_hash in _api_keys

    def test_owner_quota(self):
        raw, _ = create_api_key("owner", UserRole.OWNER)
        key_hash = _hash_key(raw)
        assert _api_keys[key_hash].quota_limit == 1000000

    def test_non_owner_quota(self):
        raw, _ = create_api_key("family", UserRole.FAMILY)
        key_hash = _hash_key(raw)
        assert _api_keys[key_hash].quota_limit == 100000

    def test_guest_quota(self):
        raw, _ = create_api_key("guest", UserRole.GUEST)
        key_hash = _hash_key(raw)
        assert _api_keys[key_hash].quota_limit == 100000

    def test_custom_allowed_tools(self):
        raw, _ = create_api_key("limited", UserRole.FAMILY, allowed_tools=["chat"])
        key_hash = _hash_key(raw)
        assert _api_keys[key_hash].allowed_tools == ["chat"]

    def test_default_allowed_tools_is_none(self):
        raw, _ = create_api_key("full", UserRole.OWNER)
        key_hash = _hash_key(raw)
        assert _api_keys[key_hash].allowed_tools is None

    def test_key_id_uniqueness(self):
        """不同 key 应有不同 key_id"""
        _, id1 = create_api_key("a", UserRole.OWNER)
        _, id2 = create_api_key("b", UserRole.OWNER)
        # 极小概率重复，但基本不可能
        assert id1 != id2


class TestRevokeApiKey:
    def test_revoke_existing_key(self):
        _, key_id = create_api_key("test", UserRole.OWNER)
        assert revoke_api_key(key_id) is True
        # 确认已删除
        assert len(_api_keys) == 0

    def test_revoke_nonexistent_key(self):
        assert revoke_api_key("deadbeef") is False

    def test_revoke_preserves_other_keys(self):
        _, id1 = create_api_key("key1", UserRole.OWNER)
        _, id2 = create_api_key("key2", UserRole.FAMILY)
        revoke_api_key(id1)
        assert len(_api_keys) == 1


class TestListApiKeys:
    def test_empty_list(self):
        assert list_api_keys() == []

    def test_list_contains_metadata(self):
        create_api_key("test", UserRole.OWNER)
        keys = list_api_keys()
        assert len(keys) == 1
        k = keys[0]
        assert "id" in k
        assert "name" in k
        assert "role" in k
        assert "quota_used" in k
        assert "quota_limit" in k
        # 不应包含 key_hash 或 raw_key
        assert "key_hash" not in k

    def test_list_excludes_raw_key(self):
        """列表中绝不应包含明文密钥"""
        create_api_key("test", UserRole.OWNER)
        for k in list_api_keys():
            for v in k.values():
                assert not isinstance(v, str) or len(v) < 40 or not all(c in "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ-_" for c in v)


# ===========================================================================
# 额度检查
# ===========================================================================
class TestQuotaCheck:
    def test_sufficient_quota(self):
        raw, _ = create_api_key("test", UserRole.OWNER)
        key_hash = _hash_key(raw)
        ok, msg = check_api_key_quota(key_hash, 1000)
        assert ok is True
        assert msg == ""

    def test_insufficient_quota(self):
        raw, _ = create_api_key("test", UserRole.FAMILY)
        key_hash = _hash_key(raw)
        ok, msg = check_api_key_quota(key_hash, 200000)
        assert ok is False
        assert "额度不足" in msg

    def test_invalid_key_hash(self):
        ok, msg = check_api_key_quota("nonexistent_hash", 1000)
        assert ok is False
        assert "无效" in msg


class TestRecordUsage:
    def test_record_increments_quota(self):
        raw, _ = create_api_key("test", UserRole.FAMILY)
        key_hash = _hash_key(raw)
        record_api_key_usage(key_hash, 500)
        assert _api_keys[key_hash].quota_used == 500

    def test_record_accumulates(self):
        raw, _ = create_api_key("test", UserRole.FAMILY)
        key_hash = _hash_key(raw)
        record_api_key_usage(key_hash, 300)
        record_api_key_usage(key_hash, 200)
        assert _api_keys[key_hash].quota_used == 500

    def test_invalid_key_returns_false(self):
        assert record_api_key_usage("nonexistent", 100) is False


# ===========================================================================
# 请求验证
# ===========================================================================
class TestVerifyRequest:
    def test_valid_api_key(self):
        raw, _ = create_api_key("test", UserRole.OWNER)
        ok, role, err, key_obj = verify_request(raw, "1.2.3.4")
        assert ok is True
        assert role == UserRole.OWNER
        assert err is None
        assert key_obj is not None

    def test_missing_api_key(self):
        ok, role, err, key_obj = verify_request(None, "1.2.3.4")
        assert ok is False
        assert "缺少" in err

    def test_invalid_api_key(self):
        ok, role, err, key_obj = verify_request("invalid_key_12345", "1.2.3.4")
        assert ok is False
        assert "无效" in err

    def test_trusted_ip_bypasses_key(self):
        add_trusted_ip("192.168.1.100", UserRole.FAMILY)
        ok, role, err, key_obj = verify_request(None, "192.168.1.100")
        assert ok is True
        assert role == UserRole.FAMILY
        assert key_obj is None

    def test_trusted_ip_overrides_key(self):
        """信任 IP 应优先于 API Key 检查"""
        add_trusted_ip("10.0.0.1", UserRole.GUEST)
        ok, role, err, key_obj = verify_request("some_key", "10.0.0.1")
        assert ok is True
        assert role == UserRole.GUEST

    def test_untrusted_ip_requires_key(self):
        ok, role, err, key_obj = verify_request(None, "8.8.8.8")
        assert ok is False


# ===========================================================================
# 权限检查
# ===========================================================================
class TestCheckPermission:
    def test_owner_has_all_permissions(self):
        for perm in ROLE_PERMISSIONS[UserRole.OWNER]:
            assert check_permission(UserRole.OWNER, perm) is True

    def test_guest_limited_permissions(self):
        assert check_permission(UserRole.GUEST, "chat") is True
        assert check_permission(UserRole.GUEST, "command") is False
        assert check_permission(UserRole.GUEST, "device_control") is False
        assert check_permission(UserRole.GUEST, "admin_users") is False

    def test_family_no_admin(self):
        assert check_permission(UserRole.FAMILY, "chat") is True
        assert check_permission(UserRole.FAMILY, "admin_users") is False
        assert check_permission(UserRole.FAMILY, "admin_config") is False

    def test_nonexistent_permission(self):
        assert check_permission(UserRole.OWNER, "nonexistent_perm") is False


class TestCheckToolAccess:
    def test_owner_full_access_by_default(self):
        assert check_tool_access(UserRole.OWNER, "any_tool") is True

    def test_family_full_access_by_default(self):
        assert check_tool_access(UserRole.FAMILY, "any_tool") is True

    def test_guest_limited_tools(self):
        assert check_tool_access(UserRole.GUEST, "control_pc") is False
        assert check_tool_access(UserRole.GUEST, "set_reminder") is False
        assert check_tool_access(UserRole.GUEST, "read_notes") is True

    def test_allowed_tools_whitelist_restricts_owner(self):
        """即使 owner，若 allowed_tools 有值，也应受白名单限制"""
        assert check_tool_access(UserRole.OWNER, "chat", allowed_tools=["command"]) is False

    def test_allowed_tools_whitelist_allows_listed(self):
        assert check_tool_access(UserRole.OWNER, "chat", allowed_tools=["chat"]) is True

    def test_allowed_tools_none_means_all(self):
        """allowed_tools=None 表示不限制"""
        assert check_tool_access(UserRole.OWNER, "anything", allowed_tools=None) is True

    def test_mapped_tools_for_family(self):
        """family 通过权限映射访问工具"""
        assert check_tool_access(UserRole.FAMILY, "control_pc") is True
        assert check_tool_access(UserRole.FAMILY, "read_webpage") is True

    def test_guest_cannot_use_device_tools(self):
        assert check_tool_access(UserRole.GUEST, "control_pc") is False
        assert check_tool_access(UserRole.GUEST, "device_command") is False


# ===========================================================================
# 信任域管理
# ===========================================================================
class TestTrustedIp:
    def test_add_and_verify(self):
        add_trusted_ip("10.0.0.1", UserRole.FAMILY)
        assert "10.0.0.1" in auth._TRUSTED_IPS

    def test_remove_trusted_ip(self):
        add_trusted_ip("10.0.0.2", UserRole.GUEST)
        remove_trusted_ip("10.0.0.2")
        assert "10.0.0.2" not in auth._TRUSTED_IPS

    def test_remove_nonexistent_ip_no_error(self):
        remove_trusted_ip("1.2.3.4")  # 不应抛异常


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
