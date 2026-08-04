"""
权限认证模块测试
- API Key 创建/验证/撤销生命周期
- 角色权限矩阵（owner / family / guest）
- 工具访问控制（角色权限 + 白名单）
- 额度检查与用量记录
- 信任 IP 免认证
"""
import os

# 在导入 auth 前设置固定盐，确保哈希在测试间确定性一致
os.environ.setdefault("AUTH_API_KEY_PEPPER", "test-pepper-fixed-for-deterministic-tests")

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
    _api_keys,
    _TRUSTED_IPS,
    _hash_key,
)


def _reset_state():
    """清空全局状态，确保测试间隔离"""
    _api_keys.clear()
    _TRUSTED_IPS.clear()


# ---------------------------------------------------------------------------
# 权限矩阵
# ---------------------------------------------------------------------------

def test_permission_matrix():
    """三级角色权限边界"""
    # OWNER：完全控制，包括 admin 权限
    assert check_permission(UserRole.OWNER, "admin_users") is True
    assert check_permission(UserRole.OWNER, "admin_config") is True
    assert check_permission(UserRole.OWNER, "admin_skills") is True
    assert check_permission(UserRole.OWNER, "chat") is True
    assert check_permission(UserRole.OWNER, "device_control") is True

    # FAMILY：工具权限齐全，但无 admin 权限
    assert check_permission(UserRole.FAMILY, "chat") is True
    assert check_permission(UserRole.FAMILY, "device_control") is True
    assert check_permission(UserRole.FAMILY, "email_send") is True
    assert check_permission(UserRole.FAMILY, "admin_users") is False
    assert check_permission(UserRole.FAMILY, "admin_config") is False

    # GUEST：仅基础权限
    assert check_permission(UserRole.GUEST, "chat") is True
    assert check_permission(UserRole.GUEST, "note_read") is True
    assert check_permission(UserRole.GUEST, "system_info") is True
    assert check_permission(UserRole.GUEST, "notify") is True
    assert check_permission(UserRole.GUEST, "device_control") is False
    assert check_permission(UserRole.GUEST, "email_send") is False
    assert check_permission(UserRole.GUEST, "admin_users") is False


# ---------------------------------------------------------------------------
# 工具访问控制
# ---------------------------------------------------------------------------

def test_tool_access_role():
    """角色决定可用工具"""
    # OWNER 可使用所有工具
    assert check_tool_access(UserRole.OWNER, "control_pc") is True
    assert check_tool_access(UserRole.OWNER, "read_notes") is True
    assert check_tool_access(UserRole.OWNER, "send_email") is True

    # FAMILY 也可使用所有工具
    assert check_tool_access(UserRole.FAMILY, "control_pc") is True

    # GUEST 仅基础工具
    assert check_tool_access(UserRole.GUEST, "read_notes") is True
    assert check_tool_access(UserRole.GUEST, "get_system_info") is True
    assert check_tool_access(UserRole.GUEST, "control_pc") is False
    assert check_tool_access(UserRole.GUEST, "send_email") is False
    assert check_tool_access(UserRole.GUEST, "mqtt_publish") is False


def test_tool_access_whitelist():
    """allowed_tools 白名单优先于角色权限"""
    # 即使 OWNER，白名单外工具也被拒绝
    assert check_tool_access(UserRole.OWNER, "control_pc", allowed_tools=["read_notes"]) is False
    # 白名单内工具仍需角色权限通过
    assert check_tool_access(UserRole.OWNER, "read_notes", allowed_tools=["read_notes"]) is True

    # GUEST + 白名单：白名单内但角色无权限 → 仍拒绝
    assert check_tool_access(UserRole.GUEST, "control_pc", allowed_tools=["control_pc"]) is False
    # GUEST + 白名单：白名单内且角色有权限 → 允许
    assert check_tool_access(UserRole.GUEST, "read_notes", allowed_tools=["read_notes"]) is True


# ---------------------------------------------------------------------------
# API Key 生命周期
# ---------------------------------------------------------------------------

def test_api_key_lifecycle():
    """创建 → 列表 → 撤销"""
    _reset_state()

    # 创建
    raw_key, key_id = create_api_key("测试家庭用户", UserRole.FAMILY)
    assert raw_key, "明文 key 不应为空"
    assert len(key_id) == 8, "key_id 应为 8 位"

    # 哈希不等于明文
    assert _hash_key(raw_key) != raw_key

    # 列表（不泄露哈希）
    keys = list_api_keys()
    assert len(keys) == 1
    meta = keys[0]
    assert meta["name"] == "测试家庭用户"
    assert meta["role"] == "family"
    assert meta["id"] == key_id
    assert "key_hash" not in meta, "列表不应暴露 key_hash"

    # 撤销
    assert revoke_api_key(key_id) is True
    assert revoke_api_key(key_id) is False, "重复撤销应返回 False"
    assert len(list_api_keys()) == 0


