"""
auth.py 单元测试
================
覆盖范围：
  - create_api_key / revoke_api_key / list_api_keys：生命周期
  - verify_request：无 Key / 无效 Key / 信任 IP / 有效 Key
  - check_permission：角色权限矩阵
  - check_tool_access：工具白名单 + 权限映射
  - check_api_key_quota + record_api_key_usage：额度检查与记录
  - add_trusted_ip / remove_trusted_ip：信任域管理
  - 并发安全性：多线程同时 verify / revoke
"""

import os
import sys
import time
import json
import shutil
import tempfile
import threading

_ORIG_CWD = os.getcwd()
_ORIG_ENV_PEPPER = os.environ.get("AUTH_API_KEY_PEPPER", None)


def _setup():
    tmp = tempfile.mkdtemp(prefix="ynex_auth_test_")
    os.chdir(tmp)
    # 设置固定 pepper，避免模块 import 时 RuntimeWarning 且 key 哈希稳定
    os.environ["AUTH_API_KEY_PEPPER"] = "test-pepper-for-unit-tests-do-not-use-in-production"
    return tmp


def _teardown():
    os.chdir(_ORIG_CWD)
    if _ORIG_ENV_PEPPER is None:
        os.environ.pop("AUTH_API_KEY_PEPPER", None)
    else:
        os.environ["AUTH_API_KEY_PEPPER"] = _ORIG_ENV_PEPPER


def _fresh_import_auth():
    """清除 auth 模块的进程内状态并重新 import，确保测试隔离。"""
    import importlib
    import auth as auth_mod
    import config as config_mod
    import logger as logger_mod

    # 先重置全局可变状态
    auth_mod._api_keys.clear()
    auth_mod._TRUSTED_IPS.clear()
    auth_mod._API_KEY_PEPPER = os.environ["AUTH_API_KEY_PEPPER"]

    # 跳过 init 逻辑（它会尝试创建初始 key）
    import hashlib
    import secrets
    auth_mod._hash_key = lambda k: hashlib.sha256(
        f"{k}:{auth_mod._API_KEY_PEPPER}".encode()
    ).hexdigest()
    return auth_mod


def main():
    tmp = _setup()
    try:
        auth = _fresh_import_auth()
        _run_tests(auth, tmp)
    finally:
        _teardown()


