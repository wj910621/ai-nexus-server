"""
认证模块测试
测试API Key管理、权限校验、角色权限等功能
"""

import os
import time
import tempfile
import shutil
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
    _hash_key,
)


def setup_module():
    """测试前准备"""
    # 使用临时目录存储测试数据
    global original_cwd, test_dir
    original_cwd = os.getcwd()
    test_dir = tempfile.mkdtemp(prefix="ynex_auth_test_")
    os.chdir(test_dir)
    os.makedirs("data", exist_ok=True)


def teardown_module():
    """测试后清理"""
    global original_cwd, test_dir
    os.chdir(original_cwd)
    try:
        shutil.rmtree(test_dir)
    except Exception:
        pass


def test_user_roles():
    """测试用户角色定义"""
    print("\n=== 测试用户角色定义 ===")

    # 检查角色权限矩阵
    assert UserRole.OWNER in ROLE_PERMISSIONS
    assert UserRole.FAMILY in ROLE_PERMISSIONS
    assert UserRole.GUEST in ROLE_PERMISSIONS

    # OWNER 权限应包含所有权限
    owner_perms = ROLE_PERMISSIONS[UserRole.OWNER]
    assert "admin_users" in owner_perms
    assert "device_control" in owner_perms

    # FAMILY 权限应少于 OWNER
    family_perms = ROLE_PERMISSIONS[UserRole.FAMILY]
    assert "admin_users" not in family_perms
    assert "device_control" in family_perms

    # GUEST 权限应最少
    guest_perms = ROLE_PERMISSIONS[UserRole.GUEST]
    assert "chat" in guest_perms
    assert "device_control" not in guest_perms

    print("  ✓ 用户角色定义测试通过")


def test_create_api_key():
    """测试创建API Key"""
    print("\n=== 测试创建API Key ===")

    # 创建不同角色的Key
    raw_owner, key_id_owner = create_api_key("测试管理员", UserRole.OWNER)
    raw_family, key_id_family = create_api_key("测试家庭成员", UserRole.FAMILY)
    raw_guest, key_id_guest = create_api_key("测试访客", UserRole.GUEST)

    # 验证Key格式
    assert len(raw_owner) > 32
    assert len(key_id_owner) == 8
    assert len(raw_family) > 32
    assert len(key_id_family) == 8

    # Key应该是唯一的
    assert raw_owner != raw_family
    assert key_id_owner != key_id_family

    print(f"  创建的 Key ID: {key_id_owner}, {key_id_family}, {key_id_guest}")
    print("  ✓ 创建API Key测试通过")


def test_list_api_keys():
    """测试列出API Keys"""
    print("\n=== 测试列出API Keys ===")

    keys = list_api_keys()
    assert isinstance(keys, list)
    assert len(keys) >= 3  # 之前创建了3个

    # 检查返回的元数据
    for k in keys:
        assert "id" in k
        assert "name" in k
        assert "role" in k
        assert "created_at" in k
        assert "last_used" in k
        # 注意：不应包含密钥明文
        assert "key_hash" not in k or k.get("key_hash") is None

    print(f"  当前有 {len(keys)} 个 API Key")
    print("  ✓ 列出API Keys测试通过")


def test_verify_request():
    """测试请求验证"""
    print("\n=== 测试请求验证 ===")

    # 创建新的Key用于测试
    raw_key, key_id = create_api_key("验证测试", UserRole.FAMILY)

    # 验证有效Key
    ok, role, err, api_key_obj = verify_request(raw_key, "127.0.0.1")
    assert ok is True
    assert role == UserRole.FAMILY
    assert err is None
    assert api_key_obj is not None
    print(f"  有效 Key 验证通过: role={role.value}")

    # 验证无效Key
    ok, role, err, api_key_obj = verify_request("invalid_key_12345", "127.0.0.1")
    assert ok is False
    assert role == UserRole.GUEST
    assert err is not None
    print(f"  无效 Key 被拒绝: {err}")

    # 验证空Key
    ok, role, err, api_key_obj = verify_request(None, "127.0.0.1")
    assert ok is False
    assert err == "缺少 API Key"
    print("  空 Key 被拒绝")

    print("  ✓ 请求验证测试通过")


def test_check_permission():
    """测试权限检查"""
    print("\n=== 测试权限检查 ===")

    # OWNER 权限
    assert check_permission(UserRole.OWNER, "admin_users") is True
    assert check_permission(UserRole.OWNER, "device_control") is True

    # FAMILY 权限
    assert check_permission(UserRole.FAMILY, "admin_users") is False
    assert check_permission(UserRole.FAMILY, "device_control") is True

    # GUEST 权限
    assert check_permission(UserRole.GUEST, "device_control") is False
    assert check_permission(UserRole.GUEST, "chat") is True

    # 未知权限
    assert check_permission(UserRole.OWNER, "unknown_permission") is False

    print("  ✓ 权限检查测试通过")


