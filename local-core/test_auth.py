"""
认证模块测试
覆盖：API Key 管理、角色权限矩阵、工具访问控制、信任域管理、请求验证
"""

import os
import sys
import time
import tempfile
import json

# 确保在 local-core 目录下运行
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 需要在导入 auth 前设置环境，避免创建初始 key 文件
os.environ["AUTH_API_KEY_PEPPER"] = "test_pepper_for_unit_tests_12345"

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
    _TRUSTED_IPS,
)


def setup_function():
    """每个测试前清理全局状态"""
    _api_keys.clear()
    _TRUSTED_IPS.clear()


# ============================================================================
# _hash_key 测试
# ============================================================================

def test_hash_key_deterministic():
    """相同输入应产生相同哈希"""
    print("\n=== _hash_key 确定性 ===")

    h1 = _hash_key("test_key_123")
    h2 = _hash_key("test_key_123")
    assert h1 == h2, "相同输入应产生相同哈希"
    print(f"  哈希一致性: {h1[:16]}...")

    h3 = _hash_key("different_key")
    assert h1 != h3, "不同输入应产生不同哈希"
    print("  不同输入产生不同哈希")


def test_hash_key_format():
    """哈希应为 SHA256 十六进制"""
    print("\n=== _hash_key 格式 ===")

    h = _hash_key("test")
    assert len(h) == 64, "SHA256 哈希应为 64 字符"
    assert all(c in "0123456789abcdef" for c in h), "应为十六进制"
    print(f"  格式正确: 64 字符十六进制")


# ============================================================================
# create_api_key 测试
# ============================================================================

def test_create_api_key_owner():
    """创建 owner 角色 API Key"""
    print("\n=== create_api_key owner ===")
    setup_function()

    raw, key_id = create_api_key("管理员", UserRole.OWNER)
    assert raw is not None and len(raw) > 20, "raw key 应足够长"
    assert len(key_id) == 8, "key_id 应为 8 字符"
    print(f"  key_id: {key_id}, raw 长度: {len(raw)}")

    # 验证 key 已存储
    key_hash = _hash_key(raw)
    assert key_hash in _api_keys, "key 应已存储"
    stored = _api_keys[key_hash]
    assert stored.role == UserRole.OWNER
    assert stored.name == "管理员"
    assert stored.quota_limit == 1000000, "owner 默认额度应为 1000000"
    print(f"  角色验证: {stored.role}, 额度: {stored.quota_limit}")


def test_create_api_key_guest():
    """创建 guest 角色 API Key"""
    print("\n=== create_api_key guest ===")
    setup_function()

    raw, key_id = create_api_key("访客", UserRole.GUEST)
    key_hash = _hash_key(raw)
    stored = _api_keys[key_hash]
    assert stored.role == UserRole.GUEST
    assert stored.quota_limit == 100000, "guest 默认额度应为 100000"
    print(f"  guest 额度: {stored.quota_limit}")


def test_create_api_key_with_tool_restrictions():
    """创建带工具限制的 API Key"""
    print("\n=== create_api_key 工具限制 ===")
    setup_function()

    raw, key_id = create_api_key("受限用户", UserRole.FAMILY, allowed_tools=["chat", "read_notes"])
    key_hash = _hash_key(raw)
    stored = _api_keys[key_hash]
    assert stored.allowed_tools == ["chat", "read_notes"], "应存储工具白名单"
    print(f"  允许工具: {stored.allowed_tools}")


# ============================================================================
# revoke_api_key 测试
# ============================================================================

def test_revoke_api_key_success():
    """成功撤销 API Key"""
    print("\n=== revoke_api_key 成功 ===")
    setup_function()

    raw, key_id = create_api_key("测试用户", UserRole.FAMILY)
    assert len(_api_keys) == 1, "应有 1 个 key"

    result = revoke_api_key(key_id)
    assert result is True, "撤销应返回 True"
    assert len(_api_keys) == 0, "撤销后应无 key"
    print(f"  撤销 key_id={key_id} 成功")


def test_revoke_api_key_not_found():
    """撤销不存在的 key"""
    print("\n=== revoke_api_key 不存在 ===")
    setup_function()

    result = revoke_api_key("deadbeef")
    assert result is False, "不存在的 key 应返回 False"
    print("  不存在的 key_id 返回 False")


# ============================================================================
# list_api_keys 测试
# ============================================================================

