"""Subscription schemas."""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class PlanInfo(BaseModel):
    """A subscription plan definition."""
    plan_id: str  # free/pro/enterprise
    name: str
    price_cents: int  # monthly price in cents (0 for free)
    credits_per_month: int
    max_projects: int  # 0 = unlimited
    max_render_resolution: int  # e.g. 1080, 2160
    features: list[str]  # human-readable feature list
    is_popular: bool = False


class PlanListResponse(BaseModel):
    """List of all available plans."""
    plans: list[PlanInfo]


class SubscribeRequest(BaseModel):
    """Request to subscribe to a plan."""
    plan: str = Field(..., description="Plan ID: free/pro/enterprise")
    duration_days: int = Field(default=30, ge=1, le=365)
    payment_method: Optional[str] = None
    payment_id: Optional[str] = None
    auto_renew: bool = False


class CancelRequest(BaseModel):
    """Request to cancel subscription."""
    reason: Optional[str] = Field(default=None, max_length=200)


class SubscriptionResponse(ORMModel):
    """A subscription record."""
    id: UUID
    user_id: UUID
    plan: str
    status: str
    started_at: datetime
    expires_at: datetime
    cancelled_at: Optional[datetime] = None
    amount: Optional[int] = None
    payment_method: Optional[str] = None
    payment_id: Optional[str] = None
    auto_renew: bool = False
    created_at: datetime
