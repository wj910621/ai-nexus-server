"""
认证模块测试
覆盖 API Key 管理、权限验证、配额检查、信任域等核心安全功能
"""

import os
import tempfile
import shutil
from auth import (
    UserRole,
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
    _load_keys,
    _save_keys,
    _api_keys,
    _TRUSTED_IPS,
)


def reset_state():
    """重置全局状态用于隔离测试"""
    _api_keys.clear()
    _TRUSTED_IPS.clear()


def main():
    print("=== 认证模块测试 ===\n")
    reset_state()

    print("1. API Key 创建与列表...")
    raw_key, key_id = create_api_key("测试用户", UserRole.FAMILY)
    assert len(raw_key) > 20, "API Key 长度不足"
    assert len(key_id) == 8, "key_id 应为 8 位"
    
    keys = list_api_keys()
    assert len(keys) == 1
    assert keys[0]["name"] == "测试用户"
    assert keys[0]["role"] == "family"
    assert "key_hash" not in keys[0], "列表不应包含密钥哈希"
    print("  ✓ 创建与列表正确")

    print("\n2. API Key 撤销...")
    result = revoke_api_key(key_id)
    assert result is True
    keys = list_api_keys()
    assert len(keys) == 0
    
    result = revoke_api_key("不存在的ID")
    assert result is False
    print("  ✓ 撤销正确")

    print("\n3. 权限矩阵验证...")
    raw_owner, _ = create_api_key("管理员", UserRole.OWNER)
    raw_family, _ = create_api_key("家庭成员", UserRole.FAMILY)
    raw_guest, _ = create_api_key("访客", UserRole.GUEST)
    
    assert check_permission(UserRole.OWNER, "admin_users") is True
    assert check_permission(UserRole.FAMILY, "admin_users") is False
    assert check_permission(UserRole.GUEST, "admin_users") is False
    
    assert check_permission(UserRole.GUEST, "chat") is True
    assert check_permission(UserRole.GUEST, "device_control") is False
    print("  ✓ 权限矩阵正确")

    print("\n4. 工具访问控制...")
    assert check_tool_access(UserRole.OWNER, "control_pc") is True
    assert check_tool_access(UserRole.FAMILY, "control_pc") is True
    assert check_tool_access(UserRole.GUEST, "control_pc") is False
    
    assert check_tool_access(UserRole.OWNER, "control_pc", allowed_tools=["read_webpage"]) is False
    assert check_tool_access(UserRole.FAMILY, "read_webpage", allowed_tools=["read_webpage"]) is True
    print("  ✓ 工具访问控制正确")

    print("\n5. 请求认证验证...")
    ok, role, err, key_obj = verify_request(raw_owner, "127.0.0.1")
    assert ok is True
    assert role == UserRole.OWNER
    
    ok, role, err, key_obj = verify_request(None, "127.0.0.1")
    assert ok is False
    assert err == "缺少 API Key"
    
    ok, role, err, key_obj = verify_request("无效密钥", "127.0.0.1")
    assert ok is False
    assert err == "无效的 API Key"
    print("  ✓ 请求认证正确")

    print("\n6. 配额检查与使用记录...")
    _, kid = create_api_key("配额测试", UserRole.FAMILY)
    keys = list_api_keys()
    quota_key = next(k for k in keys if k["id"] == kid)
    assert quota_key["quota_used"] == 0
    assert quota_key["quota_limit"] == 100000
    
    ok, err = check_api_key_quota(list(_api_keys.keys())[-1])
    assert ok is True
    
    record_api_key_usage(list(_api_keys.keys())[-1], 5000)
    keys = list_api_keys()
    quota_key = next(k for k in keys if k["id"] == kid)
    assert quota_key["quota_used"] == 5000
    print("  ✓ 配额管理正确")

    print("\n7. 信任域管理...")
    reset_state()
    add_trusted_ip("192.168.1.100", UserRole.FAMILY)
    ok, role, err, key_obj = verify_request(None, "192.168.1.100")
    assert ok is True
    assert role == UserRole.FAMILY
    
    remove_trusted_ip("192.168.1.100")
    ok, role, err, key_obj = verify_request(None, "192.168.1.100")
    assert ok is False
    print("  ✓ 信任域管理正确")

    print("\n8. 持久化测试...")
    reset_state()
    test_dir = tempfile.mkdtemp(prefix="ynex_test_")
    original_cwd = os.getcwd()
    try:
        os.chdir(test_dir)
        os.makedirs("data", exist_ok=True)
        create_api_key("持久化测试", UserRole.OWNER)
        _save_keys()
        
        _api_keys.clear()
        _load_keys()
        
        keys = list_api_keys()
        assert len(keys) == 1
        assert keys[0]["name"] == "持久化测试"
        print("  ✓ 持久化正确")
    finally:
        os.chdir(original_cwd)
        shutil.rmtree(test_dir, ignore_errors=True)

    print("\n=== 认证模块测试完成 ===")


if __name__ == "__main__":
    main()