def test_list_api_keys():
    """列出 API Key 元数据"""
    print("\n=== list_api_keys ===")
    setup_function()

    create_api_key("用户1", UserRole.OWNER)
    create_api_key("用户2", UserRole.GUEST)

    keys = list_api_keys()
    assert len(keys) == 2
    names = {k["name"] for k in keys}
    assert "用户1" in names and "用户2" in names
    # 确认不含密钥哈希
    for k in keys:
        assert "key_hash" not in k, "列表不应包含 key_hash"
    print(f"  列出 {len(keys)} 个 key，不含敏感信息")


# ============================================================================
# check_api_key_quota 测试
# ============================================================================

def test_quota_within_limit():
    """额度内请求"""
    print("\n=== check_api_key_quota 额度内 ===")
    setup_function()

    raw, key_id = create_api_key("测试", UserRole.GUEST)
    key_hash = _hash_key(raw)

    ok, err = check_api_key_quota(key_hash, 1000)
    assert ok is True, "额度充足应通过"
    assert err == ""
    print("  额度内请求通过")


def test_quota_exceeded():
    """额度不足"""
    print("\n=== check_api_key_quota 额度不足 ===")
    setup_function()

    raw, key_id = create_api_key("测试", UserRole.GUEST)
    key_hash = _hash_key(raw)
    # guest 默认额度 100000
    record_api_key_usage(key_hash, 99999)

    ok, err = check_api_key_quota(key_hash, 1000)
    assert ok is False, "超额应拒绝"
    assert "额度不足" in err
    print(f"  超额拒绝: {err}")


def test_quota_invalid_key():
    """无效 key 额度检查"""
    print("\n=== check_api_key_quota 无效 key ===")
    setup_function()

    ok, err = check_api_key_quota("nonexistent_hash")
    assert ok is False
    assert "无效" in err
    print(f"  无效 key: {err}")


# ============================================================================
# record_api_key_usage 测试
# ============================================================================

def test_record_usage():
    """记录用量"""
    print("\n=== record_api_key_usage ===")
    setup_function()

    raw, key_id = create_api_key("测试", UserRole.GUEST)
    key_hash = _hash_key(raw)

    assert record_api_key_usage(key_hash, 500) is True
    stored = _api_keys[key_hash]
    assert stored.quota_used == 500
    print(f"  用量: {stored.quota_used}")

    record_api_key_usage(key_hash, 300)
    assert stored.quota_used == 800, "用量应累加"
    print(f"  累加用量: {stored.quota_used}")


# ============================================================================
# verify_request 测试
# ============================================================================

def test_verify_with_valid_key():
    """有效 API Key 验证"""
    print("\n=== verify_request 有效 key ===")
    setup_function()

    raw, key_id = create_api_key("测试", UserRole.OWNER)
    ok, role, err, api_key_obj = verify_request(raw, "192.168.1.100")
    assert ok is True
    assert role == UserRole.OWNER
    assert err is None
    assert api_key_obj is not None
    assert api_key_obj.last_used > 0, "last_used 应被更新"
    print(f"  验证通过: role={role.value}, last_used={api_key_obj.last_used}")


def test_verify_missing_key():
    """缺少 API Key"""
    print("\n=== verify_request 缺少 key ===")
    setup_function()

    ok, role, err, api_key_obj = verify_request(None, "192.168.1.100")
    assert ok is False
    assert role == UserRole.GUEST
    assert "缺少" in err
    print(f"  缺少 key: {err}")


def test_verify_invalid_key():
    """无效 API Key"""
    print("\n=== verify_request 无效 key ===")
    setup_function()

    ok, role, err, api_key_obj = verify_request("invalid_key_12345", "192.168.1.100")
    assert ok is False
    assert role == UserRole.GUEST
    assert "无效" in err
    print(f"  无效 key: {err}")


def test_verify_trusted_ip():
    """信任 IP 直通"""
    print("\n=== verify_request 信任 IP ===")
    setup_function()

    add_trusted_ip("192.168.1.1", UserRole.FAMILY)
    ok, role, err, api_key_obj = verify_request(None, "192.168.1.1")
    assert ok is True
    assert role == UserRole.FAMILY
    assert err is None
    print(f"  信任 IP 直通: role={role.value}")


# ============================================================================
# check_permission 测试
# ============================================================================

def test_permission_owner():
    """owner 权限检查"""
    print("\n=== check_permission owner ===")

    owner_perms = ROLE_PERMISSIONS[UserRole.OWNER]
    assert "chat" in owner_perms
    assert "admin_users" in owner_perms
    assert "admin_config" in owner_perms
    assert check_permission(UserRole.OWNER, "chat")
    assert check_permission(UserRole.OWNER, "admin_config")
    print("  owner 拥有全部权限")


