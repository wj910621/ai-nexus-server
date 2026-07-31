"""
权限认证模块测试
覆盖：角色权限矩阵、API Key 生命周期、信任 IP、请求验证、工具访问控制
"""

import os
import sys
import time
import shutil
import tempfile

# 确保本地导入路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _reset_auth_module():
    """重置 auth 模块的全局状态，确保测试隔离"""
    import auth
    auth._api_keys.clear()
    auth._TRUSTED_IPS.clear()


def test_role_permissions_matrix():
    """角色权限矩阵：OWNER > FAMILY > GUEST"""
    import auth

    # GUEST 只能基础操作
    assert auth.check_permission(auth.UserRole.GUEST, "chat") is True
    assert auth.check_permission(auth.UserRole.GUEST, "device_control") is False
    assert auth.check_permission(auth.UserRole.GUEST, "admin_users") is False

    # FAMILY 有设备/浏览器权限但无管理权限
    assert auth.check_permission(auth.UserRole.FAMILY, "chat") is True
    assert auth.check_permission(auth.UserRole.FAMILY, "device_control") is True
    assert auth.check_permission(auth.UserRole.FAMILY, "admin_users") is False
    assert auth.check_permission(auth.UserRole.FAMILY, "admin_config") is False

    # OWNER 有全部权限
    assert auth.check_permission(auth.UserRole.OWNER, "chat") is True
    assert auth.check_permission(auth.UserRole.OWNER, "admin_users") is True
    assert auth.check_permission(auth.UserRole.OWNER, "admin_config") is True

    print("  ✓ 角色权限矩阵正确")


def test_api_key_create_and_verify():
    """API Key 创建与验证完整流程"""
    _reset_auth_module()
    import auth

    raw_key, key_id = auth.create_api_key("测试用户", auth.UserRole.OWNER)
    assert raw_key, "创建应返回明文 Key"
    assert key_id, "创建应返回 key_id"
    assert len(key_id) == 8, "key_id 应为 8 位"

    # 通过明文 Key 验证
    ok, role, err, api_key_obj = auth.verify_request(raw_key, "1.2.3.4")
    assert ok is True, f"应验证通过，但错误: {err}"
    assert role == auth.UserRole.OWNER
    assert api_key_obj is not None
    assert api_key_obj.name == "测试用户"

    print("  ✓ API Key 创建与验证正确")


def test_api_key_wrong_key():
    """无效 API Key 被拒绝"""
    _reset_auth_module()
    import auth

    auth.create_api_key("用户A", auth.UserRole.FAMILY)

    ok, role, err, obj = auth.verify_request("wrong_key_value", "1.2.3.4")
    assert ok is False, "错误 Key 不应通过"
    assert "无效" in err

    print("  ✓ 无效 Key 被正确拒绝")


def test_api_key_missing():
    """缺少 API Key 被拒绝"""
    _reset_auth_module()
    import auth

    ok, role, err, obj = auth.verify_request(None, "1.2.3.4")
    assert ok is False
    assert "缺少" in err

    ok2, _, err2, _ = auth.verify_request("", "1.2.3.4")
    assert ok2 is False

    print("  ✓ 缺少 Key 被正确拒绝")


def test_api_key_revoke():
    """API Key 撤销"""
    _reset_auth_module()
    import auth

    raw_key, key_id = auth.create_api_key("待撤销", auth.UserRole.GUEST)

    # 撤销前可用
    ok, _, _, _ = auth.verify_request(raw_key, "1.2.3.4")
    assert ok is True

    # 撤销
    result = auth.revoke_api_key(key_id)
    assert result is True

    # 撤销后不可用
    ok, _, err, _ = auth.verify_request(raw_key, "1.2.3.4")
    assert ok is False

    print("  ✓ API Key 撤销正确")


def test_api_key_revoke_nonexistent():
    """撤销不存在的 key_id 返回 False"""
    _reset_auth_module()
    import auth

    result = auth.revoke_api_key("deadbeef")
    assert result is False

    print("  ✓ 撤销不存在的 Key 返回 False")


def test_api_key_quota():
    """API Key 额度检查与记录"""
    _reset_auth_module()
    import auth

    raw_key, key_id = auth.create_api_key("额度测试", auth.UserRole.GUEST)
    key_hash = auth._hash_key(raw_key)

    # 新 Key 额度应充足
    ok, msg = auth.check_api_key_quota(key_hash, 1000)
    assert ok is True

    # 记录用量
    auth.record_api_key_usage(key_hash, 99000)
    ok, msg = auth.check_api_key_quota(key_hash, 2000)
    assert ok is False, "GUEST 额度 100000，已用 99000，再扣 2000 应不足"
    assert "额度不足" in msg

    # 不存在的 Key
    ok, msg = auth.check_api_key_quota("nonexistent_hash", 100)
    assert ok is False

    print("  ✓ API Key 额度检查与记录正确")


