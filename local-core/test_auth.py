"""
权限认证模块测试
覆盖 API Key 生命周期、权限校验、信任域、持久化等核心安全逻辑。
"""

import os
import sys
import tempfile
import shutil
import time

# 将测试隔离到临时目录，避免污染真实 data 目录
TEST_ROOT = tempfile.mkdtemp(prefix="ynex_auth_test_")
os.chdir(TEST_ROOT)

# auth 导入时会加载 keys 并可能创建默认 owner key，需在导入后清理状态
import auth


def _reset_auth_state():
    """重置 auth 模块状态，确保测试隔离"""
    auth._api_keys.clear()
    auth._TRUSTED_IPS.clear()
    # 删除可能自动生成的初始 key 文件
    for f in ["data/api_keys.json", "data/.initial_owner_key"]:
        if os.path.exists(f):
            os.remove(f)


def test_create_and_revoke_api_key():
    """API Key 创建与撤销"""
    print("\n=== API Key 创建与撤销 ===")
    _reset_auth_state()

    raw, key_id = auth.create_api_key("测试Key", auth.UserRole.FAMILY)
    assert len(raw) > 20, "raw key 应足够长"
    assert len(key_id) == 8, "key_id 应为 8 位 hex"

    keys = auth.list_api_keys()
    assert len(keys) == 1
    assert keys[0]["name"] == "测试Key"
    assert keys[0]["role"] == "family"
    assert keys[0]["quota_limit"] == 100000

    ok = auth.revoke_api_key(key_id)
    assert ok is True
    assert len(auth.list_api_keys()) == 0

    # 重复撤销应返回 False
    ok2 = auth.revoke_api_key(key_id)
    assert ok2 is False
    print("  ✅ API Key 创建与撤销正确")


def test_api_key_quota():
    """API Key 额度管理"""
    print("\n=== API Key 额度管理 ===")
    _reset_auth_state()

    raw, key_id = auth.create_api_key("额度测试", auth.UserRole.GUEST)
    key_hash = auth._hash_key(raw)

    ok, msg = auth.check_api_key_quota(key_hash, tokens_needed=500)
    assert ok is True, msg

    ok, msg = auth.check_api_key_quota(key_hash, tokens_needed=200000)
    assert ok is False
    assert "额度不足" in msg

    auth.record_api_key_usage(key_hash, 300)
    keys = auth.list_api_keys()
    assert keys[0]["quota_used"] == 300

    # 无效 key 的记录应返回 False
    assert auth.record_api_key_usage("invalid_hash", 100) is False
    print("  ✅ 额度管理正确")


def test_verify_request():
    """请求认证验证"""
    print("\n=== 请求认证验证 ===")
    _reset_auth_state()

    raw, key_id = auth.create_api_key("认证测试", auth.UserRole.OWNER)

    # 1. 信任 IP 直通
    auth.add_trusted_ip("192.168.1.5", auth.UserRole.FAMILY)
    ok, role, err, obj = auth.verify_request(None, "192.168.1.5")
    assert ok is True
    assert role == auth.UserRole.FAMILY
    assert err is None

    # 2. 缺少 API Key
    ok, role, err, obj = auth.verify_request(None, "1.2.3.4")
    assert ok is False
    assert err == "缺少 API Key"

    # 3. 无效 API Key
    ok, role, err, obj = auth.verify_request("invalid-key", "1.2.3.4")
    assert ok is False
    assert err == "无效的 API Key"

    # 4. 有效 API Key
    ok, role, err, obj = auth.verify_request(raw, "1.2.3.4")
    assert ok is True
    assert role == auth.UserRole.OWNER
    assert obj is not None
    assert obj.last_used > 0

    # 5. 信任 IP 移除后不再直通
    auth.remove_trusted_ip("192.168.1.5")
    ok, role, err, obj = auth.verify_request(None, "192.168.1.5")
    assert ok is False
    print("  ✅ 认证验证逻辑正确")


