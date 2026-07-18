"""
权限认证模块测试
覆盖 API Key 生命周期、权限矩阵、工具访问控制、额度管理。
"""

import contextlib
import os
import shutil
import tempfile
import time

# 固定盐，避免测试受环境变量影响并消除 RuntimeWarning
os.environ.setdefault("AUTH_API_KEY_PEPPER", "test-pepper-for-deterministic-hashing")

import auth
from auth import (
    _TRUSTED_IPS,
    ROLE_PERMISSIONS,
    UserRole,
    _api_keys,
    _hash_key,
    _load_keys,
    _save_keys,
    add_trusted_ip,
    check_api_key_quota,
    check_permission,
    check_tool_access,
    create_api_key,
    list_api_keys,
    record_api_key_usage,
    revoke_api_key,
    verify_request,
)


def _snapshot_state():
    return dict(_api_keys), dict(_TRUSTED_IPS)


def _restore_state(original_keys, original_trusted):
    _api_keys.clear()
    _api_keys.update(original_keys)
    _TRUSTED_IPS.clear()
    _TRUSTED_IPS.update(original_trusted)


def test_hash_key_deterministic():
    print("1. API Key 哈希确定性...")
    h1 = _hash_key("same-key")
    h2 = _hash_key("same-key")
    h3 = _hash_key("different-key")
    assert h1 == h2
    assert h1 != h3
    print("  ✓ 哈希确定性正确")


def test_create_and_list_api_keys(tmpdir):
    print("2. 创建与列出 API Key...")
    auth._keys_file = lambda: os.path.join(tmpdir, "api_keys.json")

    initial_count = len(list_api_keys())
    raw, key_id = create_api_key("测试Key", UserRole.FAMILY, allowed_tools=["chat"])
    assert len(key_id) == 8
    assert raw not in _api_keys, "应只存储哈希后的 Key"

    keys = list_api_keys()
    assert len(keys) == initial_count + 1
    test_key = next(k for k in keys if k["name"] == "测试Key")
    assert test_key["role"] == "family"
    assert test_key["allowed_tools"] == ["chat"]
    print("  ✓ 创建与列出正确")


def test_verify_request(tmpdir):
    print("3. 请求认证...")
    auth._keys_file = lambda: os.path.join(tmpdir, "api_keys.json")

    # 信任 IP 直通
    add_trusted_ip("192.168.1.50", UserRole.FAMILY)
    ok, role, err, _ = verify_request(None, "192.168.1.50")
    assert ok and role == UserRole.FAMILY and err is None

    # 缺少 Key
    ok, role, err, _ = verify_request(None, "10.0.0.1")
    assert not ok and err == "缺少 API Key" and role == UserRole.GUEST

    # 错误 Key
    ok, role, err, _ = verify_request("wrong-key", "10.0.0.1")
    assert not ok and err == "无效的 API Key"

    # 正确 Key
    raw, _ = create_api_key("验证Key", UserRole.OWNER)
    ok, role, err, api_key_obj = verify_request(raw, "10.0.0.1")
    assert ok and role == UserRole.OWNER and err is None
    assert api_key_obj.last_used > 0
    print("  ✓ 请求认证正确")


def test_permission_matrix():
    print("4. 权限矩阵...")
    owner_perms = ROLE_PERMISSIONS[UserRole.OWNER]
    family_perms = ROLE_PERMISSIONS[UserRole.FAMILY]
    guest_perms = ROLE_PERMISSIONS[UserRole.GUEST]

    assert "admin_users" in owner_perms
    assert "admin_users" not in family_perms
    assert "chat" in guest_perms
    assert "device_control" not in guest_perms

    assert check_permission(UserRole.OWNER, "admin_config") is True
    assert check_permission(UserRole.FAMILY, "admin_config") is False
    assert check_permission(UserRole.GUEST, "device_control") is False
    print("  ✓ 权限矩阵正确")


