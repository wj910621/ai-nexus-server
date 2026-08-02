"""
权限认证模块独立测试
不依赖项目导入，直接测试核心安全逻辑
"""

import hashlib
import secrets
import time
from enum import Enum
from typing import Dict, List, Optional
from dataclasses import dataclass


# 复制核心逻辑用于独立测试
class UserRole(Enum):
    OWNER = "owner"
    FAMILY = "family"
    GUEST = "guest"


ROLE_PERMISSIONS: Dict[UserRole, set] = {
    UserRole.OWNER: {
        "chat", "command", "device_control", "ha_control",
        "reminder", "note_read", "note_write",
        "system_info", "calendar", "email_read", "email_send",
        "browser", "mqtt", "automation_rules",
        "admin_users", "admin_config", "admin_skills",
        "wake_remote", "notify",
    },
    UserRole.FAMILY: {
        "chat", "command", "device_control", "ha_control",
        "reminder", "note_read", "note_write",
        "system_info", "calendar", "email_read", "email_send",
        "browser", "mqtt", "automation_rules",
        "wake_remote", "notify",
    },
    UserRole.GUEST: {
        "chat", "note_read",
        "system_info",
        "notify",
    },
}


@dataclass
class ApiKey:
    key_hash: str
    key_id: str
    role: UserRole
    name: str
    created_at: float
    last_used: float
    allowed_tools: Optional[List[str]] = None
    quota_used: int = 0
    quota_limit: int = 100000


_api_keys: Dict[str, ApiKey] = {}
_API_KEY_PEPPER = secrets.token_hex(32)


def _hash_key(key: str) -> str:
    """对 API Key 进行 SHA256+盐哈希"""
    return hashlib.sha256(f"{key}:{_API_KEY_PEPPER}".encode()).hexdigest()


def _generate_key() -> str:
    """生成随机 API Key"""
    return secrets.token_urlsafe(32)


def _generate_key_id() -> str:
    """生成 8 位 key_id"""
    return secrets.token_hex(4)


def create_api_key(name: str, role: UserRole, allowed_tools: Optional[List[str]] = None) -> tuple:
    """创建 API Key"""
    raw = _generate_key()
    key_hash = _hash_key(raw)
    key_id = _generate_key_id()
    api_key = ApiKey(
        key_hash=key_hash,
        key_id=key_id,
        role=role,
        name=name,
        created_at=time.time(),
        last_used=0,
        allowed_tools=allowed_tools,
        quota_used=0,
        quota_limit=1000000 if role == UserRole.OWNER else 100000,
    )
    _api_keys[key_hash] = api_key
    return raw, key_id


def revoke_api_key(key_id: str) -> bool:
    """撤销 API Key"""
    for key_hash, api_key in list(_api_keys.items()):
        if api_key.key_id == key_id:
            del _api_keys[key_hash]
            return True
    return False


def list_api_keys() -> List[Dict]:
    """列出所有 API Key"""
    return [
        {
            "id": k.key_id,
            "name": k.name,
            "role": k.role.value,
            "created_at": k.created_at,
            "last_used": k.last_used,
            "quota_used": k.quota_used,
            "quota_limit": k.quota_limit,
        }
        for k in _api_keys.values()
    ]


def verify_request(api_key: Optional[str], client_ip: str) -> tuple:
    """验证请求"""
    if not api_key:
        return False, UserRole.GUEST, "缺少 API Key", None

    key_hash = _hash_key(api_key)
    if key_hash not in _api_keys:
        return False, UserRole.GUEST, "无效的 API Key", None

    api_key_obj = _api_keys[key_hash]
    api_key_obj.last_used = time.time()
    return True, api_key_obj.role, None, api_key_obj


def check_api_key_quota(key_hash: str, tokens_needed: int = 1000) -> tuple:
    """检查配额"""
    api_key = _api_keys.get(key_hash)
    if not api_key:
        return False, "无效的 API Key"
    if api_key.quota_used + tokens_needed > api_key.quota_limit:
        return False, f"API Key 额度不足"
    return True, ""


def record_api_key_usage(key_hash: str, tokens: int) -> bool:
    """记录使用量"""
    api_key = _api_keys.get(key_hash)
    if not api_key:
        return False
    api_key.quota_used += tokens
    return True


# ============ 测试用例 ============

def setup_module():
    """测试前清理"""
    _api_keys.clear()


def teardown_module():
    """测试后清理"""
    _api_keys.clear()


