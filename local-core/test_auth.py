"""
认证模块测试
覆盖API Key管理、权限检查、配额管理、信任域等关键认证功能
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
    add_trusted_ip,
    remove_trusted_ip,
    check_api_key_quota,
    record_api_key_usage,
    _api_keys,
    _TRUSTED_IPS,
)


def setup_test_env():
    os.environ["AUTH_API_KEY_PEPPER"] = "test_pepper_1234567890"
    _api_keys.clear()
    _TRUSTED_IPS.clear()


def test_create_api_key():
    print("1. 测试API Key创建...")
    
    setup_test_env()
    
    raw_key, key_id = create_api_key("测试用户", UserRole.OWNER)
    assert len(raw_key) > 0
    assert len(key_id) == 8
    
    keys = list_api_keys()
    assert len(keys) == 1
    assert keys[0]["name"] == "测试用户"
    assert keys[0]["role"] == "owner"
    assert keys[0]["id"] == key_id
    assert "key_hash" not in keys[0]
    assert "quota_limit" in keys[0]
    
    raw_key2, key_id2 = create_api_key("家庭用户", UserRole.FAMILY)
    assert key_id != key_id2
    
    raw_key3, key_id3 = create_api_key("访客用户", UserRole.GUEST)
    assert key_id3 != key_id2
    
    keys = list_api_keys()
    assert len(keys) == 3
    
    print("  ✓ API Key创建测试通过")


def test_revoke_api_key():
    print("\n2. 测试API Key撤销...")
    
    setup_test_env()
    
    raw_key, key_id = create_api_key("待撤销用户", UserRole.OWNER)
    assert revoke_api_key(key_id) is True
    
    keys = list_api_keys()
    assert len(keys) == 0
    
    assert revoke_api_key("nonexistent") is False
    
    print("  ✓ API Key撤销测试通过")


def test_verify_request():
    print("\n3. 测试请求验证...")
    
    setup_test_env()
    
    raw_key, key_id = create_api_key("测试用户", UserRole.OWNER)
    
    ok, role, err, api_key_obj = verify_request(raw_key, "127.0.0.1")
    assert ok is True
    assert role == UserRole.OWNER
    assert err is None
    assert api_key_obj is not None
    
    ok, role, err, api_key_obj = verify_request("wrong_key", "127.0.0.1")
    assert ok is False
    assert err == "无效的 API Key"
    
    ok, role, err, api_key_obj = verify_request(None, "127.0.0.1")
    assert ok is False
    assert err == "缺少 API Key"
    
    ok, role, err, api_key_obj = verify_request("", "127.0.0.1")
    assert ok is False
    assert err == "缺少 API Key"
    
    print("  ✓ 请求验证测试通过")


def test_check_permission():
    print("\n4. 测试权限检查...")
    
    assert check_permission(UserRole.OWNER, "chat") is True
    assert check_permission(UserRole.OWNER, "admin_users") is True
    assert check_permission(UserRole.OWNER, "device_control") is True
    
    assert check_permission(UserRole.FAMILY, "chat") is True
    assert check_permission(UserRole.FAMILY, "device_control") is True
    assert check_permission(UserRole.FAMILY, "admin_users") is False
    
    assert check_permission(UserRole.GUEST, "chat") is True
    assert check_permission(UserRole.GUEST, "note_read") is True
    assert check_permission(UserRole.GUEST, "device_control") is False
    assert check_permission(UserRole.GUEST, "admin_users") is False
    
    assert check_permission(UserRole.GUEST, "nonexistent") is False
    
    print("  ✓ 权限检查测试通过")


def test_check_tool_access():
    print("\n5. 测试工具访问检查...")
    
    assert check_tool_access(UserRole.OWNER, "control_pc") is True
    assert check_tool_access(UserRole.OWNER, "read_webpage") is True
    assert check_tool_access(UserRole.OWNER, "control_ha_device") is True
    
    assert check_tool_access(UserRole.FAMILY, "control_pc") is True
    assert check_tool_access(UserRole.FAMILY, "read_webpage") is True
    assert check_tool_access(UserRole.FAMILY, "control_ha_device") is True
    
    assert check_tool_access(UserRole.GUEST, "control_pc") is False
    assert check_tool_access(UserRole.GUEST, "read_webpage") is False
    assert check_tool_access(UserRole.GUEST, "send_email") is False
    assert check_tool_access(UserRole.GUEST, "read_notes") is True
    
    assert check_tool_access(UserRole.OWNER, "control_pc", ["control_pc"]) is True
    assert check_tool_access(UserRole.OWNER, "read_webpage", ["control_pc"]) is False
    assert check_tool_access(UserRole.FAMILY, "control_pc", ["read_webpage"]) is False
    
    assert check_tool_access(UserRole.GUEST, "nonexistent") is False
    
    print("  ✓ 工具访问检查测试通过")


def test_quota_management():
    print("\n6. 测试配额管理...")
    
    setup_test_env()
    
    raw_key, key_id = create_api_key("配额测试用户", UserRole.FAMILY)
    key_hash = None
    for kh, ak in _api_keys.items():
        if ak.key_id == key_id:
            key_hash = kh
            break
    assert key_hash is not None
    
    ok, msg = check_api_key_quota(key_hash, 1000)
    assert ok is True
    assert msg == ""
    
    record_api_key_usage(key_hash, 99000)
    
    ok, msg = check_api_key_quota(key_hash, 2000)
    assert ok is False
    assert "额度不足" in msg
    
    ok, msg = check_api_key_quota("nonexistent", 1000)
    assert ok is False
    assert msg == "无效的 API Key"
    
    assert record_api_key_usage("nonexistent", 1000) is False
    
    print("  ✓ 配额管理测试通过")


def test_trusted_ip():
    print("\n7. 测试信任IP管理...")
    
    setup_test_env()
    
    add_trusted_ip("192.168.1.100", UserRole.OWNER)
    assert "192.168.1.100" in _TRUSTED_IPS
    assert _TRUSTED_IPS["192.168.1.100"] == "owner"
    
    ok, role, err, api_key_obj = verify_request(None, "192.168.1.100")
    assert ok is True
    assert role == UserRole.OWNER
    assert err is None
    
    remove_trusted_ip("192.168.1.100")
    assert "192.168.1.100" not in _TRUSTED_IPS
    
    ok, role, err, api_key_obj = verify_request(None, "192.168.1.100")
    assert ok is False
    assert err == "缺少 API Key"
    
    print("  ✓ 信任IP管理测试通过")


def test_persistence():
    print("\n8. 测试API Key持久化...")
    
    setup_test_env()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        original_cwd = os.getcwd()
        try:
            os.chdir(tmpdir)
            os.makedirs("data", exist_ok=True)
            
            raw_key, key_id = create_api_key("持久化测试", UserRole.OWNER)
            keys_before = list_api_keys()
            assert len(keys_before) == 1
            
            _api_keys.clear()
            
            from auth import _load_keys
            _load_keys()
            
            keys_after = list_api_keys()
            assert len(keys_after) == 1
            assert keys_after[0]["name"] == "持久化测试"
            assert keys_after[0]["id"] == key_id
        finally:
            os.chdir(original_cwd)
    
    print("  ✓ API Key持久化测试通过")


def main():
    print("=" * 60)
    print("  认证模块测试")
    print("=" * 60)
    
    test_create_api_key()
    test_revoke_api_key()
    test_verify_request()
    test_check_permission()
    test_check_tool_access()
    test_quota_management()
    test_trusted_ip()
    test_persistence()
    
    print("\n" + "=" * 60)
    print("🎉 认证模块测试全部通过")
    print("=" * 60)


if __name__ == "__main__":
    main()