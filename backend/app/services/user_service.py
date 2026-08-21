"""用户服务"""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import or_, select

from app.core.security import hash_password, verify_password
from app.models.user import User
from app.services.base_service import BaseService


class UserService(BaseService[User]):
    model = User

    async def get_by_username(self, username: str) -> Optional[User]:
        """根据用户名查询"""
        result = await self.db.execute(
            select(User).where(User.username == username, User.is_deleted.is_(False))
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[User]:
        """根据邮箱查询"""
        result = await self.db.execute(
            select(User).where(User.email == email, User.is_deleted.is_(False))
        )
        return result.scalar_one_or_none()

    async def get_by_account(self, account: str) -> Optional[User]:
        """根据用户名或邮箱查询（用于登录）"""
        result = await self.db.execute(
            select(User).where(
                or_(User.username == account, User.email == account),
                User.is_deleted.is_(False),
            )
        )
        return result.scalar_one_or_none()

    async def register(self, username: str, email: str, password: str) -> User:
        """注册用户"""
        # 检查用户名/邮箱是否已存在
        if await self.get_by_username(username):
            raise ValueError("用户名已存在")
        if await self.get_by_email(email):
            raise ValueError("邮箱已被注册")

        user = User(
            username=username,
            email=email,
            password_hash=hash_password(password),
        )
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def authenticate(self, account: str, password: str) -> Optional[User]:
        """验证用户凭据"""
        user = await self.get_by_account(account)
        if not user:
            return None
        if not verify_password(password, user.password_hash):
            return None
        # 更新最后登录时间
        user.last_login_at = datetime.now(timezone.utc)
        await self.db.flush()
        return user

    async def request_email_verification(self, user: User) -> bool:
        """Generate a verification code, store on user, and send via email.

        Returns True if code was generated (email may be silently skipped).
        """
        from datetime import datetime, timedelta, timezone

        from app.services.email_service import EmailService

        email_svc = EmailService()
        code = email_svc.generate_verification_code()
        user.email_verification_code = code
        user.code_expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
        await self.db.flush()

        # Send email (no-op in desktop mode)
        await email_svc.send_verification_email(user.email, code)
        return True

    async def verify_email(self, user: User, code: str) -> bool:
        """Verify user's email with provided code. Returns True on success."""
        from datetime import datetime, timezone

        if not user.email_verification_code:
            return False
        if user.code_expires_at is None:
            return False
        expires_at = user.code_expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > expires_at:
            return False
        if user.email_verification_code != code:
            return False

        user.email_verified = True
        user.email_verification_code = None
        user.code_expires_at = None
        await self.db.flush()
        return True

    async def request_password_reset(self, email: str) -> bool:
        """Generate a password reset code for the user with given email.

        Returns True if user found and code generated; False if email not found.
        (For security, do NOT reveal whether email exists in API responses.)
        """
        user = await self.get_by_email(email)
        if user is None:
            return False

        from datetime import datetime, timedelta, timezone

        from app.services.email_service import EmailService

        email_svc = EmailService()
        code = email_svc.generate_verification_code()
        user.reset_password_code = code
        user.code_expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
        await self.db.flush()

        await email_svc.send_password_reset_email(user.email, code)
        return True

    async def reset_password(self, email: str, code: str, new_password: str) -> bool:
        """Reset user's password with provided code. Returns True on success."""
        user = await self.get_by_email(email)
        if user is None:
            return False
        if not user.reset_password_code:
            return False
        if user.code_expires_at is None:
            return False
        from datetime import datetime, timezone
        expires_at = user.code_expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > expires_at:
            return False
        if user.reset_password_code != code:
            return False

        user.password_hash = hash_password(new_password)
        user.reset_password_code = None
        user.code_expires_at = None
        await self.db.flush()
        return True