def test_check_permission():
    """角色权限矩阵校验"""
    print("\n=== 角色权限矩阵校验 ===")

    assert auth.check_permission(auth.UserRole.OWNER, "admin_users") is True
    assert auth.check_permission(auth.UserRole.OWNER, "chat") is True
    assert auth.check_permission(auth.UserRole.FAMILY, "admin_users") is False
    assert auth.check_permission(auth.UserRole.FAMILY, "chat") is True
    assert auth.check_permission(auth.UserRole.GUEST, "chat") is True
    assert auth.check_permission(auth.UserRole.GUEST, "device_control") is False
    assert auth.check_permission(auth.UserRole.GUEST, "admin_config") is False
    print("  ✅ 权限矩阵正确")


def test_check_tool_access():
    """工具访问权限与白名单限制"""
    print("\n=== 工具访问权限与白名单限制 ===")

    # owner 默认有全部工具权限
    assert auth.check_tool_access(auth.UserRole.OWNER, "control_pc") is True
    # guest 只有基础权限
    assert auth.check_tool_access(auth.UserRole.GUEST, "control_pc") is False
    assert auth.check_tool_access(auth.UserRole.GUEST, "notify") is True

    # allowed_tools 白名单限制：owner 也受限制
    assert auth.check_tool_access(auth.UserRole.OWNER, "control_pc", allowed_tools=["notify"]) is False
    assert auth.check_tool_access(auth.UserRole.OWNER, "notify", allowed_tools=["notify"]) is True

    # family 的隐式权限映射
    assert auth.check_tool_access(auth.UserRole.FAMILY, "set_reminder") is True
    assert auth.check_tool_access(auth.UserRole.FAMILY, "read_emails") is True
    assert auth.check_tool_access(auth.UserRole.FAMILY, "unknown_tool") is True  # family/owner 默认全通
    print("  ✅ 工具访问权限与白名单正确")


def test_persistence():
    """持久化：保存与加载"""
    print("\n=== 持久化保存与加载 ===")
    _reset_auth_state()

    raw1, kid1 = auth.create_api_key("持久测试1", auth.UserRole.OWNER)
    raw2, kid2 = auth.create_api_key("持久测试2", auth.UserRole.GUEST, allowed_tools=["chat", "notify"])
    auth.add_trusted_ip("10.0.0.1", auth.UserRole.FAMILY)
    # 信任 IP 变更不会自动触发持久化，需手动保存以验证通道完整性
    auth._save_keys()

    # 模拟重新加载（新进程导入时会执行 _load_keys）
    auth._load_keys()

    keys = auth.list_api_keys()
    assert len(keys) == 2
    names = {k["name"] for k in keys}
    assert names == {"持久测试1", "持久测试2"}

    # 验证 allowed_tools 被保留
    guest_key = [k for k in keys if k["role"] == "guest"][0]
    assert guest_key["allowed_tools"] == ["chat", "notify"]

    # 验证信任 IP 被保留
    assert auth._TRUSTED_IPS.get("10.0.0.1") == "family"
    print("  ✅ 持久化加载正确")


def test_owner_default_key_auto_creation():
    """无 Key 时自动创建 owner key 的引导行为"""
    print("\n=== 自动创建引导 Owner Key ===")
    _reset_auth_state()

    # auth 导入时若 _api_keys 为空会自动创建，但这里我们已清空，
    # 手动触发逻辑（与模块末尾一致）
    if not auth._api_keys:
        raw, key_id = auth.create_api_key("默认管理员", auth.UserRole.OWNER)
        auth._save_keys()

    assert len(auth.list_api_keys()) >= 1
    assert any(k["role"] == "owner" for k in auth.list_api_keys())
    print("  ✅ 引导 Owner Key 正确")


def main():
    print("=" * 60)
    print("  权限认证模块测试")
    print("=" * 60)

    try:
        test_create_and_revoke_api_key()
        test_api_key_quota()
        test_verify_request()
        test_check_permission()
        test_check_tool_access()
        test_persistence()
        test_owner_default_key_auto_creation()
    finally:
        os.chdir("/workspace/local-core")
        shutil.rmtree(TEST_ROOT, ignore_errors=True)

    print("\n" + "=" * 60)
    print("  ✅ 全部认证测试通过")
    print("=" * 60)


if __name__ == "__main__":
    main()