def test_check_tool_access():
    """测试工具访问权限"""
    print("\n=== 测试工具访问权限 ===")

    # OWNER 可以访问所有工具
    assert check_tool_access(UserRole.OWNER, "control_pc") is True
    assert check_tool_access(UserRole.OWNER, "admin_users") is True

    # FAMILY 可以访问部分工具
    assert check_tool_access(UserRole.FAMILY, "control_pc") is True
    assert check_tool_access(UserRole.FAMILY, "set_reminder") is True

    # GUEST 权限受限
    assert check_tool_access(UserRole.GUEST, "control_pc") is False
    assert check_tool_access(UserRole.GUEST, "get_system_info") is True

    # allowed_tools 白名单测试
    assert check_tool_access(UserRole.OWNER, "restricted_tool", allowed_tools=["tool1", "tool2"]) is False
    assert check_tool_access(UserRole.OWNER, "tool1", allowed_tools=["tool1", "tool2"]) is True

    print("  ✓ 工具访问权限测试通过")


def test_api_key_quota():
    """测试API Key额度"""
    print("\n=== 测试API Key额度 ===")

    raw_key, key_id = create_api_key("额度测试", UserRole.GUEST)

    # 验证Key获取key_hash
    ok, role, err, api_key_obj = verify_request(raw_key, "127.0.0.1")
    assert ok is True

    # 检查额度
    key_hash = _hash_key(raw_key)
    ok, msg = check_api_key_quota(key_hash, tokens_needed=100)
    assert ok is True
    print(f"  额度检查通过: {msg}")

    # 记录使用
    result = record_api_key_usage(key_hash, tokens=50)
    assert result is True

    # 再次检查额度
    ok, msg = check_api_key_quota(key_hash, tokens_needed=100000)
    assert ok is False
    assert "额度不足" in msg
    print(f"  额度不足被检测: {msg}")

    # 无效Key
    ok, msg = check_api_key_quota("invalid_hash", tokens_needed=100)
    assert ok is False

    print("  ✓ API Key额度测试通过")


def test_revoke_api_key():
    """测试撤销API Key"""
    print("\n=== 测试撤销API Key ===")

    raw_key, key_id = create_api_key("待撤销Key", UserRole.GUEST)
    print(f"  创建 Key ID: {key_id}")

    # 撤销Key
    result = revoke_api_key(key_id)
    assert result is True

    # 验证已撤销
    ok, role, err, api_key_obj = verify_request(raw_key, "127.0.0.1")
    assert ok is False
    assert "无效" in err

    # 再次撤销应返回False
    result = revoke_api_key(key_id)
    assert result is False

    print("  ✓ 撤销API Key测试通过")


def test_trusted_ip():
    """测试信任IP管理"""
    print("\n=== 测试信任IP管理 ===")

    # 添加信任IP
    add_trusted_ip("192.168.1.100", UserRole.FAMILY)

    # 验证信任IP
    ok, role, err, api_key_obj = verify_request(None, "192.168.1.100")
    assert ok is True
    assert role == UserRole.FAMILY
    print("  信任IP验证通过")

    # 移除信任IP
    remove_trusted_ip("192.168.1.100")

    # 再次验证应失败
    ok, role, err, api_key_obj = verify_request(None, "192.168.1.100")
    assert ok is False

    print("  ✓ 信任IP管理测试通过")


def test_key_hashing():
    """测试Key哈希"""
    print("\n=== 测试Key哈希 ===")

    # 相同Key产生相同哈希
    key = "test_key_123"
    hash1 = _hash_key(key)
    hash2 = _hash_key(key)
    assert hash1 == hash2

    # 不同Key产生不同哈希
    hash3 = _hash_key("different_key")
    assert hash1 != hash3

    # 哈希长度应为64 (SHA256 hex)
    assert len(hash1) == 64

    print("  ✓ Key哈希测试通过")


def test_persistence():
    """测试持久化"""
    print("\n=== 测试持久化 ===")

    # 创建新Key
    raw_key, key_id = create_api_key("持久化测试", UserRole.OWNER)

    # 重新加载模块会自动加载持久化数据
    # 这里我们验证文件是否存在
    keys_file = os.path.join("data", "api_keys.json")
    assert os.path.exists(keys_file)

    # 检查文件权限（Unix系统）
    try:
        mode = os.stat(keys_file).st_mode
        # 文件应该存在
        print(f"  密钥文件已创建: {keys_file}")
    except Exception as e:
        print(f"  检查文件权限: {e}")

    print("  ✓ 持久化测试通过")


def test_edge_cases():
    """测试边界条件"""
    print("\n=== 测试边界条件 ===")

    # 空字符串
    try:
        create_api_key("", UserRole.GUEST)
        # 可能会创建，但名字为空
        print("  空名字创建成功")
    except Exception:
        print("  空名字被拒绝")

    # 超长名字
    long_name = "a" * 1000
    raw_key, key_id = create_api_key(long_name, UserRole.GUEST)
    assert key_id is not None

    # 特殊字符名字
    special_name = "测试<>&'\"特殊字符"
    raw_key, key_id = create_api_key(special_name, UserRole.GUEST)
    assert key_id is not None

    print("  ✓ 边界条件测试通过")


def main():
    print("=" * 60)
    print("  认证模块测试")
    print("=" * 60)

    setup_module()

    try:
        test_user_roles()
        test_create_api_key()
        test_list_api_keys()
        test_verify_request()
        test_check_permission()
        test_check_tool_access()
        test_api_key_quota()
        test_revoke_api_key()
        test_trusted_ip()
        test_key_hashing()
        test_persistence()
        test_edge_cases()

        print("\n" + "=" * 60)
        print("  所有认证测试通过")
        print("=" * 60)
    finally:
        teardown_module()


if __name__ == "__main__":
    main()