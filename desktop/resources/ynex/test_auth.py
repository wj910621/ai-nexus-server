"""
认证模块测试
- API Key 创建与撤销
- 角色权限校验
- 额度管理
- 请求验证
- 信任 IP 管理
"""

import os
import sys
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

_test_data_dir = tempfile.mkdtemp(prefix="ynex_auth_test_")
os.environ["YNEX_DATA_DIR"] = _test_data_dir
os.makedirs(os.path.join(_test_data_dir, "data"), exist_ok=True)
os.chdir(_test_data_dir)

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
    _generate_key,
    _generate_key_id,
)


def test_user_role_enum():
    """测试用户角色枚举"""
    print("\n=== 用户角色枚举 ===")

    assert UserRole.OWNER.value == "owner"
    assert UserRole.FAMILY.value == "family"
    assert UserRole.GUEST.value == "guest"

    assert UserRole("owner") == UserRole.OWNER
    assert UserRole("family") == UserRole.FAMILY
    assert UserRole("guest") == UserRole.GUEST

    print("  ✓ 角色枚举正确")


def test_role_permissions_matrix():
    """测试权限矩阵"""
    print("\n=== 权限矩阵 ===")

    owner_perms = ROLE_PERMISSIONS[UserRole.OWNER]
    family_perms = ROLE_PERMISSIONS[UserRole.FAMILY]
    guest_perms = ROLE_PERMISSIONS[UserRole.GUEST]

    assert "admin_users" in owner_perms, "owner 应有 admin_users 权限"
    assert "admin_config" in owner_perms, "owner 应有 admin_config 权限"
    assert "admin_skills" in owner_perms, "owner 应有 admin_skills 权限"

    assert "admin_users" not in family_perms, "family 不应有 admin_users 权限"
    assert "admin_config" not in family_perms, "family 不应有 admin_config 权限"

    assert "command" not in guest_perms, "guest 不应有 command 权限"
    assert "device_control" not in guest_perms, "guest 不应有 device_control 权限"

    assert "chat" in owner_perms and "chat" in family_perms and "chat" in guest_perms
    assert "notify" in owner_perms and "notify" in family_perms and "notify" in guest_perms

    assert len(owner_perms) > len(family_perms), "owner 权限应多于 family"
    assert len(family_perms) > len(guest_perms), "family 权限应多于 guest"

    print("  ✓ 权限矩阵正确")


def test_hash_key():
    """测试 API Key 哈希"""
    print("\n=== API Key 哈希 ===")

    key1 = "test-api-key-12345"
    hash1 = _hash_key(key1)
    hash2 = _hash_key(key1)

    assert hash1 == hash2, "相同 key 应产生相同 hash"
    assert len(hash1) == 64, "SHA256 哈希应为 64 位十六进制"
    assert key1 not in hash1, "哈希不应包含明文"

    key2 = "test-api-key-67890"
    hash3 = _hash_key(key2)
    assert hash1 != hash3, "不同 key 应产生不同 hash"

    print("  ✓ 哈希函数正确")


def test_generate_key():
    """测试密钥生成"""
    print("\n=== 密钥生成 ===")

    key1 = _generate_key()
    key2 = _generate_key()

    assert key1 != key2, "每次生成应不同"
    assert len(key1) > 30, "生成的 key 应有足够长度"
    assert isinstance(key1, str), "应返回字符串"

    key_id = _generate_key_id()
    assert len(key_id) == 8, "key_id 应为 8 位十六进制"
    assert all(c in "0123456789abcdef" for c in key_id), "key_id 应为十六进制"

    print("  ✓ 密钥生成正确")


def test_create_and_revoke_api_key():
    """测试 API Key 创建与撤销"""
    print("\n=== API Key 创建与撤销 ===")

    raw_key, key_id = create_api_key("测试 Key", UserRole.FAMILY)

    assert raw_key is not None and len(raw_key) > 0, "应返回明文 key"
    assert key_id is not None and len(key_id) == 8, "应返回 8 位 key_id"

    keys = list_api_keys()
    assert len(keys) >= 1, "应至少有一个 key"
    found = any(k["id"] == key_id for k in keys)
    assert found, "新创建的 key 应在列表中"

    key_info = next(k for k in keys if k["id"] == key_id)
    assert key_info["name"] == "测试 Key"
    assert key_info["role"] == "family"
    assert "quota_limit" in key_info

    result = revoke_api_key(key_id)
    assert result is True, "撤销应成功"

    keys_after = list_api_keys()
    found_after = any(k["id"] == key_id for k in keys_after)
    assert not found_after, "撤销后 key 不应在列表中"

    result2 = revoke_api_key(key_id)
    assert result2 is False, "撤销不存在的 key 应返回 False"

    print("  ✓ API Key 创建与撤销正确")


