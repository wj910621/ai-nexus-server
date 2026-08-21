"""Billing service - credit accounting.

All credit operations (deduct/recharge/bonus/refund) are atomic: user balance
is updated AND a CreditTransaction record is created in the same flush.
"""
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache_decorator import cached
from app.models.base import utc_now
from app.models.billing import CreditTransaction
from app.models.user import User
from app.services.base_service import BaseService


class BillingService(BaseService[CreditTransaction]):
    """Credit accounting service."""

    model = CreditTransaction

    def __init__(self, db: AsyncSession):
        super().__init__(db)

    @cached(ttl=30, key=lambda self, user_id: f"user:{user_id}:balance")
    async def get_balance(self, user_id: UUID) -> int:
        """Get user's current credit balance (cached 30s). Raises ValueError if user missing.

        Cache invalidated on deduct/recharge/bonus/refund.
        """
        result = await self.db.execute(
            select(User.credits).where(User.id == user_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            raise ValueError(f"User {user_id} not found")
        return row

    async def check_credits(self, user_id: UUID, amount: int) -> bool:
        """Check if user has at least `amount` credits. Zero always returns True."""
        if amount <= 0:
            return True
        balance = await self.get_balance(user_id)
        return balance >= amount

    async def deduct(
        self,
        user_id: UUID,
        amount: int,
        reason: str,
        description: str = "",
        related_id: Optional[UUID] = None,
        related_type: Optional[str] = None,
    ) -> int:
        """Deduct credits from user. Returns new balance. Raises ValueError on insufficient.

        Args:
            user_id: User to deduct from
            amount: Positive integer credits to deduct
            reason: Short reason code (e.g. 'text2img', 'tts', 'render')
            description: Human-readable description
            related_id: Optional related entity ID (e.g. render task ID)
            related_type: Optional related entity type
        """
        if amount <= 0:
            raise ValueError("Amount must be positive")

        # Lock user row and check balance
        result = await self.db.execute(
            select(User).where(User.id == user_id).with_for_update()
        )
        user = result.scalar_one_or_none()
        if user is None:
            raise ValueError(f"User {user_id} not found")
        if user.credits < amount:
            raise ValueError(
                f"insufficient credits: have {user.credits}, need {amount}"
            )

        # Update balance
        new_balance = user.credits - amount
        user.credits = new_balance
        await self.db.flush()

        # Record transaction
        txn = CreditTransaction(
            user_id=user_id,
            type="deduct",
            amount=amount,
            balance_after=new_balance,
            reason=reason,
            description=description,
            related_id=related_id,
            related_type=related_type,
            created_at=await self._next_transaction_time(user_id),
        )
        self.db.add(txn)
        await self.db.flush()

        # Invalidate balance cache
        from app.core.cache import get_cache_service
        cache = await get_cache_service()
        await cache.invalidate_pattern(f"user:{user_id}:balance")

        return new_balance

    async def recharge(
        self,
        user_id: UUID,
        amount: int,
        reason: str = "recharge",
        description: str = "",
        related_id: Optional[UUID] = None,
        related_type: Optional[str] = None,
    ) -> int:
        """Recharge credits (paid purchase). Returns new balance."""
        return await self._add_credits(
            user_id, amount, "recharge", reason, description,
            related_id, related_type,
        )

    async def bonus(
        self,
        user_id: UUID,
        amount: int,
        reason: str = "bonus",
        description: str = "",
        related_id: Optional[UUID] = None,
        related_type: Optional[str] = None,
    ) -> int:
        """Add bonus credits (free, e.g. signup bonus). Returns new balance."""
        return await self._add_credits(
            user_id, amount, "bonus", reason, description,
            related_id, related_type,
        )

    async def refund(
        self,
        user_id: UUID,
        amount: int,
        reason: str = "refund",
        description: str = "",
        related_id: Optional[UUID] = None,
        related_type: Optional[str] = None,
    ) -> int:
        """Refund credits (failed operation). Returns new balance."""
        return await self._add_credits(
            user_id, amount, "refund", reason, description,
            related_id, related_type,
        )

    async def _add_credits(
        self,
        user_id: UUID,
        amount: int,
        txn_type: str,
        reason: str,
        description: str,
        related_id: Optional[UUID] = None,
        related_type: Optional[str] = None,
    ) -> int:
        """Internal helper: add credits and record transaction."""
        if amount <= 0:
            raise ValueError("Amount must be positive")

        result = await self.db.execute(
            select(User).where(User.id == user_id).with_for_update()
        )
        user = result.scalar_one_or_none()
        if user is None:
            raise ValueError(f"User {user_id} not found")

        new_balance = user.credits + amount
        user.credits = new_balance
        await self.db.flush()

        txn = CreditTransaction(
            user_id=user_id,
            type=txn_type,
            amount=amount,
            balance_after=new_balance,
            reason=reason,
            description=description,
            related_id=related_id,
            related_type=related_type,
            created_at=await self._next_transaction_time(user_id),
        )
        self.db.add(txn)
        await self.db.flush()

        # Invalidate balance cache (covers recharge/bonus/refund)
        from app.core.cache import get_cache_service
        cache = await get_cache_service()
        await cache.invalidate_pattern(f"user:{user_id}:balance")

        return new_balance

    async def list_transactions(
        self,
        user_id: UUID,
        limit: int = 20,
        offset: int = 0,
    ) -> List[CreditTransaction]:
        """List user's transactions, newest first."""
        result = await self.db.execute(
            select(CreditTransaction)
            .where(CreditTransaction.user_id == user_id)
            .order_by(
                CreditTransaction.created_at.desc(),
                CreditTransaction.id.desc(),
            )
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def _next_transaction_time(self, user_id: UUID) -> datetime:
        """Return a strictly increasing ledger timestamp for one user.

        Windows and some databases expose clocks with millisecond resolution.
        The user row is already locked by callers, so advancing ties by one
        microsecond gives deterministic pagination and audit ordering.
        """
        latest = await self.db.scalar(
            select(func.max(CreditTransaction.created_at)).where(
                CreditTransaction.user_id == user_id
            )
        )
        now = utc_now()
        if latest is not None and now <= latest:
            return latest + timedelta(microseconds=1)
        return now

    async def _notify_user_low_credit(
        self, user_id: UUID, current_credits: int, threshold: int
    ) -> None:
        """额度低通知 - 通过 WS 推送给用户私人频道。"""
        from app.core.ws_manager import ws_manager
        now = datetime.now(timezone.utc)
        try:
            await ws_manager.publish(f"user:{user_id}", {
                "type": "notification",
                "data": {
                    "id": f"credit_low_{user_id}_{int(now.timestamp())}",
                    "type": "credit_low",
                    "title": "额度不足",
                    "body": f"本月生成额度已用 {int(current_credits / threshold * 100)}%",
                    "createdAt": int(now.timestamp() * 1000),
                    "read": False,
                },
            })
        except Exception:
            pass

    async def _notify_user_subscription_expiring(
        self, user_id: UUID, days_left: int
    ) -> None:
        """订阅即将到期通知 - 通过 WS 推送给用户私人频道。"""
        from app.core.ws_manager import ws_manager
        now = datetime.now(timezone.utc)
        try:
            await ws_manager.publish(f"user:{user_id}", {
                "type": "notification",
                "data": {
                    "id": f"sub_expiring_{user_id}_{int(now.timestamp())}",
                    "type": "subscription_expiring",
                    "title": "订阅到期",
                    "body": f"Pro 订阅 {days_left} 天后到期",
                    "createdAt": int(now.timestamp() * 1000),
                    "read": False,
                },
            })
        except Exception:
            pass
