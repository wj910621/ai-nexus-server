"""
Y·NEX权限认证模块
- API Key 认证
- 多用户分级权限（owner / family / guest）
- 敏感操作审计日志
"""

import hashlib
import os
import secrets
import time
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

from config import settings
from logger import logger


class UserRole(Enum):
    OWNER = "owner"      # 完全控制，包括添加工具、修改权限
    FAMILY = "family"    # 使用全部工具，但不能修改系统配置
    GUEST = "guest"      # 仅基础对话和查看，不能控制设备/执行敏感操作


# 权限矩阵
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

# 信任域白名单（不验证 API Key 的来源）
_TRUSTED_IPS: Dict[str, str] = {}  # ip -> role
_api_keys: Dict[str, "ApiKey"] = {}

# API Key 哈希盐：防止彩虹表攻击。
# 安全要求：必须在 .env 中设置 AUTH_API_KEY_PEPPER，否则启动时给出警告。
_API_KEY_PEPPER = os.environ.get("AUTH_API_KEY_PEPPER", "")
if not _API_KEY_PEPPER:
    import warnings as _warnings
    _warnings.warn(
        "AUTH_API_KEY_PEPPER 未设置，正在使用临时随机盐。"
        "重启后所有已签发的 API Key 将失效。请在 .env 中设置固定值。",
        RuntimeWarning,
        stacklevel=2,
    )
    _API_KEY_PEPPER = secrets.token_hex(32)


@dataclass
class ApiKey:
    key_hash: str
    key_id: str  # 8 位公开标识，用于列表与撤销
    role: UserRole
    name: str
    created_at: float
    last_used: float
    allowed_tools: Optional[List[str]] = None  # None = 所有权限
    quota_used: int = 0
    quota_limit: int = 100000  # 默认额度


def _hash_key(key: str) -> str:
    """对 API Key 进行 SHA256+盐哈希，数据库中永不存储明文 Key。"""
    return hashlib.sha256(f"{key}:{_API_KEY_PEPPER}".encode()).hexdigest()


def _generate_key() -> str:
    """生成随机 API Key"""
    return secrets.token_urlsafe(32)


def _generate_key_id() -> str:
    """生成 8 位 key_id"""
    return secrets.token_hex(4)


# ---------------------------------------------------------------------------
# API Key 管理（owner 操作）
# ---------------------------------------------------------------------------

def create_api_key(name: str, role: UserRole, allowed_tools: Optional[List[str]] = None) -> tuple[str, str]:
    """
    创建 API Key。
    返回 (raw_key, key_id)，其中 raw_key 仅创建时返回一次，之后无法找回。
    """
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
        quota_limit=100000 if role != UserRole.OWNER else 1000000,
    )
    _api_keys[key_hash] = api_key
    _save_keys()
    logger.info(f"创建 API Key：{name} ({role.value})")
    return raw, key_id


def revoke_api_key(key_id: str) -> bool:
    """撤销 API Key（通过 8 位 key_id）"""
    for key_hash, api_key in list(_api_keys.items()):
        if api_key.key_id == key_id:
            name = api_key.name
            del _api_keys[key_hash]
            _save_keys()
            logger.info(f"撤销 API Key：{name}")
            return True
    return False


def list_api_keys() -> List[Dict]:
    """列出所有 API Key（元数据，不含密钥）"""
    return [
        {
            "id": k.key_id,
            "name": k.name,
            "role": k.role.value,
            "created_at": k.created_at,
            "last_used": k.last_used,
            "allowed_tools": k.allowed_tools,
            "quota_used": k.quota_used,
            "quota_limit": k.quota_limit,
        }
        for k in _api_keys.values()
    ]


def check_api_key_quota(key_hash: str, tokens_needed: int = 1000) -> tuple[bool, str]:
    """检查 API Key 额度是否充足"""
    api_key = _api_keys.get(key_hash)
    if not api_key:
        return False, "无效的 API Key"
    if api_key.quota_used + tokens_needed > api_key.quota_limit:
        return False, f"API Key 额度不足：已用 {api_key.quota_used} / {api_key.quota_limit}"
    return True, ""


