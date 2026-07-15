"""
权限认证模块测试
覆盖 API Key 管理、权限校验、信任域、配额检查等核心功能
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from auth import (
    UserRole,
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
    _api_keys,
)


def _clear_keys():
    _api_keys.clear()


def main():
    print("=== 权限认证模块测试 ===\n")

    _clear_keys()

    # 1. API Key 创建与撤销
    print("1. API Key 创建与撤销...")
    raw_key, key_id = create_api_key("测试用户", UserRole.FAMILY)
    assert len(raw_key) == 43, f"API Key 长度不正确: {len(raw_key)}"
    assert len(key_id) == 8, f"Key ID 长度不正确: {len(key_id)}"
    keys = list_api_keys()
    assert len(keys) == 1, f"Key 数量不正确: {len(keys)}"
    assert keys[0]["name"] == "测试用户"
    assert keys[0]["role"] == "family"
    assert "key_hash" not in keys[0], "列表不应包含密钥哈希"
    print("  ✓ 创建成功")

    revoked = revoke_api_key(key_id)
    assert revoked is True
    keys = list_api_keys()
    assert len(keys) == 0, f"撤销后不应有 Key: {len(keys)}"
    print("  ✓ 撤销成功")

    revoked = revoke_api_key("不存在的id")
    assert revoked is False
    print("  ✓ 无效 ID 处理正确")

    # 2. 权限验证
    print("\n2. 权限验证...")
    _clear_keys()
    raw_key, key_id = create_api_key("管理员", UserRole.OWNER)

    ok, role, err, api_key_obj = verify_request(raw_key, "127.0.0.1")
    assert ok is True
    assert role == UserRole.OWNER
    assert err is None
    print("  ✓ 有效 Key 验证通过")

    ok, role, err, api_key_obj = verify_request("invalid_key", "127.0.0.1")
    assert ok is False
    assert err == "无效的 API Key"
    print("  ✓ 无效 Key 被拒绝")

    ok, role, err, api_key_obj = verify_request(None, "127.0.0.1")
    assert ok is False
    assert err == "缺少 API Key"
    print("  ✓ 缺少 Key 被拒绝")

    # 3. 角色权限检查
    print("\n3. 角色权限检查...")
    assert check_permission(UserRole.OWNER, "admin_users") is True
    assert check_permission(UserRole.FAMILY, "admin_users") is False
    assert check_permission(UserRole.GUEST, "admin_users") is False
    assert check_permission(UserRole.GUEST, "chat") is True
    assert check_permission(UserRole.FAMILY, "device_control") is True
    assert check_permission(UserRole.GUEST, "device_control") is False
    print("  ✓ 角色权限矩阵正确")

    # 4. 工具访问控制
    print("\n4. 工具访问控制...")
    assert check_tool_access(UserRole.OWNER, "control_pc") is True
    assert check_tool_access(UserRole.FAMILY, "control_pc") is True
    assert check_tool_access(UserRole.GUEST, "control_pc") is False
    assert check_tool_access(UserRole.FAMILY, "control_pc", ["read_only"]) is False
    assert check_tool_access(UserRole.FAMILY, "read_webpage") is True
    assert check_tool_access(UserRole.GUEST, "read_webpage") is False
    print("  ✓ 工具访问控制正确")

    # 5. 信任域
    print("\n5. 信任域...")
    add_trusted_ip("192.168.1.100", UserRole.OWNER)
    ok, role, err, api_key_obj = verify_request(None, "192.168.1.100")
    assert ok is True
    assert role == UserRole.OWNER
    print("  ✓ 信任 IP 免认证")

    remove_trusted_ip("192.168.1.100")
    ok, role, err, api_key_obj = verify_request(None, "192.168.1.100")
    assert ok is False
    print("  ✓ 移除信任 IP 后需要认证")

    # 6. 配额检查
    print("\n6. 配额检查...")
    _clear_keys()
    raw_key, key_id = create_api_key("配额测试", UserRole.FAMILY)

    key_hash = None
    for kh, ak in _api_keys.items():
        if ak.key_id == key_id:
            key_hash = kh
            break
    assert key_hash is not None

    ok, msg = check_api_key_quota(key_hash, 1000)
    assert ok is True
    assert msg == ""
    print("  ✓ 配额充足")

    ok, msg = check_api_key_quota("invalid_hash", 1000)
    assert ok is False
    assert msg == "无效的 API Key"
    print("  ✓ 无效 Key 配额检查失败")

    record_api_key_usage(key_hash, 99000)
    ok, msg = check_api_key_quota(key_hash, 2000)
    assert ok is False
    assert "额度不足" in msg
    print("  ✓ 配额不足被拒绝")

    record_api_key_usage("invalid_hash", 1000)
    print("  ✓ 无效 Key 用量记录静默失败")

    print("\n=== 权限认证模块测试完成 ===")


if __name__ == "__main__":
    main()