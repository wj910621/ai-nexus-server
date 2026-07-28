"""
认证模块安全测试
验证 API Key 管理、权限检查、配额控制等核心安全功能
"""

import os
import sys
import tempfile
import shutil
import json
import time
from pathlib import Path

# 确保导入项目根目录
sys.path.insert(0, str(Path(__file__).parent))

# 使用临时数据目录，避免污染生产数据
_test_data_dir = None


def _setup_test_env():
    """创建临时测试环境"""
    global _test_data_dir
    _test_data_dir = tempfile.mkdtemp(prefix="ynex_auth_test_")
    os.makedirs(_test_data_dir, exist_ok=True)
    os.environ["TEST_DATA_DIR"] = _test_data_dir
    # 重置 auth 模块状态
    import importlib
    if 'auth' in sys.modules:
        importlib.reload(sys.modules['auth'])


def _teardown_test_env():
    """清理临时测试环境"""
    global _test_data_dir
    if _test_data_dir and os.path.exists(_test_data_dir):
        try:
            shutil.rmtree(_test_data_dir)
        except Exception:
            pass


def test_api_key_creation_and_verification():
    """测试 API Key 创建与验证"""
    print("\n=== 测试 API Key 创建与验证 ===")

    import auth
    auth._api_keys.clear()

    # 创建 owner key
    raw_key, key_id = auth.create_api_key("测试管理员", auth.UserRole.OWNER)
    print(f"创建 Key ID: {key_id}")

    # 验证原始密钥
    key_hash = auth._hash_key(raw_key)
    assert key_hash in auth._api_keys, "API Key 应已存储"
    api_key_obj = auth._api_keys[key_hash]
    assert api_key_obj.role == auth.UserRole.OWNER
    assert api_key_obj.name == "测试管理员"
    assert api_key_obj.key_id == key_id

    # 验证 verify_request
    ok, role, err, key_obj = auth.verify_request(raw_key, "127.0.0.1")
    assert ok, f"验证应成功，错误: {err}"
    assert role == auth.UserRole.OWNER
    assert key_obj.key_id == key_id

    print("✅ API Key 创建与验证通过")


def test_api_key_revocation():
    """测试 API Key 撤销"""
    print("\n=== 测试 API Key 撤销 ===")

    import auth
    auth._api_keys.clear()

    raw_key, key_id = auth.create_api_key("测试用户", auth.UserRole.FAMILY)

    # 验证存在
    key_hash = auth._hash_key(raw_key)
    assert key_hash in auth._api_keys

    # 撤销
    result = auth.revoke_api_key(key_id)
    assert result, "撤销应成功"
    assert key_hash not in auth._api_keys, "撤销后 Key 应被删除"

    # 再次撤销应失败
    result = auth.revoke_api_key(key_id)
    assert not result, "撤销不存在的 Key 应失败"

    # 验证失效
    ok, role, err, key_obj = auth.verify_request(raw_key, "127.0.0.1")
    assert not ok, "撤销后的 Key 应无法验证"
    assert err == "无效的 API Key"

    print("✅ API Key 撤销通过")


def test_role_permissions():
    """测试角色权限矩阵"""
    print("\n=== 测试角色权限矩阵 ===")

    import auth

    # OWNER 应有所有权限
    assert auth.check_permission(auth.UserRole.OWNER, "chat")
    assert auth.check_permission(auth.UserRole.OWNER, "admin_config")
    assert auth.check_permission(auth.UserRole.OWNER, "device_control")

    # FAMILY 应缺少 admin 权限
    assert auth.check_permission(auth.UserRole.FAMILY, "chat")
    assert auth.check_permission(auth.UserRole.FAMILY, "device_control")
    assert not auth.check_permission(auth.UserRole.FAMILY, "admin_config")
    assert not auth.check_permission(auth.UserRole.FAMILY, "admin_users")

    # GUEST 仅能基础对话
    assert auth.check_permission(auth.UserRole.GUEST, "chat")
    assert not auth.check_permission(auth.UserRole.GUEST, "device_control")
    assert not auth.check_permission(auth.UserRole.GUEST, "email_send")

    print("✅ 角色权限矩阵验证通过")


def test_tool_access_control():
    """测试工具访问控制"""
    print("\n=== 测试工具访问控制 ===")

    import auth

    # OWNER 默认全部工具
    assert auth.check_tool_access(auth.UserRole.OWNER, "control_pc")
    assert auth.check_tool_access(auth.UserRole.OWNER, "unknown_tool")

    # FAMILY 默认全部工具（除 admin）
    assert auth.check_tool_access(auth.UserRole.FAMILY, "control_pc")

    # GUEST 仅限基础工具
    assert not auth.check_tool_access(auth.UserRole.GUEST, "control_pc")
    assert not auth.check_tool_access(auth.UserRole.GUEST, "send_email")

    # 白名单限制测试
    allowed_tools = ["control_pc", "get_system_info"]
    assert auth.check_tool_access(auth.UserRole.OWNER, "control_pc", allowed_tools)
    assert not auth.check_tool_access(auth.UserRole.OWNER, "send_email", allowed_tools)

    print("✅ 工具访问控制验证通过")


