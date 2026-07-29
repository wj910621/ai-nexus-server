"""
认证模块全面测试
覆盖：
  - API Key 创建、验证、撤销
  - 角色权限矩阵
  - 工具访问控制
  - 额度管理
  - 信任 IP 功能
  - 安全哈希
"""

import os
import sys
import tempfile
import json
import time
import threading
from pathlib import Path

# 设置测试环境
os.environ.setdefault("AUTH_API_KEY_PEPPER", "test_pepper_for_unit_tests_12345")
os.makedirs("data", exist_ok=True)

# 导入认证模块
from auth import (
    UserRole,
    ROLE_PERMISSIONS,
    ApiKey,
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
    _hash_key,
    _api_keys,
    _TRUSTED_IPS,
)


def setup_module():
    """测试前清空 API Keys"""
    _api_keys.clear()
    _TRUSTED_IPS.clear()


def teardown_module():
    """测试后清理"""
    _api_keys.clear()
    _TRUSTED_IPS.clear()


class TestApiKeyCreation:
    """API Key 创建测试"""

    def test_create_owner_key(self):
        """测试创建 owner 角色的 API Key"""
        raw_key, key_id = create_api_key("test_owner", UserRole.OWNER)
        
        # 验证返回值
        assert raw_key is not None and len(raw_key) > 32, "API Key 应该是足够长的随机字符串"
        assert key_id is not None and len(key_id) == 8, "Key ID 应为 8 位"
        
        # 验证 Key 已存储
        key_hash = _hash_key(raw_key)
        assert key_hash in _api_keys, "Key 应该被存储在内存中"
        
        # 验证 Key 属性
        api_key = _api_keys[key_hash]
        assert api_key.role == UserRole.OWNER
        assert api_key.name == "test_owner"
        assert api_key.quota_limit == 1000000, "Owner 默认额度应为 1000000"

    def test_create_guest_key(self):
        """测试创建 guest 角色的 API Key"""
        raw_key, key_id = create_api_key("test_guest", UserRole.GUEST)
        
        key_hash = _hash_key(raw_key)
        api_key = _api_keys[key_hash]
        
        assert api_key.role == UserRole.GUEST
        assert api_key.quota_limit == 100000, "Guest 默认额度应为 100000"

    def test_create_key_with_tools_whitelist(self):
        """测试创建带工具白名单的 Key"""
        allowed_tools = ["chat", "read_notes"]
        raw_key, key_id = create_api_key(
            "limited_user",
            UserRole.FAMILY,
            allowed_tools=allowed_tools
        )
        
        key_hash = _hash_key(raw_key)
        api_key = _api_keys[key_hash]
        
        assert api_key.allowed_tools == allowed_tools

    def test_key_uniqueness(self):
        """测试多次创建的 Key 不重复"""
        keys = set()
        for i in range(10):
            raw_key, _ = create_api_key(f"unique_{i}", UserRole.GUEST)
            keys.add(raw_key)
        
        assert len(keys) == 10, "每次创建的 Key 应该唯一"


class TestApiKeyVerification:
    """API Key 验证测试"""

    def test_verify_valid_key(self):
        """测试验证有效的 API Key"""
        raw_key, _ = create_api_key("verify_test", UserRole.FAMILY)
        
        ok, role, err, api_key_obj = verify_request(raw_key, "127.0.0.1")
        
        assert ok is True
        assert role == UserRole.FAMILY
        assert err is None
        assert api_key_obj is not None

    def test_verify_invalid_key(self):
        """测试验证无效的 API Key"""
        ok, role, err, api_key_obj = verify_request("invalid_key_12345", "127.0.0.1")
        
        assert ok is False
        assert role == UserRole.GUEST
        assert "无效" in err

    def test_verify_missing_key(self):
        """测试缺少 API Key 的情况"""
        ok, role, err, api_key_obj = verify_request(None, "127.0.0.1")
        
        assert ok is False
        assert "缺少" in err

    def test_verify_trusted_ip(self):
        """测试信任 IP 直接通过"""
        add_trusted_ip("192.168.1.100", UserRole.OWNER)
        
        ok, role, err, api_key_obj = verify_request(None, "192.168.1.100")
        
        assert ok is True
        assert role == UserRole.OWNER
        
        remove_trusted_ip("192.168.1.100")

    def test_verify_updates_last_used(self):
        """测试验证时更新 last_used 时间"""
        raw_key, _ = create_api_key("last_used_test", UserRole.GUEST)
        key_hash = _hash_key(raw_key)
        
        # 先记录原始时间
        original_time = _api_keys[key_hash].last_used
        time.sleep(0.1)
        
        verify_request(raw_key, "127.0.0.1")
        
        new_time = _api_keys[key_hash].last_used
        assert new_time > original_time