def test_permission_guest():
    """guest 权限检查"""
    print("\n=== check_permission guest ===")

    guest_perms = ROLE_PERMISSIONS[UserRole.GUEST]
    assert "chat" in guest_perms
    assert "note_read" in guest_perms
    assert "device_control" not in guest_perms
    assert not check_permission(UserRole.GUEST, "device_control")
    assert not check_permission(UserRole.GUEST, "admin_config")
    print("  guest 仅有基础权限")


def test_permission_family():
    """family 权限检查"""
    print("\n=== check_permission family ===")

    family_perms = ROLE_PERMISSIONS[UserRole.FAMILY]
    assert "chat" in family_perms
    assert "device_control" in family_perms
    assert "admin_users" not in family_perms
    assert "admin_config" not in family_perms
    print("  family 无 admin 权限")


# ============================================================================
# check_tool_access 测试
# ============================================================================

def test_tool_access_owner():
    """owner 工具访问"""
    print("\n=== check_tool_access owner ===")

    assert check_tool_access(UserRole.OWNER, "control_pc")
    assert check_tool_access(UserRole.OWNER, "get_system_info")
    assert check_tool_access(UserRole.OWNER, "any_tool")
    print("  owner 可访问所有工具")


def test_tool_access_guest():
    """guest 工具访问限制"""
    print("\n=== check_tool_access guest ===")

    assert check_tool_access(UserRole.GUEST, "get_system_info"), "guest 应有 system_info"
    assert not check_tool_access(UserRole.GUEST, "control_pc"), "guest 不应有 device_control"
    assert not check_tool_access(UserRole.GUEST, "send_email"), "guest 不应有 email_send"
    print("  guest 工具受限")


def test_tool_access_with_allowed_tools():
    """工具白名单限制"""
    print("\n=== check_tool_access 白名单 ===")

    # owner 带白名单限制
    assert check_tool_access(UserRole.OWNER, "chat", allowed_tools=["chat"])
    assert not check_tool_access(UserRole.OWNER, "control_pc", allowed_tools=["chat"])
    print("  白名单限制生效：owner 也受 allowed_tools 约束")


def test_tool_access_mapped_permissions():
    """权限-工具映射"""
    print("\n=== check_tool_access 权限映射 ===")

    # device_control -> control_pc 等
    assert check_tool_access(UserRole.FAMILY, "control_pc")
    assert check_tool_access(UserRole.FAMILY, "set_reminder")
    assert not check_tool_access(UserRole.GUEST, "set_reminder")
    # email_read
    assert check_tool_access(UserRole.FAMILY, "read_emails")
    assert not check_tool_access(UserRole.GUEST, "read_emails")
    print("  权限映射正确")


# ============================================================================
# 信任域管理
# ============================================================================

def test_trusted_ip_management():
    """信任 IP 添加/移除"""
    print("\n=== 信任 IP 管理 ===")
    setup_function()

    add_trusted_ip("10.0.0.1", UserRole.OWNER)
    assert "10.0.0.1" in _TRUSTED_IPS
    assert _TRUSTED_IPS["10.0.0.1"] == UserRole.OWNER.value
    print("  添加信任 IP")

    remove_trusted_ip("10.0.0.1")
    assert "10.0.0.1" not in _TRUSTED_IPS
    print("  移除信任 IP")

    # 移除不存在的 IP 不应报错
    remove_trusted_ip("192.168.0.1")
    print("  移除不存在的 IP 不报错")


# ============================================================================
# 主函数
# ============================================================================

def main():
    print("=" * 60)
    print("  认证模块测试")
    print("=" * 60)

    setup_function()

    # _hash_key
    test_hash_key_deterministic()
    test_hash_key_format()

    # create_api_key
    test_create_api_key_owner()
    test_create_api_key_guest()
    test_create_api_key_with_tool_restrictions()

    # revoke_api_key
    test_revoke_api_key_success()
    test_revoke_api_key_not_found()

    # list_api_keys
    test_list_api_keys()

    # check_api_key_quota
    test_quota_within_limit()
    test_quota_exceeded()
    test_quota_invalid_key()

    # record_api_key_usage
    test_record_usage()

    # verify_request
    test_verify_with_valid_key()
    test_verify_missing_key()
    test_verify_invalid_key()
    test_verify_trusted_ip()

    # check_permission
    test_permission_owner()
    test_permission_guest()
    test_permission_family()

    # check_tool_access
    test_tool_access_owner()
    test_tool_access_guest()
    test_tool_access_with_allowed_tools()
    test_tool_access_mapped_permissions()

    # 信任域
    test_trusted_ip_management()

    print("\n" + "=" * 60)
    print("  认证模块测试全部通过")
    print("=" * 60)


if __name__ == "__main__":
    main()