def test_api_key_role_quota_defaults():
    """不同角色的默认额度不同"""
    _reset_state()

    _, _ = create_api_key("owner用户", UserRole.OWNER)
    _, _ = create_api_key("guest用户", UserRole.GUEST)

    keys = list_api_keys()
    owner_key = next(k for k in keys if k["role"] == "owner")
    guest_key = next(k for k in keys if k["role"] == "guest")
    assert owner_key["quota_limit"] == 1000000
    assert guest_key["quota_limit"] == 100000


# ---------------------------------------------------------------------------
# 请求验证
# ---------------------------------------------------------------------------

def test_verify_request_missing_key():
    """无 API Key 且非信任 IP → 拒绝"""
    _reset_state()
    ok, role, err, _ = verify_request(None, "192.168.1.100")
    assert ok is False
    assert err == "缺少 API Key"


def test_verify_request_invalid_key():
    """无效 API Key → 拒绝"""
    _reset_state()
    ok, role, err, _ = verify_request("invalid-key-xxx", "192.168.1.100")
    assert ok is False
    assert "无效" in err


def test_verify_request_valid_key():
    """有效 API Key → 通过，返回正确角色"""
    _reset_state()
    raw_key, key_id = create_api_key("测试Owner", UserRole.OWNER)

    ok, role, err, key_obj = verify_request(raw_key, "192.168.1.100")
    assert ok is True
    assert role == UserRole.OWNER
    assert err is None
    assert key_obj is not None
    assert key_obj.key_id == key_id
    # 验证后 last_used 应被更新
    assert key_obj.last_used > 0


def test_verify_request_trusted_ip():
    """信任 IP 免认证"""
    _reset_state()
    add_trusted_ip("192.168.1.200", UserRole.FAMILY)

    ok, role, err, key_obj = verify_request(None, "192.168.1.200")
    assert ok is True
    assert role == UserRole.FAMILY
    assert key_obj is None, "信任 IP 不返回 key 对象"

    # 非信任 IP 仍需认证
    ok, _, _, _ = verify_request(None, "192.168.1.201")
    assert ok is False

    remove_trusted_ip("192.168.1.200")
    # 移除后不再免认证
    ok, _, _, _ = verify_request(None, "192.168.1.200")
    assert ok is False


# ---------------------------------------------------------------------------
# 额度检查
# ---------------------------------------------------------------------------

def test_quota_check_and_record():
    """额度检查与用量记录"""
    _reset_state()
    raw_key, _ = create_api_key("额度测试", UserRole.GUEST)
    key_hash = _hash_key(raw_key)

    # 初始额度充足（GUEST 默认 100000）
    ok, msg = check_api_key_quota(key_hash, 1000)
    assert ok is True

    # 记录用量
    assert record_api_key_usage(key_hash, 99000) is True

    # 刚好不超限（99000 + 1000 = 100000 <= 100000）
    ok, msg = check_api_key_quota(key_hash, 1000)
    assert ok is True

    # 超出额度
    ok, msg = check_api_key_quota(key_hash, 1001)
    assert ok is False
    assert "额度不足" in msg


def test_quota_nonexistent_key():
    """不存在的 key 哈希"""
    _reset_state()
    ok, msg = check_api_key_quota("nonexistent-hash", 100)
    assert ok is False
    assert record_api_key_usage("nonexistent-hash", 100) is False


# ---------------------------------------------------------------------------
# 运行入口
# ---------------------------------------------------------------------------

def main():
    tests = [
        ("权限矩阵", test_permission_matrix),
        ("工具访问-角色", test_tool_access_role),
        ("工具访问-白名单", test_tool_access_whitelist),
        ("API Key 生命周期", test_api_key_lifecycle),
        ("API Key 默认额度", test_api_key_role_quota_defaults),
        ("验证-缺少Key", test_verify_request_missing_key),
        ("验证-无效Key", test_verify_request_invalid_key),
        ("验证-有效Key", test_verify_request_valid_key),
        ("验证-信任IP", test_verify_request_trusted_ip),
        ("额度检查与记录", test_quota_check_and_record),
        ("额度-不存在Key", test_quota_nonexistent_key),
    ]

    print("=== 权限认证模块测试 ===\n")
    passed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  ✓ {name}")
            passed += 1
        except AssertionError as e:
            print(f"  ✗ {name}: {e}")
        except Exception as e:
            print(f"  ✗ {name}: 异常 {type(e).__name__}: {e}")

    # 清理测试产生的全局状态
    _reset_state()

    print(f"\n{'✅' if passed == len(tests) else '⚠'} 权限认证测试: {passed}/{len(tests)} 通过")
    return passed == len(tests)


if __name__ == "__main__":
    import sys
    sys.exit(0 if main() else 1)
