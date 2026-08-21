"""用户 Schema"""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.password_policy import validate_password_complexity
from app.schemas.common import ORMModel


class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr


class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def _check_password_complexity(cls, v: str) -> str:
        """A5: 密码复杂度校验"""
        return validate_password_complexity(v)


class UserLogin(BaseModel):
    account: str = Field(..., description="用户名或邮箱")
    password: str


class UserUpdate(BaseModel):
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    preferences: Optional[dict] = None


class UserResponse(ORMModel):
    id: str
    username: str
    email: str
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    status: str
    plan: str
    credits: int
    preferences: Optional[Any] = None
    email_verified: bool
    last_login_at: Optional[datetime] = None
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse


class UserPreferencesUpdate(BaseModel):
    """用户偏好更新请求"""
    preferred_provider: str | None = Field(None, pattern="^(cloud|local|hybrid)$")
    telemetry_enabled: bool | None = None
    cloud_sync_enabled: bool | None = None


class FirstLaunchUpdate(BaseModel):
    """首启动完成标记"""
    completed: bool = True


class UserPreferencesResponse(BaseModel):
    """用户偏好响应"""
    first_launch_completed: bool
    preferred_provider: str
    telemetry_enabled: bool
    cloud_sync_enabled: bool

    model_config = {"from_attributes": True}


class PasswordResetConfirm(BaseModel):
    """密码重置确认 schema - A5: 同步应用密码策略"""
    email: EmailStr
    code: str
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def _check_password_complexity(cls, v: str) -> str:
        """A5: 密码复杂度校验"""
        return validate_password_complexity(v)
