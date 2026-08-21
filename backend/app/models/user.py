"""用户模型"""
from sqlalchemy import JSON, Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin


class User(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """用户实体"""
    __tablename__ = "users"

    # 基本信息
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(200), unique=True, nullable=False, index=True)
    password_hash = Column(String(200), nullable=False)
    # In shared-account mode this record owns Story project data only.
    external_subject = Column(String(128), unique=True, nullable=True, index=True)
    avatar_url = Column(String(500))
    bio = Column(Text)

    # 账户状态
    status = Column(String(20), default="active")  # active/banned/inactive
    email_verified = Column(Boolean, default=False)
    last_login_at = Column(DateTime)

    # 认证验证码 (邮箱验证 + 密码重置)
    email_verification_code = Column(String(20))
    reset_password_code = Column(String(20))
    code_expires_at = Column(DateTime)

    # 角色 (Phase 6)
    role = Column(String(20), default="user")  # user/admin

    # 订阅信息
    plan = Column(String(20), default="free")  # free/pro/enterprise
    plan_expires_at = Column(DateTime)
    credits = Column(Integer, default=100)

    # 偏好设置
    preferences = Column(JSON, default=lambda: {
        "language": "zh-CN",
        "theme": "dark",
        "default_model": "sdxl",
        "auto_save": True,
    })

    # 前端集成：首启动与偏好设置
    first_launch_completed: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default="false"
    )
    preferred_provider: Mapped[str] = mapped_column(
        String(20), default="cloud", nullable=False, server_default="cloud"
    )
    telemetry_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, server_default="true"
    )
    cloud_sync_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default="false"
    )