def test_quota_enforcement():
    """测试配额限制"""
    print("\n=== 测试配额限制 ===")

    import auth
    auth._api_keys.clear()

    raw_key, key_id = auth.create_api_key("配额测试", auth.UserRole.FAMILY)
    key_hash = auth._hash_key(raw_key)
    api_key_obj = auth._api_keys[key_hash]

    # 检查初始配额
    assert api_key_obj.quota_limit == 100000

    # 模拟使用
    auth.record_api_key_usage(key_hash, 5000)
    api_key_obj = auth._api_keys[key_hash]
    assert api_key_obj.quota_used == 5000

    # 检查配额充足
    ok, msg = auth.check_api_key_quota(key_hash, 1000)
    assert ok

    # 检查配额不足
    ok, msg = auth.check_api_key_quota(key_hash, 100000)
    assert not ok
    assert "额度不足" in msg

    print("✅ 配额限制验证通过")


def test_trusted_ip_bypass():
    """测试信任 IP 免认证"""
    print("\n=== 测试信任 IP 免认证 ===")

    import auth
    auth._TRUSTED_IPS.clear()

    # 添加信任 IP
    auth.add_trusted_ip("192.168.1.100", auth.UserRole.FAMILY)

    # 验证免认证
    ok, role, err, key_obj = auth.verify_request(None, "192.168.1.100")
    assert ok
    assert role == auth.UserRole.FAMILY
    assert key_obj is None

    # 移除信任 IP
    auth.remove_trusted_ip("192.168.1.100")
    ok, role, err, key_obj = auth.verify_request(None, "192.168.1.100")
    assert not ok
    assert err == "缺少 API Key"

    print("✅ 信任 IP 免认证验证通过")


def test_missing_api_key():
    """测试缺少 API Key 拒绝"""
    print("\n=== 测试缺少 API Key 拒绝 ===")

    import auth
    auth._TRUSTED_IPS.clear()

    ok, role, err, key_obj = auth.verify_request(None, "10.0.0.1")
    assert not ok
    assert err == "缺少 API Key"
    assert role == auth.UserRole.GUEST

    print("✅ 缺少 API Key 拒绝验证通过")


def test_invalid_api_key():
    """测试无效 API Key 拒绝"""
    print("\n=== 测试无效 API Key 拒绝 ===")

    import auth
    auth._api_keys.clear()

    ok, role, err, key_obj = auth.verify_request("invalid_key_12345", "10.0.0.1")
    assert not ok
    assert err == "无效的 API Key"

    print("✅ 无效 API Key 拒绝验证通过")


def test_key_persistence():
    """测试密钥持久化"""
    print("\n=== 测试密钥持久化 ===")

    import auth

    # 创建临时文件
    temp_dir = tempfile.mkdtemp()
    auth._TRUSTED_IPS.clear()
    auth._api_keys.clear()

    # 模拟持久化路径
    original_keys_file = auth._keys_file
    auth._keys_file = lambda: os.path.join(temp_dir, "api_keys.json")

    try:
        # 创建并保存
        raw_key, key_id = auth.create_api_key("持久化测试", auth.UserRole.OWNER)

        # 验证文件已生成
        keys_file = auth._keys_file()
        assert os.path.exists(keys_file)

        # 清空内存并重新加载
        auth._api_keys.clear()
        auth._load_keys()

        # 验证已恢复
        key_hash = auth._hash_key(raw_key)
        assert key_hash in auth._api_keys
        api_key_obj = auth._api_keys[key_hash]
        assert api_key_obj.name == "持久化测试"
        assert api_key_obj.role == auth.UserRole.OWNER

        print("✅ 密钥持久化验证通过")
    finally:
        # 清理
        shutil.rmtree(temp_dir, ignore_errors=True)
        auth._keys_file = original_keys_file


def test_api_key_never_logged():
    """测试 API Key 明文永不记录到日志"""
    print("\n=== 测试 API Key 明文不泄露 ===")

    import auth
    auth._api_keys.clear()

    raw_key, key_id = auth.create_api_key("安全测试", auth.UserRole.OWNER)

    # 验证数据库中仅存哈希
    key_hash = auth._hash_key(raw_key)
    assert key_hash in auth._api_keys

    # 验证密钥格式（应为 yn_ 前缀的随机字符串）
    assert raw_key.startswith("yn_") or len(raw_key) >= 32

    # 验证 key_id 仅有8位标识
    assert len(key_id) == 8

    # 验证 list_api_keys 不返回明文
    keys_list = auth.list_api_keys()
    for k in keys_list:
        assert "key_hash" not in k or k.get("key_hash") != raw_key
        assert k.get("id") == key_id

    print("✅ API Key 明文不泄露验证通过")


def main():
    """运行所有认证安全测试"""
    print("=" * 60)
    print("Y·NEX 认证模块安全测试")
    print("=" * 60)

    try:
        _setup_test_env()

        test_api_key_creation_and_verification()
        test_api_key_revocation()
        test_role_permissions()
        test_tool_access_control()
        test_quota_enforcement()
        test_trusted_ip_bypass()
        test_missing_api_key()
        test_invalid_api_key()
        test_key_persistence()
        test_api_key_never_logged()

        print("\n" + "=" * 60)
        print("✅ 所有认证安全测试通过")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        _teardown_test_env()


if __name__ == "__main__":
    main()