"""Payments API - create intent, confirm, webhook."""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_current_user, get_db
from app.core.response import ApiResponse
from app.models.billing import PurchaseConsent
from app.models.user import User
from app.schemas.payment import (
    ConfirmPaymentRequest,
    CreatePaymentIntentRequest,
    PaymentConfirmResponse,
    PaymentIntentResponse,
)
from app.services.payment_service import PaymentService
from app.services.subscription_service import PLAN_DEFINITIONS

router = APIRouter(prefix="/payments", tags=["支付"])


TERMS_VERSION = "2026-07-22"
REFUND_POLICY_VERSION = "2026-07-22"


@router.post("/intent", response_model=ApiResponse[PaymentIntentResponse])
async def create_payment_intent(
    payload: CreatePaymentIntentRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a payment intent for subscribing to a plan."""
    if settings.billing_mode == "jarvis":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Purchases are managed by the YNEX/Jarvis main site",
                "portal_url": settings.jarvis_billing_portal_url,
            },
        )
    plan_info = PLAN_DEFINITIONS.get(payload.plan)
    if plan_info is None or payload.plan == "free":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的付费计划",
        )
    if payload.auto_renew:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Automatic renewal is not available yet",
        )

    svc = PaymentService()
    intent = await svc.create_intent(
        amount_cents=plan_info.price_cents,
        currency="cny",
        metadata={
            "user_id": str(current_user.id),
            "plan": payload.plan,
            "duration_days": str(payload.duration_days),
            "auto_renew": str(payload.auto_renew).lower(),
            "terms_version": TERMS_VERSION,
            "refund_policy_version": REFUND_POLICY_VERSION,
        },
    )
    db.add(PurchaseConsent(
        user_id=current_user.id,
        payment_intent_id=intent["id"],
        plan=payload.plan,
        terms_version=TERMS_VERSION,
        refund_policy_version=REFUND_POLICY_VERSION,
        terms_accepted=payload.terms_accepted,
        digital_service_acknowledged=payload.digital_service_no_refund_acknowledged,
    ))
    await db.flush()
    return ApiResponse.success(
        data=PaymentIntentResponse(
            intent_id=intent["id"],
            client_secret=intent["client_secret"],
            amount_cents=intent["amount"],
            currency=intent["currency"],
            status=intent["status"],
            provider=svc.provider_name,
        )
    )


@router.post("/confirm", response_model=ApiResponse[PaymentConfirmResponse])
async def confirm_payment(
    payload: ConfirmPaymentRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Confirm a payment and activate subscription."""
    if settings.billing_mode == "jarvis":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Payment confirmation is managed by the YNEX/Jarvis main site",
        )
    svc = PaymentService()
    try:
        result = await svc.confirm_payment(payload.intent_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    if result["status"] != "succeeded":
        return ApiResponse.success(
            data=PaymentConfirmResponse(
                intent_id=result["id"],
                status=result["status"],
                amount_cents=result["amount"],
                subscription_activated=False,
            ),
            message="支付未成功",
        )

    metadata = result.get("metadata", {})
    if metadata.get("user_id") != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
    plan = metadata.get("plan")
    plan_info = PLAN_DEFINITIONS.get(plan)
    if (
        plan_info is None
        or plan == "free"
        or result.get("amount") != plan_info.price_cents
        or result.get("currency") != "cny"
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment does not match the plan catalog",
        )

    # Production activation is webhook-only to avoid a confirm/webhook race.
    if svc.provider_name != "mock":
        return ApiResponse.success(
            data=PaymentConfirmResponse(
                intent_id=result["id"],
                status="succeeded",
                amount_cents=result["amount"],
                subscription_activated=False,
            ),
            message="Payment verified; subscription activation is processing",
        )

    # Desktop/development mock activation is synchronous.
    from app.services.subscription_service import SubscriptionService
    sub_svc = SubscriptionService(db)
    try:
        await sub_svc.subscribe(
            user_id=current_user.id,
            plan=plan,
            duration_days=int(metadata.get("duration_days", "30")),
            payment_method=svc.provider_name,
            payment_id=result["id"],
        )
        activated = True
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Payment succeeded but subscription activation failed",
        ) from exc

    return ApiResponse.success(
        data=PaymentConfirmResponse(
            intent_id=result["id"],
            status="succeeded",
            amount_cents=result["amount"],
            subscription_activated=activated,
        ),
        message="支付成功" if activated else "支付成功但订阅激活失败",
    )


@router.post("/webhook", response_model=ApiResponse)
async def payment_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Stripe webhook endpoint (no auth - verified by signature)."""
    if settings.billing_mode == "jarvis":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")

    svc = PaymentService()
    try:
        event = await svc.parse_webhook_event(payload, signature)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    handled = await svc.handle_event(event, db)
    return ApiResponse.success(data={"handled": handled})
