"""
auth.py 综合测试
覆盖：API Key 管理、权限校验、额度控制、安全哈希等核心路径
"""

import os
import tempfile
import time
import json
import shutil
import sys

# 添加路径以导入模块
sys.path.insert(0, os.path.dirname(__file__))

import auth
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
    ApiKey,
)


def setup_test_env():
    """创建测试环境"""
    test_dir = tempfile.mkdtemp(prefix="test_auth_")
    os.chdir(test_dir)
    os.makedirs("data", exist_ok=True)

    # 重置全局状态
    auth._api_keys.clear()
    auth._TRUSTED_IPS.clear()

    return test_dir


def teardown_test_env(test_dir):
    """清理测试环境"""
    os.chdir("/")
    shutil.rmtree(test_dir, ignore_errors=True)


def test_api_key_creation():
    """测试 API Key 创建流程"""
    print("\n=== 测试 API Key 创建 ===")

    # 创建 owner key
    raw_key, key_id = create_api_key("测试管理员", UserRole.OWNER)
    assert raw_key, "应该返回明文 Key"
    assert key_id, "应该返回 key_id"
    assert len(key_id) == 8, "key_id 应该是 8 位"

    # 验证 Key 不等于 hash
    assert raw_key != key_id, "明文 Key 不应等于 key_id"

    print(f"✓ 创建成功: key_id={key_id}, raw_key长度={len(raw_key)}")

    # 创建 family key
    raw_key2, key_id2 = create_api_key("家庭成员", UserRole.FAMILY)
    assert raw_key2
    assert key_id2 != key_id, "不同 Key 应有不同 ID"
    print("✓ 可以创建多个 Key")


def test_api_key_revocation():
    """测试 API Key 撤销"""
    print("\n=== 测试 API Key 撤销 ===")

    raw_key, key_id = create_api_key("待撤销用户", UserRole.GUEST)

    # 撤销
    result = revoke_api_key(key_id)
    assert result, "撤销应成功"

    # 验证已删除
    keys = list_api_keys()
    assert not any(k["id"] == key_id for k in keys)

    # 重复撤销应失败
    result2 = revoke_api_key(key_id)
    assert not result2, "重复撤销应失败"

    print("✓ 撤销流程正确")


def test_api_key_verification():
    """测试 API Key 验证"""
    print("\n=== 测试 API Key 验证 ===")

    raw_key, key_id = create_api_key("验证测试", UserRole.OWNER)

    # 正确验证
    ok, role, err, api_key_obj = verify_request(raw_key, "127.0.0.1")
    assert ok, f"验证应成功，错误: {err}"
    assert role == UserRole.OWNER
    assert api_key_obj is not None
    assert api_key_obj.key_id == key_id

    # 错误 Key
    ok2, role2, err2, _ = verify_request("invalid_key", "127.0.0.1")
    assert not ok2
    assert "无效的 API Key" in err2

    # 缺少 Key
    ok3, role3, err3, _ = verify_request(None, "127.0.0.1")
    assert not ok3
    assert "缺少 API Key" in err3

    print("✓ 验证逻辑正确")


def test_permission_matrix():
    """测试权限矩阵"""
    print("\n=== 测试权限矩阵 ===")

    # OWNER 权限
    assert check_permission(UserRole.OWNER, "admin_users")
    assert check_permission(UserRole.OWNER, "device_control")
    assert check_permission(UserRole.OWNER, "chat")

    # FAMILY 权限
    assert check_permission(UserRole.FAMILY, "device_control")
    assert not check_permission(UserRole.FAMILY, "admin_users")

    # GUEST 权限
    assert check_permission(UserRole.GUEST, "chat")
    assert not check_permission(UserRole.GUEST, "device_control")
    assert not check_permission(UserRole.GUEST, "admin_config")

    print("✓ 权限矩阵正确")


def test_tool_access_control():
    """测试工具访问控制"""
    print("\n=== 测试工具访问控制 ===")

    # OWNER 应可访问所有工具
    assert check_tool_access(UserRole.OWNER, "control_pc")
    assert check_tool_access(UserRole.OWNER, "admin_config")

    # GUEST 仅可访问基础工具
    assert check_tool_access(UserRole.GUEST, "get_system_info")
    assert not check_tool_access(UserRole.GUEST, "control_pc")

    # 白名单限制测试
    allowed_tools = ["chat", "get_system_info"]
    assert check_tool_access(UserRole.OWNER, "chat", allowed_tools)
    assert not check_tool_access(UserRole.OWNER, "control_pc", allowed_tools)

    print("✓ 工具访问控制正确")


