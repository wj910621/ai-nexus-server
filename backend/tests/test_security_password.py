"""A5: 密码策略测试 - Phase 8 P7"""
import pytest
from app.core.password_policy import validate_password_complexity


def test_strong_password_accepted():
    """强密码应通过校验"""
    pw = "Str0ngP@ssw0rd!"
    assert validate_password_complexity(pw) == pw


def test_short_password_rejected():
    """短密码（<8）应被拒绝"""
    with pytest.raises(ValueError, match="长度"):
        validate_password_complexity("Ab1")


def test_no_letter_rejected():
    """无字母的密码应被拒绝"""
    with pytest.raises(ValueError, match="字母"):
        validate_password_complexity("12345678")


def test_no_digit_rejected():
    """无数字的密码应被拒绝"""
    with pytest.raises(ValueError, match="数字"):
        validate_password_complexity("abcdefgh")


def test_weak_password_rejected():
    """常见弱密码应被拒绝"""
    for pw in ("password1", "qwerty123", "admin123", "Password", "letmein1"):
        # 必须满足长度/字母/数字前提才会进入弱密码检查
        if len(pw) >= 8 and any(c.isalpha() for c in pw) and any(c.isdigit() for c in pw):
            with pytest.raises(ValueError, match="常见"):
                validate_password_complexity(pw)


def test_user_create_rejects_weak_password():
    """UserCreate schema 应拒绝弱密码"""
    from app.schemas.user import UserCreate
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        UserCreate(username="alice", email="alice@example.com", password="123")


def test_user_create_accepts_strong_password():
    """UserCreate schema 应接受强密码"""
    from app.schemas.user import UserCreate
    u = UserCreate(
        username="alice",
        email="alice@example.com",
        password="Str0ngP@ssw0rd!",
    )
    assert u.password == "Str0ngP@ssw0rd!"
