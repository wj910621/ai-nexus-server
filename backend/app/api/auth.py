"""认证路由 - 注册/登录/刷新令牌"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_current_user, get_db
from app.core.rate_limit import rate_limit
from app.core.response import ApiResponse
from app.core.security import create_access_token, create_refresh_token, decode_token
from app.models.revoked_token import RevokedToken
from app.models.user import User
from app.schemas.user import TokenResponse, UserCreate, UserLogin, UserResponse
from app.services.user_service import UserService

router = APIRouter(prefix="/auth", tags=["认证"])


def _shared_account_mode() -> None:
    if settings.billing_mode == "jarvis":
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Y·NEX Story Studio 使用主站账户登录，请从 Y·NEX 主站进入。",
        )


@router.post("/register", response_model=ApiResponse[UserResponse])
async def register(payload: UserCreate, db: AsyncSession = Depends(get_db)):
    """用户注册"""
    _shared_account_mode()
    service = UserService(db)
    try:
        user = await service.register(
            username=payload.username,
            email=payload.email,
            password=payload.password,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    return ApiResponse.success(data=UserResponse.model_validate(user), message="注册成功")


@router.post("/login", response_model=ApiResponse[TokenResponse])
@rate_limit(times=5, seconds=60)
async def login(
    payload: UserLogin,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """用户登录

    A3: 限流落地 - 5 次/分钟，防止暴力破解。
    """
    _shared_account_mode()
    service = UserService(db)
    user = await service.authenticate(payload.account, payload.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名/邮箱或密码错误",
        )
    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))
    return ApiResponse.success(
        data=TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            user=UserResponse.model_validate(user),
        ),
        message="登录成功",
    )


@router.post("/refresh", response_model=ApiResponse[TokenResponse])
async def refresh_token(refresh_token: str, db: AsyncSession = Depends(get_db)):
    """刷新访问令牌 (Task 7: 旋转 + 撤销旧 refresh token)"""
    _shared_account_mode()
    payload = decode_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的刷新令牌",
        )
    jti = payload.get("jti")
    user_id = payload.get("sub")

    # Check if refresh token was revoked (rotation reuse detection)
    if jti:
        revoked = await db.execute(
            select(RevokedToken).where(RevokedToken.jti == jti)
        )
        if revoked.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="刷新令牌已被撤销",
            )

    service = UserService(db)
    user = await service.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
        )

    # Revoke old refresh token (rotation)
    if jti:
        db.add(RevokedToken(
            jti=jti,
            user_id=str(user_id),
            token_type="refresh",
            expires_at=datetime.now(timezone.utc) + timedelta(
                days=settings.jwt_refresh_token_expire_days
            ),
        ))
        await db.flush()

    new_access = create_access_token(str(user.id))
    new_refresh = create_refresh_token(str(user.id))
    return ApiResponse.success(
        data=TokenResponse(
            access_token=new_access,
            refresh_token=new_refresh,
            user=UserResponse.model_validate(user),
        )
    )


@router.post("/verify-email/request", response_model=ApiResponse)
async def request_email_verification(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Request a verification code for the current user's email."""
    service = UserService(db)
    await service.request_email_verification(current_user)
    return ApiResponse.success(message="验证码已发送（若 SMTP 未配置，请查看日志）")


@router.post("/verify-email/confirm", response_model=ApiResponse)
async def confirm_email_verification(
    code: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Confirm email verification with provided code."""
    service = UserService(db)
    ok = await service.verify_email(current_user, code)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="验证码无效或已过期",
        )
    return ApiResponse.success(message="邮箱验证成功")


@router.post("/password-reset/request", response_model=ApiResponse)
async def request_password_reset(
    email: str,
    db: AsyncSession = Depends(get_db),
):
    """Request a password reset code. Always returns success (security)."""
    service = UserService(db)
    await service.request_password_reset(email)
    return ApiResponse.success(message="若邮箱存在，重置码已发送")


@router.post("/password-reset/confirm", response_model=ApiResponse)
async def confirm_password_reset(
    email: str,
    code: str,
    new_password: str,
    db: AsyncSession = Depends(get_db),
):
    """Reset password with provided email, code, and new password."""
    service = UserService(db)
    ok = await service.reset_password(email, code, new_password)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="重置码无效或已过期",
        )
    return ApiResponse.success(message="密码重置成功")


@router.post("/logout", response_model=ApiResponse)
async def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Logout — revoke current access token (Task 7).

    Stateless JWT still works client-side; server-side blacklist ensures the
    token cannot be reused before its natural expiry.
    """
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.replace("Bearer ", "")
    payload = decode_token(token) if token else None
    jti = payload.get("jti") if payload else None

    if jti:
        # Revoke access token until its natural expiry
        db.add(RevokedToken(
            jti=jti,
            user_id=str(current_user.id),
            token_type="access",
            expires_at=datetime.now(timezone.utc) + timedelta(
                minutes=settings.jwt_access_token_expire_minutes
            ),
        ))
        await db.flush()

    return ApiResponse.success(message="登出成功")
