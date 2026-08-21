"""依赖注入 - 数据库会话与当前用户"""
import hashlib
import uuid
from typing import AsyncGenerator

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.security import decode_token, decode_ynex_story_token
from app.models.revoked_token import RevokedToken
from app.models.user import User

# OAuth2 密码流
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def _is_token_revoked(db: AsyncSession, jti: str | None) -> bool:
    """检查 token jti 是否在撤销表中。"""
    if not jti:
        return False
    result = await db.execute(select(RevokedToken).where(RevokedToken.jti == jti))
    return result.scalar_one_or_none() is not None


def _coerce_user_id(user_id):
    """JWT sub 声明是字符串，UUID 列在 SQLite 下需要 UUID 对象。

    PostgreSQL+asyncpg 接受字符串，但 SQLite(as_uuid=True) 不接受。
    此函数统一转换，保持跨后端兼容。
    """
    if isinstance(user_id, str):
        try:
            return uuid.UUID(user_id)
        except (ValueError, AttributeError):
            return user_id
    return user_id


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """获取当前登录用户"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无效的认证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if settings.billing_mode == "jarvis":
        payload = decode_ynex_story_token(token)
        if payload is None or not payload.get("sub"):
            raise credentials_exception
        subject = str(payload["sub"])
        result = await db.execute(select(User).where(User.external_subject == subject))
        user = result.scalar_one_or_none()
        if user is None:
            digest = hashlib.sha256(subject.encode("utf-8")).hexdigest()[:24]
            email = str(payload.get("email") or f"ynex-{digest}@invalid.local").lower()
            user = User(
                username=f"ynex_{digest}",
                email=email,
                password_hash="!ynex-sso-disabled!",
                external_subject=subject,
                email_verified=True,
                plan=str(payload.get("membership") or "free"),
                credits=0,
                preferences={"language": "zh-CN", "theme": "dark", "default_model": "cloud", "auto_save": True},
            )
            db.add(user)
            await db.flush()
        elif user.plan != str(payload.get("membership") or "free"):
            user.plan = str(payload.get("membership") or "free")
            await db.flush()
    else:
        payload = decode_token(token)
        user = None
    if payload is None:
        raise credentials_exception

    if settings.billing_mode != "jarvis":
        user_id = payload.get("sub")
        token_type = payload.get("type")
        if user_id is None or token_type != "access":
            raise credentials_exception

    # A1: 校验 token 是否已撤销（登出/刷新旋转后旧 token 失效）
    if settings.billing_mode != "jarvis" and await _is_token_revoked(db, payload.get("jti")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="令牌已被撤销",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if settings.billing_mode != "jarvis":
        result = await db.execute(select(User).where(User.id == _coerce_user_id(user_id)))
        user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception

    if user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账户已被禁用",
        )

    return user


async def get_current_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """Require admin role. Raises 403 if user is not admin."""
    from app.core.permissions import require_admin
    require_admin(current_user)
    return current_user


async def get_optional_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """Get current user if authenticated, else None (for public endpoints)."""
    if not token:
        return None
    try:
        return await get_current_user(token=token, db=db)
    except HTTPException:
        return None