class TestApiKeyRevocation:
    """API Key 撤销测试"""

    def test_revoke_existing_key(self):
        """测试撤销存在的 Key"""
        raw_key, key_id = create_api_key("revoke_test", UserRole.GUEST)
        
        result = revoke_api_key(key_id)
        assert result is True
        
        # 验证 Key 已被删除
        key_hash = _hash_key(raw_key)
        assert key_hash not in _api_keys

    def test_revoke_nonexistent_key(self):
        """测试撤销不存在的 Key"""
        result = revoke_api_key("notexist")
        assert result is False


class TestPermissionSystem:
    """权限系统测试"""

    def test_owner_has_all_permissions(self):
        """测试 Owner 拥有所有权限"""
        owner_perms = ROLE_PERMISSIONS[UserRole.OWNER]
        
        # Owner 应该包含关键权限
        assert "chat" in owner_perms
        assert "device_control" in owner_perms
        assert "admin_users" in owner_perms
        assert "admin_config" in owner_perms

    def test_family_has_no_admin_permissions(self):
        """测试 Family 没有管理员权限"""
        family_perms = ROLE_PERMISSIONS[UserRole.FAMILY]
        
        assert "chat" in family_perms
        assert "device_control" in family_perms
        assert "admin_users" not in family_perms
        assert "admin_config" not in family_perms

    def test_guest_has_minimal_permissions(self):
        """测试 Guest 只有最小权限"""
        guest_perms = ROLE_PERMISSIONS[UserRole.GUEST]
        
        assert "chat" in guest_perms
        assert "device_control" not in guest_perms
        assert "email_send" not in guest_perms
        assert "browser" not in guest_perms

    def test_check_permission_function(self):
        """测试 check_permission 函数"""
        assert check_permission(UserRole.OWNER, "admin_users") is True
        assert check_permission(UserRole.FAMILY, "admin_users") is False
        assert check_permission(UserRole.GUEST, "chat") is True
        assert check_permission(UserRole.GUEST, "device_control") is False


class TestToolAccess:
    """工具访问控制测试"""

    def test_owner_can_access_all_tools(self):
        """测试 Owner 可以访问所有工具"""
        assert check_tool_access(UserRole.OWNER, "control_pc") is True
        assert check_tool_access(UserRole.OWNER, "send_email") is True
        assert check_tool_access(UserRole.OWNER, "write_note") is True

    def test_guest_cannot_access_sensitive_tools(self):
        """测试 Guest 不能访问敏感工具"""
        assert check_tool_access(UserRole.GUEST, "control_pc") is False
        assert check_tool_access(UserRole.GUEST, "send_email") is False

    def test_tool_whitelist_restriction(self):
        """测试工具白名单限制"""
        allowed_tools = ["chat", "read_notes"]
        
        # 即使是 Owner，如果 Key 有白名单，也要受限
        assert check_tool_access(UserRole.OWNER, "chat", allowed_tools) is True
        assert check_tool_access(UserRole.OWNER, "control_pc", allowed_tools) is False

    def test_family_can_access_device_control(self):
        """测试 Family 可以访问设备控制"""
        assert check_tool_access(UserRole.FAMILY, "control_pc") is True
        assert check_tool_access(UserRole.FAMILY, "control_ha_device") is True


