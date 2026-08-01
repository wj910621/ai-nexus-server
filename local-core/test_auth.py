"""
权限认证模块测试
覆盖：
- UserRole 权限矩阵（owner / family / guest）
- check_permission / check_tool_access（角色到工具映射 + allowed_tools 白名单限制）
- API Key 生命周期（create / list / revoke / verify / 配额检查与用量记录）
- 信任 IP（add_trusted_ip / remove_trusted_ip / verify_request 直通）
- verify_request 的各种错误分支（无 Key、无效 Key、有效 Key、信任 IP）
"""

import os
import sys
import time

# 在导入 auth 前切到临时目录，避免污染正式 data/
import tempfile
import shutil

_TMP = tempfile.mkdtemp(prefix="ynex-auth-test-")
os.chdir(_TMP)

import auth
from auth import (
    UserRole,
    ROLE_PERMISSIONS,
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
)


def _cleanup():
    try:
        shutil.rmtree(_TMP, ignore_errors=True)
    except Exception:
        pass


def _section(title):
    print(f"\n--- {title} ---")


def test_role_permissions_matrix():
    _section("权限矩阵")
    # owner 拥有所有权限
    owner_perms = ROLE_PERMISSIONS[UserRole.OWNER]
    for perm in {"admin_users", "admin_config", "wake_remote", "chat", "device_control"}:
        assert perm in owner_perms, f"owner 应包含 {perm}"

    # family 缺少 admin_*
    family_perms = ROLE_PERMISSIONS[UserRole.FAMILY]
    assert "admin_users" not in family_perms
    assert "admin_config" not in family_perms
    assert "admin_skills" not in family_perms
    assert "chat" in family_perms

    # guest 仅基础能力
    guest_perms = ROLE_PERMISSIONS[UserRole.GUEST]
    for forbidden in {"device_control", "admin_users", "browser", "email_send", "automation_rules"}:
        assert forbidden not in guest_perms, f"guest 不应拥有 {forbidden}"
    for allowed in {"chat", "note_read", "system_info", "notify"}:
        assert allowed in guest_perms, f"guest 应拥有 {allowed}"

    # check_permission 正确性
    assert check_permission(UserRole.OWNER, "admin_users")
    assert not check_permission(UserRole.GUEST, "admin_users")
    assert check_permission(UserRole.GUEST, "chat")
    assert not check_permission(UserRole.FAMILY, "nonexistent_perm")
    print("  ✓ 三级角色权限矩阵与 check_permission 行为正确")


def test_check_tool_access():
    _section("工具访问控制")
    # 从权限映射的工具
    assert check_tool_access(UserRole.OWNER, "control_pc")
    assert check_tool_access(UserRole.FAMILY, "send_email")
    assert not check_tool_access(UserRole.GUEST, "send_email")

    # guest 只有少数工具可用
    assert not check_tool_access(UserRole.GUEST, "control_ha_device")
    assert not check_tool_access(UserRole.GUEST, "read_webpage")

    # 白名单 allowed_tools 覆盖 owner/family
    assert not check_tool_access(UserRole.OWNER, "control_pc", allowed_tools=["read_emails"])
    assert check_tool_access(UserRole.OWNER, "read_emails", allowed_tools=["read_emails"])

    # owner/family 即使没有权限映射也默认放行其他工具（白名单未设置时）
    assert check_tool_access(UserRole.OWNER, "custom_tool_xyz_unknown_perm")
    assert check_tool_access(UserRole.FAMILY, "custom_tool_xyz_unknown_perm")

    # guest 不会因默认放行绕过权限
    assert not check_tool_access(UserRole.GUEST, "custom_tool_xyz_unknown_perm")
    print("  ✓ 工具访问：角色权限、白名单、owner/family 默认放行均正确")


