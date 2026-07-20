"""
auth.py 覆盖缺口测试
=====================

目标：覆盖权限校验、API Key 生命周期、配额与信任域等高风险路径。
这些路径在生产代码中完全无单测覆盖，且涉及安全敏感行为。

说明：
  - auth 模块在 import 时会从 data/api_keys.json 加载已有 Key，
    并在没有 AUTH_API_KEY_PEPPER 时发出警告（不强制）。
  - 每个用例创建带唯一前缀的 Key，结束后显式撤销，避免污染仓库根目录数据。
  - 所有测试独立运行，不依赖外部网络、文件系统（除 data/ 目录）。
"""

import time
import os
import sys
import json
import hashlib
import tempfile

# 与项目其他测试一致：把 local-core 加入 sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import auth  # noqa: E402
from auth import UserRole  # noqa: E402


# ---------------------------------------------------------------------------
# 工具：唯一命名 + 清理
# ---------------------------------------------------------------------------

_TEST_PREFIX = f"unittest-auth-{int(time.time())}-"
_created_key_ids: list = []  # 记录需要清理的 key_id


def _make_raw_key(role: UserRole, suffix: str = "") -> tuple:
    """创建测试用 Key，返回 (raw_key, key_id)。会自动登记清理。"""
    name = f"{_TEST_PREFIX}{role.value}{suffix}"
    raw, key_id = auth.create_api_key(name, role)
    _created_key_ids.append(key_id)
    return raw, key_id


def _cleanup():
    for kid in list(_created_key_ids):
        try:
            auth.revoke_api_key(kid)
        except Exception:
            pass
    _created_key_ids.clear()


# ---------------------------------------------------------------------------
# 1. API Key 生命周期：哈希入库、明文永不返回、撤销
# ---------------------------------------------------------------------------

def test_create_and_verify_roundtrip():
    raw, kid = _make_raw_key(UserRole.FAMILY)
    # 明文只创建时返回一次
    assert raw and len(raw) >= 16, "raw key 长度异常"

    # 用明文可成功校验
    ok, role, err, obj = auth.verify_request(raw, "10.0.0.1")
    assert ok is True, f"verify_request 失败: {err}"
    assert role == UserRole.FAMILY
    assert err is None
    assert obj is not None
    assert obj.key_id == kid
    assert obj.role == UserRole.FAMILY
    print("  ✓ 创建/校验往返一致")