def test_api_key_roles_and_quotas():
    """测试不同角色的配额"""
    print("\n=== 角色配额 ===")

    owner_key, owner_id = create_api_key("Owner Key", UserRole.OWNER)
    family_key, family_id = create_api_key("Family Key", UserRole.FAMILY)
    guest_key, guest_id = create_api_key("Guest Key", UserRole.GUEST)

    keys = list_api_keys()
    owner_info = next(k for k in keys if k["id"] == owner_id)
    family_info = next(k for k in keys if k["id"] == family_id)
    guest_info = next(k for k in keys if k["id"] == guest_id)

    assert owner_info["quota_limit"] == 1000000, "owner 配额应为 1,000,000"
    assert family_info["quota_limit"] == 100000, "family 配额应为 100,000"
    assert guest_info["quota_limit"] == 100000, "guest 配额应为 100,000"

    assert owner_info["role"] == "owner"
    assert family_info["role"] == "family"
    assert guest_info["role"] == "guest"

    revoke_api_key(owner_id)
    revoke_api_key(family_id)
    revoke_api_key(guest_id)

    print("  ✓ 角色配额正确")


def test_quota_management():
    """测试额度管理"""
    print("\n=== 额度管理 ===")

    raw_key, key_id = create_api_key("Quota Test", UserRole.FAMILY, allowed_tools=["chat"])

    key_hash = _hash_key(raw_key)

    ok, msg = check_api_key_quota(key_hash, 1000)
    assert ok is True, f"初始额度应充足: {msg}"

    result = record_api_key_usage(key_hash, 50000)
    assert result is True, "记录用量应成功"

    ok, msg = check_api_key_quota(key_hash, 50000)
    assert ok is True, "50000+50000 = 100000 应等于限额"

    ok, msg = check_api_key_quota(key_hash, 50001)
    assert ok is False, "超出限额应被拒绝"
    assert "额度不足" in msg

    result = record_api_key_usage("invalid_hash", 100)
    assert result is False, "无效 key 记录用量应失败"

    ok, msg = check_api_key_quota("invalid_hash", 100)
    assert ok is False, "无效 key 应返回 False"
    assert "无效的 API Key" in msg

    revoke_api_key(key_id)

    print("  ✓ 额度管理正确")


def test_check_permission():
    """测试权限检查"""
    print("\n=== 权限检查 ===")

    assert check_permission(UserRole.OWNER, "admin_users") is True
    assert check_permission(UserRole.OWNER, "chat") is True
    assert check_permission(UserRole.OWNER, "nonexistent_perm") is False

    assert check_permission(UserRole.FAMILY, "chat") is True
    assert check_permission(UserRole.FAMILY, "admin_users") is False

    assert check_permission(UserRole.GUEST, "chat") is True
    assert check_permission(UserRole.GUEST, "command") is False
    assert check_permission(UserRole.GUEST, "device_control") is False

    assert check_permission("invalid_role", "chat") is False

    print("  ✓ 权限检查正确")


def test_check_tool_access():
    """测试工具访问控制"""
    print("\n=== 工具访问控制 ===")

    assert check_tool_access(UserRole.OWNER, "set_reminder") is True
    assert check_tool_access(UserRole.OWNER, "control_pc") is True

    assert check_tool_access(UserRole.FAMILY, "set_reminder") is True
    assert check_tool_access(UserRole.FAMILY, "read_notes") is True

    assert check_tool_access(UserRole.GUEST, "get_time") is True
    assert check_tool_access(UserRole.GUEST, "set_reminder") is False
    assert check_tool_access(UserRole.GUEST, "control_pc") is False

    assert check_tool_access(UserRole.OWNER, "some_custom_tool") is True
    assert check_tool_access(UserRole.FAMILY, "some_custom_tool") is True
    assert check_tool_access(UserRole.GUEST, "some_custom_tool") is False

    assert check_tool_access(UserRole.OWNER, "chat_tool", allowed_tools=["chat_tool"]) is True
    assert check_tool_access(UserRole.OWNER, "other_tool", allowed_tools=["chat_tool"]) is False
    assert check_tool_access(UserRole.FAMILY, "chat_tool", allowed_tools=["chat_tool"]) is True
    assert check_tool_access(UserRole.FAMILY, "other_tool", allowed_tools=["chat_tool"]) is False

    print("  ✓ 工具访问控制正确")