class TestQuotaSystem:
    """额度系统测试"""

    def test_check_quota_sufficient(self):
        """测试额度充足的情况"""
        raw_key, _ = create_api_key("quota_test", UserRole.GUEST)
        key_hash = _hash_key(raw_key)
        
        ok, msg = check_api_key_quota(key_hash, 1000)
        assert ok is True

    def test_check_quota_insufficient(self):
        """测试额度不足的情况"""
        raw_key, _ = create_api_key("quota_low", UserRole.GUEST)
        key_hash = _hash_key(raw_key)
        
        # 模拟大量使用
        _api_keys[key_hash].quota_used = 99900
        
        ok, msg = check_api_key_quota(key_hash, 200)
        assert ok is False
        assert "额度不足" in msg

    def test_record_usage(self):
        """测试记录使用量"""
        raw_key, _ = create_api_key("usage_test", UserRole.GUEST)
        key_hash = _hash_key(raw_key)
        
        original_used = _api_keys[key_hash].quota_used
        
        result = record_api_key_usage(key_hash, 500)
        assert result is True
        assert _api_keys[key_hash].quota_used == original_used + 500

    def test_record_usage_invalid_key(self):
        """测试对无效 Key 记录使用量"""
        result = record_api_key_usage("invalid_hash", 100)
        assert result is False


class TestSecurity:
    """安全性测试"""

    def test_key_hashing_is_deterministic(self):
        """测试哈希是确定性的"""
        key = "test_key_12345"
        
        hash1 = _hash_key(key)
        hash2 = _hash_key(key)
        
        assert hash1 == hash2

    def test_key_hashing_differs_from_plaintext(self):
        """测试哈希与明文不同"""
        key = "my_secret_key_123"
        hashed = _hash_key(key)
        
        assert hashed != key
        assert len(hashed) == 64  # SHA256 hex 输出长度

    def test_different_keys_have_different_hashes(self):
        """测试不同 Key 产生不同哈希"""
        key1 = "key_one"
        key2 = "key_two"
        
        assert _hash_key(key1) != _hash_key(key2)

    def test_list_keys_does_not_expose_hashes(self):
        """测试列出 Keys 不暴露哈希值"""
        create_api_key("list_test", UserRole.GUEST)
        
        keys = list_api_keys()
        
        for k in keys:
            assert "key_hash" not in k
            assert "hash" not in k


class TestConcurrency:
    """并发测试"""

    def test_concurrent_key_creation(self):
        """测试并发创建 Key"""
        results = []
        
        def create_key(i):
            try:
                raw_key, key_id = create_api_key(f"concurrent_{i}", UserRole.GUEST)
                results.append((raw_key, key_id))
            except Exception as e:
                results.append(None)
        
        threads = [
            threading.Thread(target=create_key, args=(i,))
            for i in range(5)
        ]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # 验证所有 Key 都创建成功
        successful = [r for r in results if r is not None]
        assert len(successful) == 5

    def test_concurrent_quota_update(self):
        """测试并发更新额度"""
        raw_key, _ = create_api_key("concurrent_quota", UserRole.GUEST)
        key_hash = _hash_key(raw_key)
        
        def update_quota():
            for _ in range(10):
                record_api_key_usage(key_hash, 1)
        
        threads = [threading.Thread(target=update_quota) for _ in range(3)]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # 验证额度正确（30 次 * 1 = 30）
        assert _api_keys[key_hash].quota_used >= 30


def run_tests():
    """运行所有测试"""
    import traceback
    
    setup_module()
    
    test_classes = [
        TestApiKeyCreation,
        TestApiKeyVerification,
        TestApiKeyRevocation,
        TestPermissionSystem,
        TestToolAccess,
        TestQuotaSystem,
        TestSecurity,
        TestConcurrency,
    ]
    
    total = 0
    passed = 0
    failed = 0
    
    for test_class in test_classes:
        print(f"\n{'='*60}")
        print(f"  {test_class.__name__}")
        print(f"{'='*60}")
        
        instance = test_class()
        
        for method_name in dir(instance):
            if method_name.startswith("test_"):
                total += 1
                method = getattr(instance, method_name)
                try:
                    method()
                    print(f"  ✓ {method_name}")
                    passed += 1
                except AssertionError as e:
                    print(f"  ✗ {method_name}: {e}")
                    failed += 1
                except Exception as e:
                    print(f"  ✗ {method_name}: {type(e).__name__}: {e}")
                    traceback.print_exc()
                    failed += 1
    
    teardown_module()
    
    print(f"\n{'='*60}")
    print(f"  测试结果: {passed}/{total} 通过")
    print(f"{'='*60}")
    
    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)