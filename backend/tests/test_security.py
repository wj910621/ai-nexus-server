"""安全工具测试"""
import pytest
from app.core.security import (
    hash_password, verify_password,
    create_access_token, create_refresh_token, decode_token,
)


def test_password_hashing():
    """测试密码哈希与验证"""
    password = "test_password_123"
    hashed = hash_password(password)

    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("wrong_password", hashed) is False


def test_access_token_creation():
    """测试访问令牌生成与解码"""
    user_id = "test-user-id"
    token = create_access_token(user_id)

    assert isinstance(token, str)

    payload = decode_token(token)
    assert payload is not None
    assert payload["sub"] == user_id
    assert payload["type"] == "access"


def test_refresh_token_creation():
    """测试刷新令牌"""
    user_id = "test-user-id"
    token = create_refresh_token(user_id)

    payload = decode_token(token)
    assert payload is not None
    assert payload["sub"] == user_id
    assert payload["type"] == "refresh"


def test_invalid_token_returns_none():
    """测试无效令牌解码返回 None"""
    payload = decode_token("invalid.token.here")
    assert payload is None
