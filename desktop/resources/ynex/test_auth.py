"""
权限认证模块完整测试
覆盖：API Key 管理、角色权限、配额控制、安全哈希
"""

import os
import time
import tempfile
import json
from auth import (
    UserRole,
    ROLE_PERMISSIONS,
    create_api_key,
    revoke_api_key,
    list_api_keys,
    verify_request,
    check_api_key_quota,
    record_api_key_usage,
    _hash_key,
    _api_keys,
)


def setup_module():
    """测试前清理环境"""
    _api_keys.clear()


def teardown_module():
    """测试后清理"""
    _api_keys.clear()


def test_user_role_permissions():
    """测试角色权限矩阵完整性"""
    print("\n=== 测试角色权限矩阵 ===")

    # 验证 OWNER 拥有所有权限
    assert "admin_users" in ROLE_PERMISSIONS[UserRole.OWNER]
    assert "admin_config" in ROLE_PERMISSIONS[UserRole.OWNER]
    assert "chat" in ROLE_PERMISSIONS[UserRole.OWNER]

    # 验证 FAMILY 缺少管理权限
    assert "admin_users" not in ROLE_PERMISSIONS[UserRole.FAMILY]
    assert "admin_config" not in ROLE_PERMISSIONS[UserRole.FAMILY]
    assert "chat" in ROLE_PERMISSIONS[UserRole.FAMILY]

    # 验证 GUEST 权限最少
    assert "chat" in ROLE_PERMISSIONS[UserRole.GUEST]
    assert "device_control" not in ROLE_PERMISSIONS[UserRole.GUEST]
    assert "admin_users" not in ROLE_PERMISSIONS[UserRole.GUEST]

    print("✅ 角色权限矩阵正确")


def test_api_key_creation():
    """测试 API Key 创建"""
    print("\n=== 测试 API Key 创建 ===")

    # 创建 OWNER 角色的 Key
    raw_key, key_id = create_api_key("test_owner", UserRole.OWNER)
    assert raw_key.startswith("ynex_") or len(raw_key) >= 32
    assert len(key_id) == 8

    # 验证 Key 已存储
    key_hash = _hash_key(raw_key)
    assert key_hash in _api_keys

    api_key_obj = _api_keys[key_hash]
    assert api_key_obj.name == "test_owner"
    assert api_key_obj.role == UserRole.OWNER
    assert api_key_obj.key_id == key_id
    assert api_key_obj.quota_limit == 1000000  # OWNER 配额

    print("✅ API Key 创建成功")


def test_api_key_revocation():
    """测试 API Key 撤销"""
    print("\n=== 测试 API Key 撤销 ===")

    # 创建并立即撤销
    raw_key, key_id = create_api_key("to_revoke", UserRole.FAMILY)
    assert len(list_api_keys()) >= 1

    # 撤销存在的 Key
    result = revoke_api_key(key_id)
    assert result is True

    # 验证已删除
    key_hash = _hash_key(raw_key)
    assert key_hash not in _api_keys

    # 撤销不存在的 Key
    result = revoke_api_key("nonexist")
    assert result is False

    print("✅ API Key 撤销成功")


def test_api_key_verification():
    """测试请求验证逻辑"""
    print("\n=== 测试请求验证 ===")

    # 创建测试 Key
    raw_key, key_id = create_api_key("verify_test", UserRole.FAMILY)

    # 验证有效 Key
    is_valid, role, error, api_obj = verify_request(raw_key, "192.168.1.100")
    assert is_valid is True
    assert role == UserRole.FAMILY
    assert error is None
    assert api_obj is not None
    assert api_obj.key_id == key_id

    # 验证无效 Key
    is_valid, role, error, api_obj = verify_request("invalid_key_12345", "192.168.1.100")
    assert is_valid is False
    assert role == UserRole.GUEST
    assert "无效" in error

    # 验证缺少 Key
    is_valid, role, error, api_obj = verify_request(None, "192.168.1.100")
    assert is_valid is False
    assert "缺少" in error

    print("✅ 请求验证成功")