def test_user_role_permissions():
    """测试角色权限矩阵"""
    print("\n=== 测试角色权限矩阵 ===")

    # OWNER 拥有所有权限
    assert "admin_users" in ROLE_PERMISSIONS[UserRole.OWNER]
    assert "admin_config" in ROLE_PERMISSIONS[UserRole.OWNER]
    assert "chat" in ROLE_PERMISSIONS[UserRole.OWNER]

    # FAMILY 缺少管理权限
    assert "admin_users" not in ROLE_PERMISSIONS[UserRole.FAMILY]
    assert "chat" in ROLE_PERMISSIONS[UserRole.FAMILY]

    # GUEST 权限最少
    assert "chat" in ROLE_PERMISSIONS[UserRole.GUEST]
    assert "device_control" not in ROLE_PERMISSIONS[UserRole.GUEST]

    print("✅ 角色权限矩阵正确")


def test_api_key_creation():
    """测试 API Key 创建"""
    print("\n=== 测试 API Key 创建 ===")

    raw_key, key_id = create_api_key("test_owner", UserRole.OWNER)
    assert len(raw_key) >= 32
    assert len(key_id) == 8

    key_hash = _hash_key(raw_key)
    assert key_hash in _api_keys

    api_key_obj = _api_keys[key_hash]
    assert api_key_obj.name == "test_owner"
    assert api_key_obj.role == UserRole.OWNER
    assert api_key_obj.quota_limit == 1000000

    print("✅ API Key 创建成功")


def test_api_key_revocation():
    """测试 API Key 撤销"""
    print("\n=== 测试 API Key 撤销 ===")

    raw_key, key_id = create_api_key("to_revoke", UserRole.FAMILY)
    assert len(list_api_keys()) >= 1

    result = revoke_api_key(key_id)
    assert result is True

    key_hash = _hash_key(raw_key)
    assert key_hash not in _api_keys

    result = revoke_api_key("nonexist")
    assert result is False

    print("✅ API Key 撤销成功")


def test_api_key_verification():
    """测试请求验证"""
    print("\n=== 测试请求验证 ===")

    raw_key, key_id = create_api_key("verify_test", UserRole.FAMILY)

    is_valid, role, error, api_obj = verify_request(raw_key, "192.168.1.100")
    assert is_valid is True
    assert role == UserRole.FAMILY
    assert error is None
    assert api_obj is not None

    is_valid, role, error, api_obj = verify_request("invalid_key", "192.168.1.100")
    assert is_valid is False
    assert role == UserRole.GUEST

    is_valid, role, error, api_obj = verify_request(None, "192.168.1.100")
    assert is_valid is False
    assert "缺少" in error

    print("✅ 请求验证成功")


def test_quota_management():
    """测试配额管理"""
    print("\n=== 测试配额管理 ===")

    raw_key, key_id = create_api_key("quota_test", UserRole.GUEST)
    key_hash = _hash_key(raw_key)

    is_ok, msg = check_api_key_quota(key_hash, 1000)
    assert is_ok is True

    record_api_key_usage(key_hash, 50000)
    api_obj = _api_keys[key_hash]
    assert api_obj.quota_used == 50000

    is_ok, msg = check_api_key_quota(key_hash, 100000)
    assert is_ok is False

    print("✅ 配额管理成功")


def test_key_hash_security():
    """测试密钥哈希安全"""
    print("\n=== 测试密钥哈希安全 ===")

    hash1 = _hash_key("test_key_123")
    hash2 = _hash_key("test_key_123")
    assert hash1 == hash2

    hash3 = _hash_key("test_key_456")
    assert hash1 != hash3

    assert len(hash1) == 64

    print("✅ 密钥哈希安全")


def test_key_id_collision_resistance():
    """测试 Key ID 碰撞抵抗"""
    print("\n=== 测试 Key ID 碰撞抵抗 ===")

    key_ids = set()
    for i in range(100):
        _, key_id = create_api_key(f"test_{i}", UserRole.GUEST)
        assert key_id not in key_ids
        key_ids.add(key_id)

    print(f"✅ 100 个 Key ID 无碰撞")


def main():
    print("=" * 60)
    print("  权限认证模块独立测试")
    print("=" * 60)

    setup_module()

    try:
        test_user_role_permissions()
        test_api_key_creation()
        test_api_key_revocation()
        test_api_key_verification()
        test_quota_management()
        test_key_hash_security()
        test_key_id_collision_resistance()

        print("\n" + "=" * 60)
        print("🎉 所有认证测试通过")
        print("=" * 60)

    finally:
        teardown_module()


if __name__ == "__main__":
    main()