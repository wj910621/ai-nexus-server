"""
认证模块单元测试
覆盖 API Key 创建/撤销、权限检查、配额管理
"""
import pytest
import os
import json
from auth import (
    UserRole,
    create_api_key,
    revoke_api_key,
    list_api_keys,
    verify_request,
    check_permission,
    check_tool_access,
    add_trusted_ip,
    remove_trusted_ip,
)


class TestAuth:
    def setup_method(self):
        global _api_keys, _TRUSTED_IPS
        from auth import _api_keys, _TRUSTED_IPS
        self._original_keys = _api_keys.copy()
        self._original_trusted = _TRUSTED_IPS.copy()
        _api_keys.clear()
        _TRUSTED_IPS.clear()

    def teardown_method(self):
        global _api_keys, _TRUSTED_IPS
        from auth import _api_keys, _TRUSTED_IPS
        _api_keys.clear()
        _api_keys.update(self._original_keys)
        _TRUSTED_IPS.clear()
        _TRUSTED_IPS.update(self._original_trusted)

    def test_create_api_key_owner(self):
        raw_key, key_id = create_api_key("test-owner", UserRole.OWNER)
        assert raw_key is not None
        assert len(raw_key) > 0
        assert key_id is not None
        assert len(key_id) == 8

    def test_create_api_key_family(self):
        raw_key, key_id = create_api_key("test-family", UserRole.FAMILY)
        assert raw_key is not None
        assert key_id is not None

    def test_create_api_key_guest(self):
        raw_key, key_id = create_api_key("test-guest", UserRole.GUEST)
        assert raw_key is not None
        assert key_id is not None

    def test_revoke_api_key(self):
        raw_key, key_id = create_api_key("to-revoke", UserRole.OWNER)
        assert revoke_api_key(key_id) is True
        assert revoke_api_key(key_id) is False

    def test_revoke_api_key_invalid(self):
        assert revoke_api_key("invalid-key-id") is False

    def test_list_api_keys(self):
        create_api_key("test1", UserRole.OWNER)
        create_api_key("test2", UserRole.FAMILY)
        keys = list_api_keys()
        assert len(keys) == 2
        assert keys[0]["name"] == "test1"
        assert keys[1]["name"] == "test2"

    def test_verify_request_valid_key(self):
        raw_key, _ = create_api_key("test-user", UserRole.FAMILY)
        ok, role, err, api_key_obj = verify_request(raw_key, "127.0.0.1")
        assert ok is True
        assert role == UserRole.FAMILY
        assert err is None

    def test_verify_request_invalid_key(self):
        ok, role, err, api_key_obj = verify_request("invalid-key-abc123", "127.0.0.1")
        assert ok is False
        assert err == "无效的 API Key"

    def test_verify_request_missing_key(self):
        ok, role, err, api_key_obj = verify_request(None, "127.0.0.1")
        assert ok is False
        assert err == "缺少 API Key"

    def test_verify_request_trusted_ip(self):
        add_trusted_ip("192.168.1.100", UserRole.OWNER)
        ok, role, err, api_key_obj = verify_request(None, "192.168.1.100")
        assert ok is True
        assert role == UserRole.OWNER

    def test_check_permission_owner(self):
        assert check_permission(UserRole.OWNER, "chat") is True
        assert check_permission(UserRole.OWNER, "admin_users") is True

    def test_check_permission_family(self):
        assert check_permission(UserRole.FAMILY, "chat") is True
        assert check_permission(UserRole.FAMILY, "admin_users") is False

    def test_check_permission_guest(self):
        assert check_permission(UserRole.GUEST, "chat") is True
        assert check_permission(UserRole.GUEST, "device_control") is False

    def test_check_tool_access_owner(self):
        assert check_tool_access(UserRole.OWNER, "control_pc") is True
        assert check_tool_access(UserRole.OWNER, "send_email") is True

    def test_check_tool_access_guest(self):
        assert check_tool_access(UserRole.GUEST, "control_pc") is False
        assert check_tool_access(UserRole.GUEST, "read_webpage") is False

    def test_check_tool_access_with_allowed_tools(self):
        assert check_tool_access(UserRole.OWNER, "control_pc", allowed_tools=["chat"]) is False
        assert check_tool_access(UserRole.OWNER, "chat", allowed_tools=["chat"]) is True

    def test_add_remove_trusted_ip(self):
        add_trusted_ip("10.0.0.1", UserRole.FAMILY)
        from auth import _TRUSTED_IPS
        assert "10.0.0.1" in _TRUSTED_IPS
        remove_trusted_ip("10.0.0.1")
        assert "10.0.0.1" not in _TRUSTED_IPS


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