def record_api_key_usage(key_hash: str, tokens: int) -> bool:
    """记录 API Key 用量"""
    api_key = _api_keys.get(key_hash)
    if not api_key:
        return False
    api_key.quota_used += tokens
    _save_keys()
    return True


# ---------------------------------------------------------------------------
# 认证验证
# ---------------------------------------------------------------------------

def verify_request(api_key: Optional[str], client_ip: str) -> tuple[bool, UserRole, Optional[str], Optional[ApiKey]]:
    """
    验证请求是否合法。
    返回 (是否通过, 用户角色, 错误信息, API Key 对象)
    """
    # 信任 IP 直通（本地网络）
    if client_ip in _TRUSTED_IPS:
        role = UserRole(_TRUSTED_IPS[client_ip])
        return True, role, None, None

    if not api_key:
        return False, UserRole.GUEST, "缺少 API Key", None

    key_hash = _hash_key(api_key)
    if key_hash not in _api_keys:
        return False, UserRole.GUEST, "无效的 API Key", None

    api_key_obj = _api_keys[key_hash]
    api_key_obj.last_used = time.time()
    return True, api_key_obj.role, None, api_key_obj


def check_permission(role: UserRole, permission: str) -> bool:
    """检查角色是否有指定权限"""
    return permission in ROLE_PERMISSIONS.get(role, set())


def check_tool_access(role: UserRole, tool_name: str, allowed_tools: Optional[List[str]] = None) -> bool:
    """检查角色是否有权限使用指定工具。若传入 allowed_tools，则额外受白名单限制。"""
    # 若 Key 指定了允许的工具列表，优先按白名单校验（owner/family 也受限制）
    if allowed_tools is not None and tool_name not in allowed_tools:
        return False

    perms = ROLE_PERMISSIONS.get(role, set())
    # 从权限名推断可用的工具
    tool_perm_map = {
        "chat": ["chat", "send_message", "read_message"],
        "device_control": ["control_pc", "device_command", "list_device_domains"],
        "ha_control": ["control_ha_device", "list_ha_entities", "get_ha_entity_state",
                       "list_ha_scenes", "activate_ha_scene", "list_ha_areas", "get_ha_sensor"],
        "reminder": ["set_reminder", "list_reminders", "cancel_reminder"],
        "note_write": ["write_note"],
        "note_read": ["read_notes"],
        "email_read": ["read_emails"],
        "email_send": ["send_email"],
        "browser": ["read_webpage", "search_web", "run_browser_task"],
        "automation_rules": ["add_automation_rule", "list_automation_rules"],
        "mqtt": ["mqtt_publish"],
        "system_info": ["get_system_info", "get_time"],
        "wake_remote": ["wake_remote"],
        "notify": ["notify"],
    }
    allowed = perms & set(tool_perm_map.keys())
    for perm in allowed:
        if tool_name in tool_perm_map[perm]:
            return True
    # owner 和 family 默认有全部工具权限（但仍受 allowed_tools 白名单限制，已在上方处理）
    if role in (UserRole.OWNER, UserRole.FAMILY):
        return True
    return False


# ---------------------------------------------------------------------------
# 认证装饰器（用于 Flask 路由）
# ---------------------------------------------------------------------------

def require_auth(permission: Optional[str] = None):
    """Flask 路由认证装饰器"""
    def decorator(f):
        def wrapped(*args, **kwargs):
            from flask import request, jsonify

            # 仅从 Header 获取 API Key，禁止 URL Query 传参以避免日志泄露
            api_key = request.headers.get("X-API-Key")
            client_ip = request.remote_addr or "127.0.0.1"

            ok, role, err, api_key_obj = verify_request(api_key, client_ip)
            if not ok:
                return jsonify({"error": err, "authenticated": False}), 401

            if permission and not check_permission(role, permission):
                return jsonify({"error": f"权限不足：需要 {permission}"}), 403

            request._user_role = role
            request._api_key_obj = api_key_obj
            return f(*args, **kwargs)
        wrapped.__name__ = f.__name__
        return wrapped
    return decorator