def test_raw_key_never_appears_in_persistence():
    raw, _kid = _make_raw_key(UserRole.FAMILY)
    keys_file = auth._keys_file()
    assert os.path.exists(keys_file), "持久化文件应存在"
    with open(keys_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    # 整个文件不应出现明文 Key 片段
    for stored in data.get("keys", []):
        assert raw not in json.dumps(stored), "明文 Key 出现在了持久化文件中！"
    # 仅存储 hash（64 位 hex）
    for stored in data.get("keys", []):
        assert len(stored["key_hash"]) == 64
        assert all(c in "0123456789abcdef" for c in stored["key_hash"])
    print("  ✓ 持久化只存哈希，明文不落盘")


def test_revoke_removes_key():
    raw, kid = _make_raw_key(UserRole.GUEST)
    # 撤销前能通过
    ok, _, _, _ = auth.verify_request(raw, "10.0.0.2")
    assert ok is True

    # 撤销
    assert auth.revoke_api_key(kid) is True
    # 撤销后立刻失败
    ok2, role2, err2, _ = auth.verify_request(raw, "10.0.0.2")
    assert ok2 is False
    assert role2 == UserRole.GUEST  # 失败时仍为 GUEST（保守）
    assert "无效" in err2
    # 重复撤销返回 False
    assert auth.revoke_api_key(kid) is False
    # 撤销后从 _created_key_ids 摘除
    if kid in _created_key_ids:
        _created_key_ids.remove(kid)
    print("  ✓ 撤销后立即失效，不可重复撤销")


# ---------------------------------------------------------------------------
# 2. 权限矩阵与工具白名单
# ---------------------------------------------------------------------------

def test_role_permission_matrix():
    """角色权限矩阵应严格遵循 ROLE_PERMISSIONS。"""
    # OWNER 全权
    assert auth.check_permission(UserRole.OWNER, "admin_users") is True
    assert auth.check_permission(UserRole.OWNER, "admin_config") is True
    assert auth.check_permission(UserRole.OWNER, "chat") is True

    # FAMILY 不能管用户/系统配置
    assert auth.check_permission(UserRole.FAMILY, "admin_users") is False
    assert auth.check_permission(UserRole.FAMILY, "admin_config") is False
    # FAMILY 仍可用家庭场景下的常规能力
    assert auth.check_permission(UserRole.FAMILY, "device_control") is True
    assert auth.check_permission(UserRole.FAMILY, "email_send") is True

    # GUEST 仅 chat / note_read / system_info / notify
    for perm in ("chat", "note_read", "system_info", "notify"):
        assert auth.check_permission(UserRole.GUEST, perm) is True, f"GUEST 缺少 {perm}"
    for perm in ("admin_users", "admin_config", "device_control", "ha_control",
                 "browser", "email_send", "automation_rules"):
        assert auth.check_permission(UserRole.GUEST, perm) is False, f"GUEST 不应有 {perm}"
    print("  ✓ 角色权限矩阵与文档一致")


def test_unknown_role_returns_empty_permission():
    """不存在的权限名：查表不命中。"""
    # 不存在的权限：对所有角色都应返回 False
    for r in (UserRole.OWNER, UserRole.FAMILY, UserRole.GUEST):
        assert auth.check_permission(r, "not_a_real_permission") is False
    print("  ✓ 未知权限一律拒绝")


def test_tool_access_role_enforcement():
    """工具级访问控制遵循权限矩阵。"""
    # GUEST 不能控设备
    assert auth.check_tool_access(UserRole.GUEST, "control_pc") is False
    assert auth.check_tool_access(UserRole.GUEST, "read_webpage") is False

    # OWNER 默认放行
    assert auth.check_tool_access(UserRole.OWNER, "control_pc") is True
    assert auth.check_tool_access(UserRole.OWNER, "send_email") is True
    print("  ✓ 工具级访问受角色约束")


def test_tool_access_allowed_tools_whitelist_overrides_role():
    """
    即便角色是 OWNER/FAMILY，只要 Key 指定了 allowed_tools 白名单，
    未列入白名单的工具必须被拒绝。
    """
    # 创建一个限定白名单的 OWNER Key（仅 chat）
    name = f"{_TEST_PREFIX}whitelist"
    raw, kid = auth.create_api_key(name, UserRole.OWNER, allowed_tools=["chat", "get_time"])
    _created_key_ids.append(kid)

    # 角色是 OWNER，但 chat/get_time 允许，控制 PC 必须拒绝
    assert auth.check_tool_access(UserRole.OWNER, "control_pc", allowed_tools=["chat", "get_time"]) is False
    assert auth.check_tool_access(UserRole.OWNER, "send_email", allowed_tools=["chat", "get_time"]) is False
    # 白名单内的工具
    assert auth.check_tool_access(UserRole.OWNER, "get_time", allowed_tools=["chat", "get_time"]) is True
    print("  ✓ allowed_tools 白名单在角色之上额外限制")


# ---------------------------------------------------------------------------
# 3. 验证入口：缺失/错误/信任域
# ---------------------------------------------------------------------------

def test_verify_missing_key_for_unknown_ip():
    ok, role, err, obj = auth.verify_request(None, "203.0.113.5")
    assert ok is False
    assert role == UserRole.GUEST
    assert "缺少" in err
    assert obj is None
    print("  ✓ 缺 Key 且非信任 IP：拒绝")


def test_verify_invalid_key_returns_guest():
    ok, role, err, obj = auth.verify_request("obviously-not-a-real-key-xxxxxx", "203.0.113.5")
    assert ok is False
    assert role == UserRole.GUEST
    assert "无效" in err
    print("  ✓ 无效 Key：拒绝并降级为 GUEST")


def test_trusted_ip_bypasses_auth():
    """信任 IP 无需 API Key 直接放行，并获得配置的角色。"""
    test_ip = f"198.51.100.{int(time.time()) % 200 + 10}"
    auth.add_trusted_ip(test_ip, UserRole.FAMILY)
    try:
        ok, role, err, obj = auth.verify_request(None, test_ip)
        assert ok is True
        assert role == UserRole.FAMILY
        assert err is None
        # 信任域不返回 api_key 对象
        assert obj is None
    finally:
        auth.remove_trusted_ip(test_ip)
    print("  ✓ 信任 IP 免认证放行")


# ---------------------------------------------------------------------------
# 4. 配额
# ---------------------------------------------------------------------------

def test_quota_enforcement():
    """配额耗尽时拒绝请求。"""
    name = f"{_TEST_PREFIX}quota"
    # 创建一个限 50 的 family key
    raw, kid = auth.create_api_key(name, UserRole.FAMILY)
    _created_key_ids.append(kid)
    # 找到刚创建的 ApiKey，把 quota_limit 改成 50
    obj = next(o for o in auth._api_keys.values() if o.key_id == kid)
    obj.quota_limit = 50

    # 50 个 token 允许
    ok, msg = auth.check_api_key_quota(obj.key_hash, tokens_needed=40)
    assert ok is True, msg
    # 累计到 40
    auth.record_api_key_usage(obj.key_hash, 40)

    # 再要 20 个 → 40 + 20 = 60 > 50，拒绝
    ok, msg = auth.check_api_key_quota(obj.key_hash, tokens_needed=20)
    assert ok is False
    assert "额度不足" in msg
    # 5 个仍然允许（40 + 5 = 45 <= 50）
    ok, msg = auth.check_api_key_quota(obj.key_hash, tokens_needed=5)
    assert ok is True, msg
    print("  ✓ 配额正确累计/拒绝")


def test_quota_check_unknown_key():
    ok, msg = auth.check_api_key_quota("nonexistent_hash_value_xxx", tokens_needed=1)
    assert ok is False
    assert "无效" in msg
    print("  ✓ 未知 key 哈希拒绝")


# ---------------------------------------------------------------------------
# 5. list_api_keys 元数据正确性
# ---------------------------------------------------------------------------

def test_list_keys_does_not_leak_secret():
    raw, kid = _make_raw_key(UserRole.FAMILY)
    items = auth.list_api_keys()
    target = next(i for i in items if i["id"] == kid)
    # 列表里不能包含 raw key 或 key_hash
    blob = json.dumps(target, ensure_ascii=False)
    assert raw not in blob
    assert "key_hash" not in target
    # 必须包含元信息
    for k in ("id", "name", "role", "created_at", "last_used", "allowed_tools", "quota_used", "quota_limit"):
        assert k in target, f"缺少字段 {k}"
    print("  ✓ 列表仅返回元数据，不泄露密钥")


# ---------------------------------------------------------------------------
# 6. 持久化：list_api_keys → 重启加载也能找到
# ---------------------------------------------------------------------------

def test_persistence_roundtrip():
    """
    写入磁盘 → 清空内存 → _load_keys 重新载入，应能找到相同 key_id。
    """
    raw, kid = _make_raw_key(UserRole.GUEST)
    # 清空内存中的 _api_keys（保留磁盘）
    saved = dict(auth._api_keys)
    try:
        auth._api_keys.clear()
        # 重新加载
        auth._load_keys()
        assert kid in {k.key_id for k in auth._api_keys.values()}, "持久化后应能找到该 key"
        # 用 raw 校验也应通过
        ok, role, _, _ = auth.verify_request(raw, "10.0.0.99")
        assert ok is True
        assert role == UserRole.GUEST
    finally:
        # 恢复内存（不污染磁盘）
        auth._api_keys.clear()
        auth._api_keys.update(saved)
    print("  ✓ 持久化/重载往返一致")


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

def main():
    print("=== auth.py 覆盖缺口测试 ===\n")
    tests = [
        test_create_and_verify_roundtrip,
        test_raw_key_never_appears_in_persistence,
        test_revoke_removes_key,
        test_role_permission_matrix,
        test_unknown_role_returns_empty_permission,
        test_tool_access_role_enforcement,
        test_tool_access_allowed_tools_whitelist_overrides_role,
        test_verify_missing_key_for_unknown_ip,
        test_verify_invalid_key_returns_guest,
        test_trusted_ip_bypasses_auth,
        test_quota_enforcement,
        test_quota_check_unknown_key,
        test_list_keys_does_not_leak_secret,
        test_persistence_roundtrip,
    ]
    failed = 0
    try:
        for t in tests:
            try:
                t()
            except AssertionError as e:
                print(f"  ✗ {t.__name__}: {e}")
                failed += 1
            except Exception as e:
                print(f"  ✗ {t.__name__} 异常: {type(e).__name__}: {e}")
                failed += 1
    finally:
        _cleanup()
    if failed:
        print(f"\n❌ {failed} 个用例失败")
        sys.exit(1)
    print(f"\n✅ 全部 {len(tests)} 个 auth 用例通过")


if __name__ == "__main__":
    main()
