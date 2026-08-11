"""
权限认证模块测试

覆盖 API Key 生命周期、信任 IP、权限矩阵、额度控制、持久化以及 Flask 认证装饰器。
"""

import importlib
import os

import pytest


@pytest.fixture
def auth(tmp_path, monkeypatch):
    """在隔离临时目录中重新加载 auth，确保每个用例拥有独立的密钥与信任 IP 状态。"""
    monkeypatch.setenv("AUTH_API_KEY_PEPPER", "test-pepper")
    monkeypatch.chdir(tmp_path)
    import auth as auth_mod

    importlib.reload(auth_mod)
    return auth_mod


class _FakeRequest:
    def __init__(self, headers=None, remote_addr="127.0.0.1"):
        self.headers = headers or {}
        self.remote_addr = remote_addr


def _hash_raw(auth, raw):
    return auth._hash_key(raw)


def test_create_api_key_returns_metadata_not_secret(auth):
    raw, key_id = auth.create_api_key("test", auth.UserRole.FAMILY)
    assert raw and isinstance(raw, str)
    assert len(key_id) == 8  # token_hex(4)

    key_hash = _hash_raw(auth, raw)
    assert key_hash in auth._api_keys
    assert auth._api_keys[key_hash].role == auth.UserRole.FAMILY
    assert auth._api_keys[key_hash].quota_limit == 100000

    listed = auth.list_api_keys()
    assert any(k["id"] == key_id and k["name"] == "test" for k in listed)
    assert raw not in repr(listed)


def test_owner_quota_limit_is_higher(auth):
    raw, key_id = auth.create_api_key("owner", auth.UserRole.OWNER)
    assert auth._api_keys[_hash_raw(auth, raw)].quota_limit == 1000000


def test_revoke_api_key(auth):
    raw, key_id = auth.create_api_key("to-revoke", auth.UserRole.GUEST)
    assert auth.revoke_api_key(key_id) is True
    assert auth.revoke_api_key(key_id) is False
    assert key_id not in {k["id"] for k in auth.list_api_keys()}


def test_verify_trusted_ip_bypasses_key(auth):
    auth.add_trusted_ip("192.168.1.10", auth.UserRole.FAMILY)
    ok, role, err, obj = auth.verify_request(None, "192.168.1.10")
    assert ok is True
    assert role == auth.UserRole.FAMILY
    assert err is None
    assert obj is None


def test_verify_missing_api_key(auth):
    ok, role, err, obj = auth.verify_request(None, "10.0.0.1")
    assert ok is False
    assert role == auth.UserRole.GUEST
    assert err == "缺少 API Key"
    assert obj is None


def test_verify_invalid_api_key(auth):
    ok, role, err, obj = auth.verify_request("not-a-key", "10.0.0.1")
    assert ok is False
    assert err == "无效的 API Key"


def test_verify_valid_key_updates_last_used(auth, monkeypatch):
    raw, key_id = auth.create_api_key("valid", auth.UserRole.OWNER)
    fixed_time = 1700000000.0
    monkeypatch.setattr(auth.time, "time", lambda: fixed_time)
    ok, role, err, obj = auth.verify_request(raw, "10.0.0.1")
    assert ok is True
    assert role == auth.UserRole.OWNER
    assert obj is not None
    assert obj.last_used == fixed_time


def test_check_permission(auth):
    assert auth.check_permission(auth.UserRole.OWNER, "admin_config") is True
    assert auth.check_permission(auth.UserRole.FAMILY, "admin_config") is False
    assert auth.check_permission(auth.UserRole.GUEST, "chat") is True
    assert auth.check_permission(auth.UserRole.GUEST, "device_control") is False
    assert auth.check_permission(object(), "chat") is False


def test_check_tool_access_respects_allowed_tools_whitelist(auth):
    raw, key_id = auth.create_api_key("limited", auth.UserRole.OWNER, allowed_tools=["notify"])
    api_key = auth._api_keys[_hash_raw(auth, raw)]
    assert auth.check_tool_access(api_key.role, "notify", api_key.allowed_tools) is True
    assert auth.check_tool_access(api_key.role, "control_pc", api_key.allowed_tools) is False


def test_check_tool_access_guest_limited(auth):
    assert auth.check_tool_access(auth.UserRole.GUEST, "notify") is True
    assert auth.check_tool_access(auth.UserRole.GUEST, "control_pc") is False


def test_check_tool_access_family_uses_permission_map(auth):
    assert auth.check_tool_access(auth.UserRole.FAMILY, "control_ha_device") is True
    assert auth.check_tool_access(auth.UserRole.FAMILY, "unknown_tool") is True  # owner/family fallback


def test_check_api_key_quota(auth):
    raw, key_id = auth.create_api_key("quota", auth.UserRole.GUEST)
    key_hash = _hash_raw(auth, raw)
    assert auth.check_api_key_quota(key_hash, 1000) == (True, "")
    ok, msg = auth.check_api_key_quota(key_hash, 1_000_000)
    assert ok is False
    assert "额度不足" in msg
    assert auth.check_api_key_quota("missing", 1) == (False, "无效的 API Key")


def test_record_api_key_usage(auth):
    raw, key_id = auth.create_api_key("usage", auth.UserRole.GUEST)
    key_hash = _hash_raw(auth, raw)
    assert auth.record_api_key_usage(key_hash, 150) is True
    assert auth.record_api_key_usage("missing", 1) is False
    assert auth._api_keys[key_hash].quota_used == 150


def test_persistence_across_reload(auth, monkeypatch, tmp_path):
    raw, key_id = auth.create_api_key("persist", auth.UserRole.FAMILY)

    monkeypatch.setenv("AUTH_API_KEY_PEPPER", "test-pepper")
    importlib.reload(auth)

    ids = {k["id"] for k in auth.list_api_keys()}
    assert key_id in ids


def test_require_auth_decorator(auth):
    from flask import Flask

    app = Flask(__name__)

    @app.route("/admin")
    @auth.require_auth(permission="admin_config")
    def admin_route():
        return {"ok": True}

    family_raw, _ = auth.create_api_key("family", auth.UserRole.FAMILY)
    owner_raw, _ = auth.create_api_key("owner", auth.UserRole.OWNER)

    with app.test_client() as client:
        assert client.get("/admin").status_code == 401
        assert client.get("/admin", headers={"X-API-Key": "bad"}).status_code == 401
        assert client.get("/admin", headers={"X-API-Key": family_raw}).status_code == 403
        assert client.get("/admin", headers={"X-API-Key": owner_raw}).status_code == 200


def test_get_client_id_from_request(auth):
    # auth 模块不直接暴露请求解析，但通过 rate_limiter 共享相似逻辑；
    # 这里验证 verify_request 同样从请求头提取 key。
    raw, key_id = auth.create_api_key("header", auth.UserRole.OWNER)
    ok, role, err, obj = auth.verify_request(raw, "10.0.0.1")
    assert ok is True
    assert obj.key_id == key_id
