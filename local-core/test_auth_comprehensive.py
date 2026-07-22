"""
认证模块全面测试
覆盖：API Key管理、权限校验、额度控制、安全边界
"""

import os
import sys
import time
import tempfile
import threading
from pathlib import Path

# 确保可以导入本地模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def setup_clean_env():
    """为每个测试创建干净的环境"""
    import importlib
    # 清除已导入的模块以重置状态
    mods_to_remove = [k for k in sys.modules.keys() if k.startswith('auth')]
    for mod in mods_to_remove:
        del sys.modules[mod]


def test_api_key_hashing():
    """测试 API Key 哈希安全"""
    print("\n=== 测试 API Key 哈希安全 ===")
    
    # 临时设置盐值
    os.environ["AUTH_API_KEY_PEPPER"] = "test_pepper_value_123"
    setup_clean_env()
    from auth import create_api_key, verify_request, UserRole, _hash_key
    
    # 测试哈希确定性
    key = "test_key_123"
    hash1 = _hash_key(key)
    hash2 = _hash_key(key)
    assert hash1 == hash2, "相同key应产生相同哈希"
    assert len(hash1) == 64, "SHA256哈希应为64字符"
    
    # 测试不同key产生不同哈希
    hash3 = _hash_key("different_key")
    assert hash1 != hash3, "不同key应产生不同哈希"
    
    # 测试盐值影响
    os.environ["AUTH_API_KEY_PEPPER"] = "different_pepper"
    setup_clean_env()
    from auth import _hash_key as _hash_key2
    hash_different_salt = _hash_key2(key)
    assert hash1 != hash_different_salt, "不同盐值应产生不同哈希"
    
    print("✅ API Key 哈希安全测试通过")


def test_api_key_lifecycle():
    """测试 API Key 完整生命周期"""
    print("\n=== 测试 API Key 生命周期 ===")
    
    os.environ["AUTH_API_KEY_PEPPER"] = "test_pepper_lifecycle"
    setup_clean_env()
    from auth import (
        create_api_key, revoke_api_key, list_api_keys,
        verify_request, UserRole
    )
    
    # 创建 Key
    raw_key, key_id = create_api_key("测试用户", UserRole.FAMILY)
    assert raw_key, "应返回原始key"
    assert key_id, "应返回key_id"
    assert len(key_id) == 8, "key_id应为8字符"
    
    # 验证 Key
    ok, role, err, api_key_obj = verify_request(raw_key, "127.0.0.1")
    assert ok, f"验证失败: {err}"
    assert role == UserRole.FAMILY
    assert api_key_obj is not None
    assert api_key_obj.key_id == key_id
    
    # 列出 Keys（至少包含新创建的）
    keys = list_api_keys()
    assert len(keys) >= 1
    # 找到新创建的key（字段名是"id"不是"key_id"）
    new_key = next((k for k in keys if k["id"] == key_id), None)
    assert new_key is not None, f"新创建的key应在列表中"
    assert "key_hash" not in new_key, "列表中不应包含哈希"
    assert new_key["role"] == "family"
    
    # 撤销 Key
    result = revoke_api_key(key_id)
    assert result, "撤销应成功"
    
    # 验证已撤销
    ok, role, err, _ = verify_request(raw_key, "127.0.0.1")
    assert not ok, "撤销后验证应失败"
    assert "无效" in err or "缺少" in err
    
    # 重复撤销
    result = revoke_api_key(key_id)
    assert not result, "重复撤销应返回False"
    
    print("✅ API Key 生命周期测试通过")


def test_permission_matrix():
    """测试权限矩阵完整性"""
    print("\n=== 测试权限矩阵 ===")
    
    os.environ["AUTH_API_KEY_PEPPER"] = "test_pepper_perms"
    setup_clean_env()
    from auth import check_permission, check_tool_access, UserRole, ROLE_PERMISSIONS
    
    # OWNER 权限测试
    owner_perms = ROLE_PERMISSIONS[UserRole.OWNER]
    assert "admin_users" in owner_perms
    assert "admin_config" in owner_perms
    assert "chat" in owner_perms
    
    # FAMILY 权限测试
    family_perms = ROLE_PERMISSIONS[UserRole.FAMILY]
    assert "chat" in family_perms
    assert "device_control" in family_perms
    assert "admin_users" not in family_perms
    
    # GUEST 权限测试
    guest_perms = ROLE_PERMISSIONS[UserRole.GUEST]
    assert "chat" in guest_perms
    assert "notify" in guest_perms
    assert "device_control" not in guest_perms
    assert "email_read" not in guest_perms
    
    # check_permission 函数测试
    assert check_permission(UserRole.OWNER, "admin_users")
    assert not check_permission(UserRole.FAMILY, "admin_users")
    assert not check_permission(UserRole.GUEST, "device_control")
    
    # 不存在的权限应返回False
    assert not check_permission(UserRole.OWNER, "nonexistent_permission")
    
    print("✅ 权限矩阵测试通过")


def test_tool_access_control():
    """测试工具访问控制"""
    print("\n=== 测试工具访问控制 ===")
    
    os.environ["AUTH_API_KEY_PEPPER"] = "test_pepper_tools"
    setup_clean_env()
    from auth import check_tool_access, UserRole
    
    # GUEST 不应访问设备控制
    assert not check_tool_access(UserRole.GUEST, "control_pc")
    assert not check_tool_access(UserRole.GUEST, "run_browser_task")
    
    # FAMILY 应能访问大部分工具
    assert check_tool_access(UserRole.FAMILY, "control_pc")
    assert check_tool_access(UserRole.FAMILY, "read_emails")
    
    # OWNER 应能访问所有工具
    assert check_tool_access(UserRole.OWNER, "control_pc")
    assert check_tool_access(UserRole.OWNER, "mqtt_publish")
    
    # allowed_tools 白名单测试
    assert check_tool_access(UserRole.FAMILY, "control_pc", allowed_tools=["control_pc"])
    assert not check_tool_access(UserRole.FAMILY, "control_pc", allowed_tools=["other_tool"])
    
    # OWNER 也受白名单限制
    assert not check_tool_access(UserRole.OWNER, "control_pc", allowed_tools=["other_tool"])
    
    print("✅ 工具访问控制测试通过")