def test_tool_access():
    print("5. 工具访问控制...")
    # owner 默认可访问任意工具
    assert check_tool_access(UserRole.OWNER, "control_pc") is True

    # 但受 allowed_tools 白名单限制
    assert check_tool_access(UserRole.OWNER, "control_pc", allowed_tools=["chat"]) is False
    assert check_tool_access(UserRole.OWNER, "chat", allowed_tools=["chat"]) is True

    # guest 只能访问显式授权工具
    assert check_tool_access(UserRole.GUEST, "chat") is True
    assert check_tool_access(UserRole.GUEST, "control_pc") is False

    # family 可访问映射内的工具
    assert check_tool_access(UserRole.FAMILY, "control_ha_device") is True
    print("  ✓ 工具访问控制正确")


def test_quota_management(tmpdir):
    print("6. 额度管理...")
    auth._keys_file = lambda: os.path.join(tmpdir, "api_keys.json")

    raw, key_id = create_api_key("额度Key", UserRole.FAMILY)
    key_hash = _hash_key(raw)

    ok, msg = check_api_key_quota(key_hash, tokens_needed=100)
    assert ok and msg == ""

    # 默认 family 额度 100000
    ok, msg = check_api_key_quota(key_hash, tokens_needed=100001)
    assert not ok and "额度不足" in msg

    assert record_api_key_usage(key_hash, 50) is True
    api_key = _api_keys[key_hash]
    assert api_key.quota_used == 50

    # 记录不存在的 Key
    assert record_api_key_usage("nonexistent-hash", 10) is False
    print("  ✓ 额度管理正确")


def test_revoke_api_key(tmpdir):
    print("7. 撤销 API Key...")
    auth._keys_file = lambda: os.path.join(tmpdir, "api_keys.json")

    initial_count = len(list_api_keys())
    raw, key_id = create_api_key("待撤销", UserRole.GUEST)
    assert len(list_api_keys()) == initial_count + 1

    assert revoke_api_key(key_id) is True
    assert len(list_api_keys()) == initial_count
    assert revoke_api_key("not-exist") is False

    # 撤销后原 Key 无法认证
    ok, _, err, _ = verify_request(raw, "10.0.0.1")
    assert not ok and err == "无效的 API Key"
    print("  ✓ 撤销 API Key 正确")


def test_persistence_roundtrip(tmpdir):
    print("8. 持久化读写...")
    auth._keys_file = lambda: os.path.join(tmpdir, "api_keys.json")

    raw, key_id = create_api_key("持久化", UserRole.OWNER)
    last_used_ts = time.time()
    _api_keys[_hash_key(raw)].last_used = last_used_ts
    _save_keys()

    # 模拟新进程：清空后重新加载
    original_keys = dict(_api_keys)
    _api_keys.clear()
    _load_keys()

    loaded = _api_keys[_hash_key(raw)]
    assert loaded.key_id == key_id
    assert loaded.role == UserRole.OWNER
    assert abs(loaded.last_used - last_used_ts) < 1

    # 恢复原始状态
    _api_keys.clear()
    _api_keys.update(original_keys)
    print("  ✓ 持久化读写正确")


def main():
    print("=== 权限认证模块测试 ===\n")

    original_keys, original_trusted = _snapshot_state()
    tmpdir = tempfile.mkdtemp(prefix="ynex_auth_test_")
    try:
        test_hash_key_deterministic()
        test_create_and_list_api_keys(tmpdir)
        test_verify_request(tmpdir)
        test_permission_matrix()
        test_tool_access()
        test_quota_management(tmpdir)
        test_revoke_api_key(tmpdir)
        test_persistence_roundtrip(tmpdir)
    finally:
        _restore_state(original_keys, original_trusted)
        shutil.rmtree(tmpdir, ignore_errors=True)
        # 清理模块初始化可能生成的引导文件
        for cleanup_path in ("data/.initial_owner_key", "data/api_keys.json"):
            with contextlib.suppress(FileNotFoundError):
                os.remove(cleanup_path)

    print("\n=== 权限认证测试全部通过 ===")


if __name__ == "__main__":
    main()
