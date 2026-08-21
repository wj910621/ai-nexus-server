"""Subscription service - plan management and billing cycles.

Plan definitions are static (read from PLAN_DEFINITIONS). Each subscribe
operation creates a Subscription record, updates user.plan, and grants
monthly credits via BillingService.
"""
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache_decorator import cached
from app.models.billing import Subscription
from app.models.user import User
from app.schemas.subscription import PlanInfo
from app.services.base_service import BaseService
from app.services.billing_service import BillingService

# Static plan catalog (could be moved to DB in the future)
PLAN_DEFINITIONS: dict[str, PlanInfo] = {
    "free": PlanInfo(
        plan_id="free",
        name="免费版",
        price_cents=0,
        credits_per_month=100,
        max_projects=5,
        max_render_resolution=720,
        features=["100 积分/月", "最多 5 个项目", "720p 渲染", "基础 AI 引擎"],
        is_popular=False,
    ),
    "pro": PlanInfo(
        plan_id="pro",
        name="专业版",
        price_cents=4900,  # ¥49/month
        credits_per_month=2000,
        max_projects=50,
        max_render_resolution=1080,
        features=["2000 积分/月", "最多 50 个项目", "1080p 渲染", "全部 AI 引擎", "优先支持"],
        is_popular=True,
    ),
    "enterprise": PlanInfo(
        plan_id="enterprise",
        name="企业版",
        price_cents=29900,  # ¥299/month
        credits_per_month=20000,
        max_projects=0,  # unlimited
        max_render_resolution=2160,
        features=["20000 积分/月", "无限项目", "4K 渲染", "全部 AI 引擎", "专属支持", "团队协作"],
        is_popular=False,
    ),
}


class SubscriptionService(BaseService[Subscription]):
    """Subscription management."""

    model = Subscription

    def __init__(self, db: AsyncSession):
        super().__init__(db)
        self._billing = BillingService(db)

    def list_plans(self) -> List[PlanInfo]:
        """Return all available plans."""
        return list(PLAN_DEFINITIONS.values())

    def get_plan_info(self, plan_id: str) -> Optional[PlanInfo]:
        """Return a specific plan by ID, or None if not found."""
        return PLAN_DEFINITIONS.get(plan_id)

    async def subscribe(
        self,
        user_id: UUID,
        plan: str,
        duration_days: int = 30,
        payment_method: Optional[str] = None,
        payment_id: Optional[str] = None,
        auto_renew: bool = False,
    ) -> Subscription:
        """Subscribe user to a plan. Creates Subscription, updates user, grants credits.

        Args:
            user_id: User to subscribe
            plan: Plan ID (must exist in PLAN_DEFINITIONS)
            duration_days: Subscription duration in days
            payment_method: e.g. 'stripe', 'alipay', 'mock'
            payment_id: Payment intent ID from payment provider
            auto_renew: Whether to auto-renew at expiry

        Raises:
            ValueError: If plan is unknown or user not found
        """
        plan_info = PLAN_DEFINITIONS.get(plan)
        if plan_info is None:
            raise ValueError(f"Unknown plan: {plan}")

        now = datetime.now(timezone.utc)
        started_at = now
        expires_at = now + timedelta(days=duration_days)

        # Cancel any existing active subscription for this user
        existing = await self.get_active(user_id)
        if existing is not None:
            existing.status = "cancelled"
            existing.cancelled_at = now
            existing.auto_renew = False
            await self.db.flush()

        # Create new subscription
        sub = Subscription(
            user_id=user_id,
            plan=plan,
            status="active",
            started_at=started_at,
            expires_at=expires_at,
            amount=plan_info.price_cents,
            payment_method=payment_method,
            payment_id=payment_id,
            auto_renew=auto_renew,
        )
        self.db.add(sub)
        await self.db.flush()
        await self.db.refresh(sub)

        # Update user's plan
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        if user is None:
            raise ValueError(f"User {user_id} not found")
        user.plan = plan
        user.plan_expires_at = expires_at
        await self.db.flush()

        # Grant monthly credits as bonus
        if plan_info.credits_per_month > 0:
            await self._billing.bonus(
                user_id=user_id,
                amount=plan_info.credits_per_month,
                reason="subscription_grant",
                description=f"Subscription grant: {plan_info.name} ({plan})",
                related_id=sub.id,
                related_type="subscription",
            )

        # Invalidate subscription cache (covers new subscribe + plan switch)
        from app.core.cache import get_cache_service
        cache = await get_cache_service()
        await cache.invalidate_pattern(f"user:{user_id}:subscription")

        return sub

    async def cancel(self, subscription_id: UUID, user_id: UUID) -> Subscription:
        """Cancel a subscription. Marks as cancelled, sets cancelled_at.

        Raises:
            ValueError: If subscription not found or doesn't belong to user.
        """
        result = await self.db.execute(
            select(Subscription).where(
                Subscription.id == subscription_id,
                Subscription.user_id == user_id,
            )
        )
        sub = result.scalar_one_or_none()
        if sub is None:
            raise ValueError(
                f"Subscription {subscription_id} not found for user {user_id}"
            )
        sub.status = "cancelled"
        sub.cancelled_at = datetime.now(timezone.utc)
        sub.auto_renew = False
        await self.db.flush()
        await self.db.refresh(sub)

        # Invalidate subscription cache
        from app.core.cache import get_cache_service
        cache = await get_cache_service()
        await cache.invalidate_pattern(f"user:{user_id}:subscription")

        return sub

    async def cancel_renewal(
        self, subscription_id: UUID, user_id: UUID
    ) -> Subscription:
        """Disable future renewal without revoking the already-paid period."""
        result = await self.db.execute(
            select(Subscription).where(
                Subscription.id == subscription_id,
                Subscription.user_id == user_id,
                Subscription.status == "active",
            )
        )
        sub = result.scalar_one_or_none()
        if sub is None:
            raise ValueError(
                f"Active subscription {subscription_id} not found for user {user_id}"
            )
        sub.auto_renew = False
        await self.db.flush()
        await self.db.refresh(sub)

        from app.core.cache import get_cache_service
        cache = await get_cache_service()
        await cache.invalidate_pattern(f"user:{user_id}:subscription")
        return sub

    @cached(ttl=60, key=lambda self, user_id: f"user:{user_id}:subscription")
    async def get_active(self, user_id: UUID) -> Optional[Subscription]:
        """Get user's currently active subscription (not cancelled, not expired).

        Cached for 60s; invalidated on subscribe/cancel.
        """
        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            select(Subscription).where(
                Subscription.user_id == user_id,
                Subscription.status == "active",
                Subscription.expires_at > now,
            ).order_by(Subscription.created_at.desc())
        )
        return result.scalar_one_or_none()