def test_quota_tracking():
    """测试额度追踪"""
    print("\n=== 测试额度追踪 ===")

    raw_key, key_id = create_api_key("额度测试", UserRole.GUEST)

    # 验证获取 key_hash
    ok, role, err, api_key_obj = verify_request(raw_key, "127.0.0.1")
    assert ok
    key_hash = api_key_obj.key_hash

    # 检查额度
    has_quota, msg = check_api_key_quota(key_hash, 1000)
    assert has_quota

    # 记录使用
    result = record_api_key_usage(key_hash, 500)
    assert result

    # 再次检查
    keys = list_api_keys()
    key_info = next(k for k in keys if k["id"] == key_id)
    assert key_info["quota_used"] == 500

    print("✓ 额度追踪正确")


def test_trusted_ip():
    """测试信任 IP 管理"""
    print("\n=== 测试信任 IP ===")

    # 添加信任 IP
    add_trusted_ip("192.168.1.100", UserRole.FAMILY)

    # 验证信任 IP 可免认证
    ok, role, err, _ = verify_request(None, "192.168.1.100")
    assert ok
    assert role == UserRole.FAMILY

    # 移除信任 IP
    remove_trusted_ip("192.168.1.100")

    # 再次验证应失败
    ok2, role2, err2, _ = verify_request(None, "192.168.1.100")
    assert not ok2

    print("✓ 信任 IP 管理正确")


def test_key_persistence():
    """测试 Key 持久化"""
    print("\n=== 测试持久化 ===")

    raw_key, key_id = create_api_key("持久化测试", UserRole.OWNER)

    # 加载已保存的 Key
    auth._load_keys()

    keys = list_api_keys()
    saved_key = next((k for k in keys if k["id"] == key_id), None)
    assert saved_key, "应能从文件加载已保存的 Key"
    assert saved_key["role"] == "owner"

    print("✓ 持久化正确")


def test_pepper_security():
    """测试哈希盐安全性"""
    print("\n=== 测试哈希盐安全 ===")

    # 验证相同 Key 在不同盐下产生不同 hash
    test_key = "test_key_12345"

    # 使用当前盐
    hash1 = auth._hash_key(test_key)

    # 临时修改盐
    original_pepper = auth._API_KEY_PEPPER
    auth._API_KEY_PEPPER = "different_pepper_for_test"
    hash2 = auth._hash_key(test_key)

    # 还原盐
    auth._API_KEY_PEPPER = original_pepper

    assert hash1 != hash2, "不同盐应产生不同哈希"
    print("✓ 哈希盐安全机制正确")


def test_last_used_update():
    """测试最后使用时间更新"""
    print("\n=== 测试最后使用时间更新 ===")

    raw_key, key_id = create_api_key("时间测试", UserRole.OWNER)

    # 验证前检查 last_used
    keys_before = list_api_keys()
    key_before = next(k for k in keys_before if k["id"] == key_id)
    assert key_before["last_used"] == 0

    # 验证
    time.sleep(0.1)
    verify_request(raw_key, "127.0.0.1")

    # 检查时间更新
    keys_after = list_api_keys()
    key_after = next(k for k in keys_after if k["id"] == key_id)
    assert key_after["last_used"] > key_before["last_used"]

    print("✓ 最后使用时间更新正确")


def run_all_tests():
    """运行所有测试"""
    test_dir = setup_test_env()
    try:
        test_api_key_creation()
        test_api_key_revocation()
        test_api_key_verification()
        test_permission_matrix()
        test_tool_access_control()
        test_quota_tracking()
        test_trusted_ip()
        test_key_persistence()
        test_pepper_security()
        test_last_used_update()

        print("\n" + "="*50)
        print("✅ 所有 auth.py 测试通过")
        print("="*50)

    finally:
        teardown_test_env(test_dir)


if __name__ == "__main__":
    run_all_tests()