"""密码策略 - 复杂度校验"""
import re

WEAK_PASSWORDS = {
    "password", "12345678", "qwerty123", "abc12345", "letmein1",
    "welcome1", "admin123", "password1", "iloveyou1", "monkey123",
    # 可扩展到 top 1000
}


def validate_password_complexity(password: str) -> str:
    """校验密码复杂度，通过返回原值，失败抛 ValueError。"""
    if len(password) < 8:
        raise ValueError("密码长度至少 8 位")
    if not re.search(r"[A-Za-z]", password):
        raise ValueError("密码必须包含至少一个字母")
    if not re.search(r"\d", password):
        raise ValueError("密码必须包含至少一个数字")
    if password.lower() in WEAK_PASSWORDS:
        raise ValueError("密码过于常见，请使用更强的密码")
    return password