def test_api_key_lifecycle():
    _section("API Key 生命周期")
    before = list_api_keys()
    n = len(before)

    raw, key_id = create_api_key("测试Key", UserRole.FAMILY)
    assert raw, "应返回 raw key"
    assert len(raw) >= 20
    assert len(key_id) == 8

    # 列出应多一个
    keys = list_api_keys()
    assert len(keys) == n + 1
    assert any(k["id"] == key_id for k in keys)
    assert keys[-1]["role"] == "family"

    # 配额初始检查通过
    ok, msg = check_api_key_quota(auth._hash_key(raw), tokens_needed=1000)
    assert ok, f"新 Key 应额度充足: {msg}"

    # 记录用量后 quota_used 增加
    record_api_key_usage(auth._hash_key(raw), tokens=500)
    keys2 = list_api_keys()
    target = next(k for k in keys2 if k["id"] == key_id)
    assert target["quota_used"] >= 500

    # 撤销
    assert revoke_api_key(key_id), "撤销应成功"
    assert not revoke_api_key(key_id), "重复撤销应返回 False"
    assert len(list_api_keys()) == n, "撤销后列表恢复"

    # 撤销后 verify 失败
    ok2, role2, err2, _ = verify_request(raw, "127.0.0.1")
    assert not ok2 and err2 == "无效的 API Key"
    assert role2 == UserRole.GUEST
    print("  ✓ 创建/列出/配额/用量/撤销/撤销后失效 全流程正确")


def test_owner_quota_larger():
    _section("Owner 配额更高")
    raw_fam, kid_fam = create_api_key("F", UserRole.FAMILY)
    raw_own, kid_own = create_api_key("O", UserRole.OWNER)
    fam_hash = auth._hash_key(raw_fam)
    own_hash = auth._hash_key(raw_own)
    # family 默认 100000，owner 默认 1000000
    fam_used = next(k for k in list_api_keys() if k["id"] == kid_fam)["quota_limit"]
    own_used = next(k for k in list_api_keys() if k["id"] == kid_own)["quota_limit"]
    assert fam_used == 100000
    assert own_used == 1000000
    revoke_api_key(kid_fam)
    revoke_api_key(kid_own)
    print("  ✓ owner 配额 100w、family 配额 10w")


def test_verify_request_errors_and_success():
    _section("verify_request 分支")
    # 1) 无 api_key
    ok, role, err, _ = verify_request(None, "127.0.0.1")
    assert not ok and err == "缺少 API Key"
    assert role == UserRole.GUEST

    # 2) 无效 api_key
    ok, role, err, _ = verify_request("not-a-real-key", "127.0.0.1")
    assert not ok and err == "无效的 API Key"

    # 3) 有效 api_key
    raw, kid = create_api_key("VerifyCase", UserRole.FAMILY)
    ok, role, err, obj = verify_request(raw, "127.0.0.1")
    assert ok and role == UserRole.FAMILY and err is None
    assert obj is not None
    # last_used 应被更新
    assert obj.last_used > 0
    revoke_api_key(kid)

    # 4) 信任 IP 直通（不需 Key）
    add_trusted_ip("192.168.1.10", UserRole.OWNER)
    ok, role, err, obj = verify_request(None, "192.168.1.10")
    assert ok and role == UserRole.OWNER and err is None
    assert obj is None, "信任 IP 直通时无 ApiKey 对象"

    # 移除信任 IP 后恢复严格校验
    remove_trusted_ip("192.168.1.10")
    ok, role, err, _ = verify_request(None, "192.168.1.10")
    assert not ok and err == "缺少 API Key"

    print("  ✓ verify_request 四个分支（无 Key、无效、有效、信任 IP）均正确")


def test_quota_exhausted():
    _section("配额耗尽检查")
    raw, kid = create_api_key("QuotaCase", UserRole.FAMILY)
    key_hash = auth._hash_key(raw)

    # 用尽额度
    record_api_key_usage(key_hash, tokens=100000)
    ok, msg = check_api_key_quota(key_hash, tokens_needed=1)
    assert not ok, f"额度耗尽时应拒绝: {msg}"

    # 稍小请求仍不足
    ok2, _ = check_api_key_quota(key_hash, tokens_needed=100)
    assert not ok2

    # 无效 key 返回失败
    ok3, msg3 = check_api_key_quota("not-a-hash", tokens_needed=1)
    assert not ok3 and "无效" in msg3

    revoke_api_key(kid)
    print("  ✓ 配额耗尽与无效 Key 分支均正确")


def main():
    print("=== 权限认证模块测试 ===\n")
    try:
        test_role_permissions_matrix()
        test_check_tool_access()
        test_api_key_lifecycle()
        test_owner_quota_larger()
        test_verify_request_errors_and_success()
        test_quota_exhausted()
        print("\n✅ 所有认证测试通过")
    finally:
        _cleanup()


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    main()
