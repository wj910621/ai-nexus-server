"""Admin service - system administration operations."""
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import Subscription
from app.models.user import User
from app.services.base_service import BaseService
from app.services.billing_service import BillingService


class AdminService(BaseService[User]):
    """Admin-only operations."""

    model = User

    def __init__(self, db: AsyncSession):
        super().__init__(db)
        self._billing = BillingService(db)

    async def list_users(
        self,
        limit: int = 50,
        offset: int = 0,
        role: Optional[str] = None,
        status_filter: Optional[str] = None,
    ) -> list[User]:
        """List all users with optional filters."""
        stmt = select(User).where(User.is_deleted.is_(False))
        if role:
            stmt = stmt.where(User.role == role)
        if status_filter:
            stmt = stmt.where(User.status == status_filter)
        stmt = stmt.order_by(User.created_at.desc()).offset(offset).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_stats(self) -> dict:
        """Get system statistics."""
        # Total users
        total_users = await self.db.scalar(
            select(func.count(User.id)).where(User.is_deleted.is_(False))
        )
        # Active subscriptions
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        active_subs = await self.db.scalar(
            select(func.count(Subscription.id)).where(
                Subscription.status == "active",
                Subscription.expires_at > now,
            )
        )
        # Total credits in circulation
        total_credits = await self.db.scalar(
            select(func.sum(User.credits)).where(User.is_deleted.is_(False))
        )
        # Users by plan
        plan_counts_rows = await self.db.execute(
            select(User.plan, func.count(User.id))
            .where(User.is_deleted.is_(False))
            .group_by(User.plan)
        )
        users_by_plan = {plan: count for plan, count in plan_counts_rows}

        return {
            "total_users": total_users or 0,
            "active_subscriptions": active_subs or 0,
            "total_credits_in_circulation": total_credits or 0,
            "users_by_plan": users_by_plan,
        }

    async def ban_user(self, user_id: UUID) -> bool:
        """Ban a user (set status='banned')."""
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        if user is None:
            return False
        user.status = "banned"
        await self.db.flush()
        return True

    async def unban_user(self, user_id: UUID) -> bool:
        """Unban a user (set status='active')."""
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        if user is None:
            return False
        user.status = "active"
        await self.db.flush()
        return True

    async def grant_credits(
        self, user_id: UUID, amount: int,
        reason: str = "admin_grant", description: str = "",
    ) -> int:
        """Grant credits to a user (admin bonus)."""
        return await self._billing.bonus(
            user_id=user_id, amount=amount,
            reason=reason, description=description,
        )

    async def promote_admin(self, user_id: UUID) -> bool:
        """Promote a user to admin role."""
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        if user is None:
            return False
        user.role = "admin"
        await self.db.flush()
        return True

    async def demote_admin(self, user_id: UUID) -> bool:
        """Demote an admin to regular user."""
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        if user is None:
            return False
        user.role = "user"
        await self.db.flush()
        return True