def test_api_key_owner_higher_quota():
    """OWNER 角色拥有更高默认额度"""
    _reset_auth_module()
    import auth

    _, _ = auth.create_api_key("owner用户", auth.UserRole.OWNER)
    keys = auth.list_api_keys()
    owner_key = keys[0]
    assert owner_key["quota_limit"] == 1000000, "OWNER 默认额度应为 1000000"

    raw2, _ = auth.create_api_key("guest用户", auth.UserRole.GUEST)
    keys = auth.list_api_keys()
    guest_key = [k for k in keys if k["name"] == "guest用户"][0]
    assert guest_key["quota_limit"] == 100000, "GUEST 默认额度应为 100000"

    print("  ✓ OWNER/GUEST 额度区分正确")


def test_trusted_ip_bypass():
    """信任 IP 免认证直通"""
    _reset_auth_module()
    import auth

    auth.add_trusted_ip("192.168.1.100", auth.UserRole.FAMILY)

    ok, role, err, obj = auth.verify_request(None, "192.168.1.100")
    assert ok is True
    assert role == auth.UserRole.FAMILY

    # 非信任 IP 仍需 Key
    ok2, _, _, _ = auth.verify_request(None, "10.0.0.1")
    assert ok2 is False

    print("  ✓ 信任 IP 免认证正确")


def test_trusted_ip_remove():
    """移除信任 IP"""
    _reset_auth_module()
    import auth

    auth.add_trusted_ip("192.168.1.200", auth.UserRole.OWNER)
    auth.remove_trusted_ip("192.168.1.200")

    ok, _, _, _ = auth.verify_request(None, "192.168.1.200")
    assert ok is False, "移除后应不再免认证"

    print("  ✓ 移除信任 IP 正确")


def test_check_tool_access():
    """工具级别访问控制"""
    _reset_auth_module()
    import auth

    # GUEST 无 device_control 权限 -> 对应工具被拒
    assert auth.check_tool_access(auth.UserRole.GUEST, "control_pc") is False
    assert auth.check_tool_access(auth.UserRole.GUEST, "get_system_info") is True

    # FAMILY 有 device_control -> control_pc 允许
    assert auth.check_tool_access(auth.UserRole.FAMILY, "control_pc") is True

    # OWNER 默认全部允许
    assert auth.check_tool_access(auth.UserRole.OWNER, "any_tool") is True

    # FAMILY 默认也允许未映射工具
    assert auth.check_tool_access(auth.UserRole.FAMILY, "unknown_tool") is True

    print("  ✓ 工具访问控制正确")


def test_tool_access_allowed_tools_whitelist():
    """allowed_tools 白名单限制（即使 OWNER 也受限）"""
    import auth

    # OWNER 但白名单不含 target -> 被拒
    assert auth.check_tool_access(auth.UserRole.OWNER, "control_pc", allowed_tools=["read_notes"]) is False

    # 白名单包含 target -> 允许
    assert auth.check_tool_access(auth.UserRole.GUEST, "read_notes", allowed_tools=["read_notes"]) is True

    # allowed_tools=None -> 不受白名单限制
    assert auth.check_tool_access(auth.UserRole.OWNER, "control_pc", allowed_tools=None) is True

    print("  ✓ allowed_tools 白名单限制正确")


def test_list_api_keys_no_secret():
    """列出 API Key 不泄露密钥"""
    _reset_auth_module()
    import auth

    auth.create_api_key("用户1", auth.UserRole.OWNER)
    keys = auth.list_api_keys()
    assert len(keys) >= 1
    k = keys[0]
    # 不应包含 key_hash 或 raw_key
    assert "key_hash" not in k
    assert "raw" not in str(k).lower() or k.get("raw") is None
    # 应包含元数据
    assert "id" in k
    assert "name" in k
    assert "role" in k

    print("  ✓ API Key 列表不泄露密钥")


def test_key_hash_deterministic():
    """相同 Key 哈希结果一致"""
    import auth

    h1 = auth._hash_key("test_key_123")
    h2 = auth._hash_key("test_key_123")
    assert h1 == h2, "相同输入应产生相同哈希"

    h3 = auth._hash_key("different_key")
    assert h1 != h3, "不同输入应产生不同哈希"

    print("  ✓ Key 哈希确定性正确")


def main():
    print("=== 权限认证模块测试 ===\n")

    test_role_permissions_matrix()
    test_api_key_create_and_verify()
    test_api_key_wrong_key()
    test_api_key_missing()
    test_api_key_revoke()
    test_api_key_revoke_nonexistent()
    test_api_key_quota()
    test_api_key_owner_higher_quota()
    test_trusted_ip_bypass()
    test_trusted_ip_remove()
    test_check_tool_access()
    test_tool_access_allowed_tools_whitelist()
    test_list_api_keys_no_secret()
    test_key_hash_deterministic()

    print("\n=== 权限认证模块测试完成 ===")


if __name__ == "__main__":
    main()