# ---------------------------------------------------------------------------
# 信任域管理
# ---------------------------------------------------------------------------

def add_trusted_ip(ip: str, role: UserRole):
    """添加信任 IP（同一局域网内免认证）"""
    _TRUSTED_IPS[ip] = role.value
    logger.info(f"添加信任 IP：{ip} -> {role.value}")


def remove_trusted_ip(ip: str):
    if ip in _TRUSTED_IPS:
        del _TRUSTED_IPS[ip]


# ---------------------------------------------------------------------------
# 持久化
# ---------------------------------------------------------------------------

def _keys_file() -> str:
    return os.path.join("data", "api_keys.json")


def _save_keys():
    """保存 API Key 到文件"""
    os.makedirs("data", exist_ok=True)
    import json
    data = {
        "keys": [
            {
                "key_hash": k.key_hash,
                "key_id": k.key_id,
                "role": k.role.value,
                "name": k.name,
                "created_at": k.created_at,
                "last_used": k.last_used,
                "allowed_tools": k.allowed_tools,
                "quota_used": k.quota_used,
                "quota_limit": k.quota_limit,
            }
            for k in _api_keys.values()
        ],
        "trusted_ips": _TRUSTED_IPS,
    }
    with open(_keys_file(), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    # 限制密钥文件权限，仅所有者可读写（Windows 会忽略 chmod，但 Unix 系统有效）
    try:
        os.chmod(_keys_file(), 0o600)
    except Exception:
        pass


def _load_keys():
    """从文件加载 API Key"""
    global _TRUSTED_IPS
    try:
        import json
        with open(_keys_file(), "r", encoding="utf-8") as f:
            data = json.load(f)
        for k in data.get("keys", []):
            # 兼容旧数据：若缺少 key_id 则自动生成
            key_id = k.get("key_id") or _generate_key_id()
            _api_keys[k["key_hash"]] = ApiKey(
                key_hash=k["key_hash"],
                key_id=key_id,
                role=UserRole(k["role"]),
                name=k["name"],
                created_at=k["created_at"],
                last_used=k.get("last_used", 0),
                allowed_tools=k.get("allowed_tools"),
                quota_used=k.get("quota_used", 0),
                quota_limit=k.get("quota_limit", 100000),
            )
        _TRUSTED_IPS = data.get("trusted_ips", {})
        logger.info(f"已加载 {len(_api_keys)} 个 API Key")
    except FileNotFoundError:
        pass
    except Exception as e:
        logger.warning(f"加载 API Key 失败：{e}")


# ---------------------------------------------------------------------------
# 初始化
# ---------------------------------------------------------------------------

_load_keys()

# 如果没有任何 Key，自动创建一个 owner key 引导配置
if not _api_keys:
    raw, key_id = create_api_key("默认管理员", UserRole.OWNER)
    # 安全：将初始 Key 写入只读文件而非 stdout，避免日志采集泄露
    import pathlib as _pathlib
    _key_file = _pathlib.Path("data/.initial_owner_key")
    try:
        _key_file.parent.mkdir(parents=True, exist_ok=True)
        _key_file.write_text(
            f"Y·NEX 初始管理员 API Key\n"
            f"Key ID: {key_id}\n"
            f"API Key: {raw}\n"
            f"\n使用方法：在请求 Header 中添加 X-API-Key: <your-api-key>\n"
            f"安全提示：请妥善保存此文件，确认后建议删除。\n",
            encoding="utf-8",
        )
        try:
            _key_file.chmod(0o600)
        except Exception:
            pass  # Windows 上 chmod 限制
        logger.info(f"首次配置：已创建管理员 API Key，请查看 {_key_file}")
    except Exception as e:
        # 极端情况下回退到日志（不输出明文 Key）
        logger.error(f"创建初始 Key 文件失败: {e}，Key ID: {key_id}")