def test_quota_management():
    """测试额度管理"""
    print("\n=== 测试额度管理 ===")
    
    os.environ["AUTH_API_KEY_PEPPER"] = "test_pepper_quota"
    setup_clean_env()
    from auth import (
        create_api_key, verify_request, check_api_key_quota,
        record_api_key_usage, UserRole, _api_keys, _hash_key
    )
    
    raw_key, key_id = create_api_key("额度测试", UserRole.FAMILY)
    
    # 验证并获取对象
    ok, role, err, api_key_obj = verify_request(raw_key, "127.0.0.1")
    assert ok
    key_hash = _hash_key(raw_key)
    
    # 初始额度检查
    can_use, msg = check_api_key_quota(key_hash, 1000)
    assert can_use, f"初始额度应充足: {msg}"
    
    # 记录使用
    result = record_api_key_usage(key_hash, 50000)
    assert result, "记录使用应成功"
    
    # 检查额度减少
    api_key_obj = _api_keys.get(key_hash)
    assert api_key_obj.quota_used == 50000
    
    # 接近上限时应拒绝
    can_use, msg = check_api_key_quota(key_hash, 60000)
    assert not can_use, "超额时应拒绝"
    assert "额度不足" in msg or "无效" in msg
    
    # 验证无效key
    can_use, msg = check_api_key_quota("invalid_hash", 100)
    assert not can_use
    assert "无效" in msg
    
    print("✅ 额度管理测试通过")


def test_trusted_ip():
    """测试信任IP机制"""
    print("\n=== 测试信任IP机制 ===")
    
    os.environ["AUTH_API_KEY_PEPPER"] = "test_pepper_ip"
    setup_clean_env()
    from auth import (
        add_trusted_ip, remove_trusted_ip, verify_request, UserRole
    )
    
    # 添加信任IP
    add_trusted_ip("192.168.1.100", UserRole.OWNER)
    
    # 从信任IP访问应免认证
    ok, role, err, _ = verify_request(None, "192.168.1.100")
    assert ok, "信任IP应免认证"
    assert role == UserRole.OWNER
    
    # 从非信任IP访问应需认证
    ok, role, err, _ = verify_request(None, "192.168.1.200")
    assert not ok
    assert "缺少 API Key" in err
    
    # 移除信任IP
    remove_trusted_ip("192.168.1.100")
    ok, role, err, _ = verify_request(None, "192.168.1.100")
    assert not ok, "移除后应需要认证"
    
    print("✅ 信任IP机制测试通过")


def test_concurrent_access():
    """测试并发访问安全性"""
    print("\n=== 测试并发访问安全性 ===")
    
    os.environ["AUTH_API_KEY_PEPPER"] = "test_pepper_concurrent"
    setup_clean_env()
    from auth import create_api_key, verify_request, UserRole, _api_keys
    
    raw_key, key_id = create_api_key("并发测试", UserRole.FAMILY)
    
    errors = []
    success_count = [0]
    lock = threading.Lock()
    
    def verify_concurrently():
        try:
            for _ in range(100):
                ok, role, err, _ = verify_request(raw_key, "127.0.0.1")
                if ok and role == UserRole.FAMILY:
                    with lock:
                        success_count[0] += 1
        except Exception as e:
            errors.append(str(e))
    
    # 并发验证
    threads = [threading.Thread(target=verify_concurrently) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    assert not errors, f"并发验证出错: {errors}"
    assert success_count[0] == 1000, f"预期1000次成功，实际{success_count[0]}"
    
    print("✅ 并发访问安全性测试通过")


def test_security_boundary():
    """测试安全边界条件"""
    print("\n=== 测试安全边界条件 ===")
    
    os.environ["AUTH_API_KEY_PEPPER"] = "test_pepper_boundary"
    setup_clean_env()
    from auth import verify_request, create_api_key, UserRole
    
    # 空key测试
    ok, role, err, _ = verify_request("", "127.0.0.1")
    assert not ok
    
    # None key测试
    ok, role, err, _ = verify_request(None, "127.0.0.1")
    assert not ok
    
    # 空白key测试
    ok, role, err, _ = verify_request("   ", "127.0.0.1")
    assert not ok
    
    # 超长key测试
    long_key = "a" * 10000
    ok, role, err, _ = verify_request(long_key, "127.0.0.1")
    assert not ok
    
    # 特殊字符key测试
    special_keys = ["../../../etc/passwd", "'; DROP TABLE users; --", "<script>alert(1)</script>"]
    for key in special_keys:
        ok, role, err, _ = verify_request(key, "127.0.0.1")
        assert not ok, f"特殊字符key应被拒绝: {key}"
    
    print("✅ 安全边界条件测试通过")


def main():
    print("=== 认证模块全面测试 ===")
    
    # 创建临时数据目录
    os.makedirs("data", exist_ok=True)
    
    test_api_key_hashing()
    test_api_key_lifecycle()
    test_permission_matrix()
    test_tool_access_control()
    test_quota_management()
    test_trusted_ip()
    test_concurrent_access()
    test_security_boundary()
    
    print("\n=== 全部认证测试通过 ===")


if __name__ == "__main__":
    main()