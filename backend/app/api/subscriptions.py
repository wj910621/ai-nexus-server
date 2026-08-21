"""Subscription query and renewal-management API."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.core.response import ApiResponse
from app.models.user import User
from app.schemas.subscription import (
    CancelRequest,
    PlanListResponse,
    SubscribeRequest,
    SubscriptionResponse,
)
from app.services.subscription_service import SubscriptionService

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


@router.get("/plans", response_model=ApiResponse[PlanListResponse])
async def list_plans():
    from app.services.subscription_service import PLAN_DEFINITIONS
    return ApiResponse.success(
        data=PlanListResponse(plans=list(PLAN_DEFINITIONS.values()))
    )


@router.get("/current", response_model=ApiResponse[SubscriptionResponse])
async def get_current_subscription(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sub = await SubscriptionService(db).get_active(current_user.id)
    if sub is None:
        return ApiResponse.success(data=None, message="No active subscription")
    return ApiResponse.success(data=SubscriptionResponse.model_validate(sub))


@router.post("/subscribe", response_model=ApiResponse[SubscriptionResponse])
async def subscribe(
    payload: SubscribeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Reject legacy client-side activation.

    Free entitlement is assigned when an account is created. Paid entitlement
    is created only by the verified payment webhook. This also prevents callers
    from repeatedly activating a free plan to farm bonus credits.
    """
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="Direct subscription activation is disabled; use the payment flow",
    )


@router.post("/cancel", response_model=ApiResponse[SubscriptionResponse])
async def cancel_subscription(
    payload: CancelRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Stop renewal while preserving already-paid access until expiry."""
    svc = SubscriptionService(db)
    active = await svc.get_active(current_user.id)
    if active is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active subscription to cancel",
        )
    cancelled = await svc.cancel_renewal(active.id, user_id=current_user.id)
    return ApiResponse.success(
        data=SubscriptionResponse.model_validate(cancelled),
        message="Automatic renewal disabled; access remains until expiry",
    )