def test_verify_request_with_api_key():
    """测试使用 API Key 验证请求"""
    print("\n=== API Key 请求验证 ===")

    raw_key, key_id = create_api_key("Verify Test", UserRole.FAMILY)

    ok, role, err, key_obj = verify_request(raw_key, "192.168.1.100")
    assert ok is True, f"有效 API Key 应通过验证: {err}"
    assert role == UserRole.FAMILY
    assert err is None
    assert key_obj is not None
    assert key_obj.name == "Verify Test"
    assert key_obj.last_used > 0, "last_used 应被更新"

    ok, role, err, key_obj = verify_request("invalid-key", "192.168.1.100")
    assert ok is False, "无效 API Key 应被拒绝"
    assert "无效的 API Key" in err
    assert role == UserRole.GUEST

    ok, role, err, key_obj = verify_request("", "192.168.1.100")
    assert ok is False, "空 API Key 应被拒绝"
    assert "缺少 API Key" in err
    assert role == UserRole.GUEST

    ok, role, err, key_obj = verify_request(None, "192.168.1.100")
    assert ok is False, "None API Key 应被拒绝"
    assert role == UserRole.GUEST

    revoke_api_key(key_id)

    print("  ✓ API Key 请求验证正确")


def test_trusted_ip():
    """测试信任 IP 直通"""
    print("\n=== 信任 IP 直通 ===")

    test_ip = "10.0.0.5"

    add_trusted_ip(test_ip, UserRole.OWNER)

    ok, role, err, key_obj = verify_request(None, test_ip)
    assert ok is True, "信任 IP 应直通验证"
    assert role == UserRole.OWNER
    assert err is None
    assert key_obj is None

    remove_trusted_ip(test_ip)

    ok, role, err, key_obj = verify_request(None, test_ip)
    assert ok is False, "移除信任 IP 后应需要认证"

    remove_trusted_ip("nonexistent_ip")

    print("  ✓ 信任 IP 直通正确")


def test_allowed_tools_restriction():
    """测试 allowed_tools 白名单限制"""
    print("\n=== allowed_tools 白名单 ===")

    raw_key, key_id = create_api_key(
        "Restricted Key",
        UserRole.OWNER,
        allowed_tools=["set_reminder", "get_time"]
    )

    key_hash = _hash_key(raw_key)
    keys = list_api_keys()
    key_info = next(k for k in keys if k["id"] == key_id)
    assert key_info["allowed_tools"] == ["set_reminder", "get_time"]

    assert check_tool_access(UserRole.OWNER, "set_reminder", allowed_tools=["set_reminder", "get_time"]) is True
    assert check_tool_access(UserRole.OWNER, "get_time", allowed_tools=["set_reminder", "get_time"]) is True
    assert check_tool_access(UserRole.OWNER, "control_pc", allowed_tools=["set_reminder", "get_time"]) is False
    assert check_tool_access(UserRole.OWNER, "read_notes", allowed_tools=["set_reminder", "get_time"]) is False

    revoke_api_key(key_id)

    print("  ✓ allowed_tools 白名单正确")


def test_list_api_keys_returns_metadata_only():
    """测试 list_api_keys 只返回元数据，不含密钥"""
    print("\n=== 列表只返回元数据 ===")

    raw_key, key_id = create_api_key("Metadata Test", UserRole.GUEST)

    keys = list_api_keys()
    for k in keys:
        assert "key_hash" not in k, "列表不应包含 key_hash"
        assert "raw_key" not in k, "列表不应包含 raw_key"
        assert "id" in k, "列表应包含 key_id"
        assert "name" in k, "列表应包含 name"
        assert "role" in k, "列表应包含 role"

    revoke_api_key(key_id)

    print("  ✓ 元数据保护正确")


def main():
    print("=" * 60)
    print("  认证模块安全网测试")
    print("=" * 60)

    test_user_role_enum()
    test_role_permissions_matrix()
    test_hash_key()
    test_generate_key()
    test_create_and_revoke_api_key()
    test_api_key_roles_and_quotas()
    test_quota_management()
    test_check_permission()
    test_check_tool_access()
    test_verify_request_with_api_key()
    test_trusted_ip()
    test_allowed_tools_restriction()
    test_list_api_keys_returns_metadata_only()

    print("\n" + "=" * 60)
    print("  ✅ 所有认证模块测试通过")
    print("=" * 60)

    shutil.rmtree(_test_data_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