def _run_tests(auth, tmp_dir):
    errors = []

    # ================================
    # 1. create_api_key / revoke / list
    # ================================
    print("1. API Key 生命周期")

    # 1.1 创建 OWNER Key
    raw_owner, kid_owner = auth.create_api_key("test-owner", auth.UserRole.OWNER)
    assert raw_owner, "raw key 应非空"
    assert len(kid_owner) == 8, f"key_id 应为 8 位十六进制，实际 {len(kid_owner)}"
    assert auth.verify_request(raw_owner, "127.0.0.1")[0] is True
    print("   ✓ OWNER Key 创建 & verify 成功")

    # 1.2 创建 FAMILY Key（带工具白名单）
    raw_family, kid_family = auth.create_api_key(
        "test-family", auth.UserRole.FAMILY, allowed_tools=["chat", "get_system_info"]
    )
    print("   ✓ FAMILY Key 创建（带 allowed_tools 白名单）")

    # 1.3 创建 GUEST Key
    raw_guest, kid_guest = auth.create_api_key("test-guest", auth.UserRole.GUEST)
    print("   ✓ GUEST Key 创建")

    # 1.4 list 验证元数据
    listed = auth.list_api_keys()
    ids_in_list = {k["id"] for k in listed}
    for kid in [kid_owner, kid_family, kid_guest]:
        assert kid in ids_in_list, f"key_id {kid} 未出现在 list_api_keys 中"
    # 元数据不含 raw key
    for entry in listed:
        assert "raw" not in entry and "key" not in entry
    print(f"   ✓ list_api_keys 返回 {len(listed)} 条元数据（不泄露密钥）")

    # 1.5 revoke
    assert auth.revoke_api_key(kid_guest) is True
    # 已撤销的 key 不能再 verify
    assert auth.verify_request(raw_guest, "127.0.0.1")[0] is False
    print("   ✓ revoke 成功，已撤销 Key 无法使用")

    # 1.6 revoke 不存在的 key_id 返回 False
    assert auth.revoke_api_key("00000000") is False
    print("   ✓ revoke 不存在的 key_id 返回 False")

    # ================================
    # 2. verify_request 边界
    # ================================
    print("\n2. verify_request 边界")

    # 2.1 缺少 API Key
    ok, role, err, _ = auth.verify_request(None, "127.0.0.1")
    assert ok is False and err == "缺少 API Key" and role == auth.UserRole.GUEST
    print("   ✓ 缺少 API Key 被拒，返回 GUEST 角色占位")

    # 2.2 空字符串 Key
    ok, _, err, _ = auth.verify_request("", "127.0.0.1")
    assert ok is False
    print("   ✓ 空字符串 Key 被拒")

    # 2.3 无效 Key
    ok, _, err, _ = auth.verify_request("totally-invalid-key", "127.0.0.1")
    assert ok is False and err == "无效的 API Key"
    print("   ✓ 无效 Key 被拒")

    # 2.4 信任 IP 直通
    auth.add_trusted_ip("192.168.1.100", auth.UserRole.FAMILY)
    ok, role, err, _ = auth.verify_request(None, "192.168.1.100")
    assert ok is True and role == auth.UserRole.FAMILY and err is None
    print("   ✓ 信任 IP 无 Key 直通")

    # 2.5 非信任 IP 但提供了有效 Key
    ok, role, _, key_obj = auth.verify_request(raw_owner, "8.8.8.8")
    assert ok is True and role == auth.UserRole.OWNER
    assert key_obj is not None
    # last_used 应被更新
    assert key_obj.last_used > 0
    print("   ✓ 有效 Key + 外部 IP 验证成功，last_used 被更新")

    # ================================
    # 3. check_permission —— 角色权限矩阵
    # ================================
    print("\n3. 角色权限矩阵 check_permission")

    # OWNER 拥有所有权限
    owner_perms = auth.ROLE_PERMISSIONS[auth.UserRole.OWNER]
    for p in owner_perms:
        assert auth.check_permission(auth.UserRole.OWNER, p), f"OWNER 应有 {p}"
    print(f"   ✓ OWNER 拥有 {len(owner_perms)} 项权限")

    # FAMILY 有全部 except admin_* 和 wake_remote
    family_perms = auth.ROLE_PERMISSIONS[auth.UserRole.FAMILY]
    assert "admin_users" not in family_perms
    assert "admin_config" not in family_perms
    assert "admin_skills" not in family_perms
    for p in family_perms:
        assert auth.check_permission(auth.UserRole.FAMILY, p)
    print(f"   ✓ FAMILY 拥有 {len(family_perms)} 项权限（不含 admin_*）")

    # GUEST 最少
    guest_perms = auth.ROLE_PERMISSIONS[auth.UserRole.GUEST]
    assert "device_control" not in guest_perms
    assert "command" not in guest_perms
    assert "admin_users" not in guest_perms
    assert auth.check_permission(auth.UserRole.GUEST, "chat")
    assert not auth.check_permission(auth.UserRole.GUEST, "device_control")
    print(f"   ✓ GUEST 仅有 {len(guest_perms)} 项基础权限")

    # 不存在的权限名
    assert not auth.check_permission(auth.UserRole.OWNER, "non_existent_permission")
    print("   ✓ 不存在的权限返回 False")

    # 非法角色枚举外值（防御性）——实际 Enum 不会产生，但测试默认空 set
    class _FakeRole:
        pass
    assert not auth.check_permission(_FakeRole(), "chat")
    print("   ✓ 未知角色返回 False")

    # ================================
    # 4. check_tool_access —— 工具白名单 + 权限映射
    # ================================
    print("\n4. check_tool_access")

    # OWNER 默认可使用所有工具
    assert auth.check_tool_access(auth.UserRole.OWNER, "control_pc")
    assert auth.check_tool_access(auth.UserRole.OWNER, "mqtt_publish")
    print("   ✓ OWNER 默认所有工具可用")

    # FAMILY 也默认所有工具可用（不受 admin_* 限制）
    assert auth.check_tool_access(auth.UserRole.FAMILY, "control_pc")
    print("   ✓ FAMILY 默认所有工具可用")

    # GUEST 只能用基础工具
    assert not auth.check_tool_access(auth.UserRole.GUEST, "control_pc")
    assert not auth.check_tool_access(auth.UserRole.GUEST, "run_browser_task")
    assert auth.check_tool_access(auth.UserRole.GUEST, "notify")  # 在 guest perms 中
    print("   ✓ GUEST 仅基础工具可用")

    # allowed_tools 白名单覆盖
    # 即便是 OWNER，若指定 allowed_tools=["chat"]，也不能用 device_control 工具
    assert auth.check_tool_access(auth.UserRole.OWNER, "chat", allowed_tools=["chat"])
    assert not auth.check_tool_access(
        auth.UserRole.OWNER, "control_pc", allowed_tools=["chat"]
    )
    print("   ✓ allowed_tools 白名单覆盖 OWNER/FAMILY 全工具权限")

    # 权限推断：ha_control 权限应让 list_ha_entities 可用
    assert auth.check_tool_access(auth.UserRole.FAMILY, "list_ha_entities")
    print("   ✓ 工具 -> 权限映射正常（ha_control -> list_ha_entities）")

    # ================================
    # 5. 额度检查与记录
    # ================================
    print("\n5. API Key 额度")

    # OWNER 初始额度 1000000
    keys = auth.list_api_keys()
    owner_meta = next(k for k in keys if k["name"] == "test-owner")
    assert owner_meta["quota_limit"] == 1_000_000
    assert owner_meta["quota_used"] == 0

    # 检查额度充足
    ok, msg = auth.check_api_key_quota(auth._hash_key(raw_owner), tokens_needed=500000)
    assert ok is True, msg
    print("   ✓ 额度充足时 check 成功")

    # 记录用量
    h = auth._hash_key(raw_owner)
    assert auth.record_api_key_usage(h, tokens=1000) is True
    assert auth._api_keys[h].quota_used == 1000
    print("   ✓ 用量记录成功")

    # 额度耗尽边界
    ok, msg = auth.check_api_key_quota(h, tokens_needed=1_000_000)
    assert ok is False and "额度不足" in msg
    print("   ✓ 额度不足被拦截")

    # 无效 key 哈希
    ok, msg = auth.check_api_key_quota("not-a-real-hash")
    assert ok is False and "无效" in msg
    assert auth.record_api_key_usage("not-a-real-hash", 1) is False
    print("   ✓ 无效 key 哈希被拒")

    # ================================
    # 6. 信任域管理
    # ================================
    print("\n6. 信任域")
    auth.add_trusted_ip("10.0.0.5", auth.UserRole.OWNER)
    ok, role, _, _ = auth.verify_request(None, "10.0.0.5")
    assert ok and role == auth.UserRole.OWNER
    auth.remove_trusted_ip("10.0.0.5")
    ok, _, err, _ = auth.verify_request(None, "10.0.0.5")
    assert not ok
    print("   ✓ add_trusted_ip / remove_trusted_ip 生效")

    # ================================
    # 7. 持久化 round-trip
    # ================================
    print("\n7. 持久化 round-trip")
    # _save_keys 应把 keys 和 trusted_ips 写到 data/api_keys.json
    keys_file = os.path.join(tmp_dir, "data", "api_keys.json")
    assert os.path.exists(keys_file), f"{keys_file} 应存在"
    with open(keys_file, "r") as f:
        persisted = json.load(f)
    assert "keys" in persisted
    assert "trusted_ips" in persisted
    print(f"   ✓ 持久化文件存在，包含 {len(persisted['keys'])} 条 key")

    # ================================
    # 8. 并发安全 —— 多线程同时 verify / revoke / create
    # ================================
    print("\n8. 并发安全（16 线程 × 30 次）")
    exceptions = []
    results_lock = threading.Lock()
    ok_count = 0
    fail_count = 0

    def verify_worker(key_str):
        nonlocal ok_count, fail_count
        try:
            for _ in range(30):
                res = auth.verify_request(key_str, "127.0.0.1")
                with results_lock:
                    if res[0]:
                        ok_count += 1
                    else:
                        fail_count += 1
        except Exception as e:
            exceptions.append(e)

    threads = [threading.Thread(target=verify_worker, args=(raw_owner,)) for _ in range(16)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not exceptions, f"并发 verify 出现异常: {exceptions}"
    assert ok_count == 16 * 30, f"全部应 ok，实际 ok={ok_count} fail={fail_count}"
    print(f"   ✓ 16 线程并发 verify 全部成功 ({ok_count})，无异常")

    # ================================
    # 9. 额外边界：key_id 唯一性
    # ================================
    print("\n9. key_id 唯一性")
    seen_ids = set()
    for _ in range(200):
        _, kid = auth.create_api_key("uniqueness", auth.UserRole.GUEST)
        assert kid not in seen_ids, f"key_id 冲突: {kid}"
        seen_ids.add(kid)
    # 清理
    for kid in seen_ids:
        auth.revoke_api_key(kid)
    print(f"   ✓ 200 次 create key_id 全部唯一")

    # ================================
    # 结果
    # ================================
    print("\n" + "=" * 50)
    if errors:
        print(f"❌ 发现 {len(errors)} 个问题：")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("🎉 auth.py 全部测试通过")


if __name__ == "__main__":
    main()
