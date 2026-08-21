"""安全工具 - JWT 令牌与密码哈希"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from jwt import PyJWTError

from app.core.config import settings


def hash_password(password: str) -> str:
    """哈希密码 (bcrypt，截断到72字节以兼容bcrypt版本)"""
    password_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    try:
        password_bytes = plain_password.encode("utf-8")[:72]
        hashed_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(password_bytes, hashed_bytes)
    except (ValueError, TypeError):
        return False


def create_access_token(subject: str, expires_delta: Optional[timedelta] = None) -> str:
    """创建访问令牌"""
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.jwt_access_token_expire_minutes)
    )
    to_encode = {
        "sub": subject,
        "exp": expire,
        "type": "access",
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(subject: str) -> str:
    """创建刷新令牌"""
    expire = datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_token_expire_days)
    to_encode = {
        "sub": subject,
        "exp": expire,
        "type": "refresh",
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> Optional[dict]:
    """解码令牌，失败返回 None"""
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except PyJWTError:
        return None


def decode_ynex_story_token(token: str) -> Optional[dict]:
    """Validate the short-lived, audience-restricted session from Y·NEX."""
    if not settings.ynex_sso_secret:
        return None
    try:
        return jwt.decode(
            token,
            settings.ynex_sso_secret,
            algorithms=[settings.jwt_algorithm],
            audience=settings.ynex_sso_audience,
            issuer=settings.ynex_sso_issuer,
        )
    except PyJWTError:
        return None