def test_quota_management():
    """测试配额管理"""
    print("\n=== 测试配额管理 ===")

    raw_key, key_id = create_api_key("quota_test", UserRole.GUEST)
    key_hash = _hash_key(raw_key)

    # 检查初始配额充足
    is_ok, msg = check_api_key_quota(key_hash, 1000)
    assert is_ok is True
    assert msg == ""

    # 记录使用量
    record_api_key_usage(key_hash, 50000)
    api_obj = _api_keys[key_hash]
    assert api_obj.quota_used == 50000

    # 检查超额情况
    is_ok, msg = check_api_key_quota(key_hash, 100000)
    assert is_ok is False
    assert "不足" in msg

    print("✅ 配额管理成功")


def test_key_hash_security():
    """测试密钥哈希安全性"""
    print("\n=== 测试密钥哈希安全 ===")

    # 相同明文应产生相同哈希
    raw1 = "test_key_123"
    hash1 = _hash_key(raw1)
    hash2 = _hash_key(raw1)
    assert hash1 == hash2

    # 不同明文应产生不同哈希
    hash3 = _hash_key("test_key_456")
    assert hash1 != hash3

    # 哈希应为 SHA256 长度
    assert len(hash1) == 64

    print("✅ 密钥哈希安全")


def test_list_api_keys():
    """测试 API Key 列表"""
    print("\n=== 测试 API Key 列表 ===")

    # 创建多个 Key
    create_api_key("list_test_1", UserRole.OWNER)
    create_api_key("list_test_2", UserRole.FAMILY)
    create_api_key("list_test_3", UserRole.GUEST)

    keys = list_api_keys()
    assert len(keys) >= 3

    # 验证返回的数据结构
    for k in keys:
        assert "id" in k
        assert "name" in k
        assert "role" in k
        assert "created_at" in k
        assert "quota_used" in k
        assert "quota_limit" in k

    print("✅ API Key 列表正确")


def test_role_based_tool_restrictions():
    """测试基于角色的工具限制"""
    print("\n=== 测试工具限制 ===")

    # 创建受限工具的 Key
    raw_key, key_id = create_api_key(
        "restricted_user",
        UserRole.FAMILY,
        allowed_tools=["chat", "command"]
    )

    key_hash = _hash_key(raw_key)
    api_obj = _api_keys[key_hash]

    assert api_obj.allowed_tools == ["chat", "command"]

    print("✅ 工具限制正确")


def test_last_used_timestamp():
    """测试最后使用时间戳更新"""
    print("\n=== 测试最后使用时间戳 ===")

    raw_key, key_id = create_api_key("timestamp_test", UserRole.GUEST)
    key_hash = _hash_key(raw_key)

    # 获取初始时间戳
    initial_ts = _api_keys[key_hash].last_used

    # 等待一小段时间
    time.sleep(0.1)

    # 使用 Key 后应更新时间戳
    verify_request(raw_key, "192.168.1.100")
    updated_ts = _api_keys[key_hash].last_used

    assert updated_ts >= initial_ts

    print("✅ 时间戳更新正确")


def test_key_id_collision_resistance():
    """测试 Key ID 碰撞抵抗"""
    print("\n=== 测试 Key ID 碰撞抵抗 ===")

    key_ids = set()
    for i in range(100):
        _, key_id = create_api_key(f"collision_test_{i}", UserRole.GUEST)
        assert key_id not in key_ids, f"Key ID 碰撞: {key_id}"
        key_ids.add(key_id)

    print(f"✅ 100 个 Key ID 无碰撞")


def main():
    print("=" * 60)
    print("  权限认证模块完整测试")
    print("=" * 60)

    setup_module()

    try:
        test_user_role_permissions()
        test_api_key_creation()
        test_api_key_revocation()
        test_api_key_verification()
        test_quota_management()
        test_key_hash_security()
        test_list_api_keys()
        test_role_based_tool_restrictions()
        test_last_used_timestamp()
        test_key_id_collision_resistance()

        print("\n" + "=" * 60)
        print("🎉 所有认证测试通过")
        print("=" * 60)

    finally:
        teardown_module()


if __name__ == "__main__":
    main()