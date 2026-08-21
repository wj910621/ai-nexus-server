"""Payment schemas."""
from typing import Literal, Optional

from pydantic import BaseModel, Field


class CreatePaymentIntentRequest(BaseModel):
    """Request to create a payment intent."""
    plan: str = Field(..., description="Plan to subscribe: pro/enterprise")
    duration_days: int = Field(default=30, ge=1, le=365)
    auto_renew: bool = False
    terms_accepted: Literal[True]
    digital_service_no_refund_acknowledged: Literal[True]


class PaymentIntentResponse(BaseModel):
    """Payment intent created by provider."""
    intent_id: str
    client_secret: str
    amount_cents: int
    currency: str
    status: str
    provider: str  # mock/stripe


class ConfirmPaymentRequest(BaseModel):
    """Request to confirm a payment."""
    intent_id: str
    payment_method: Optional[str] = None  # Stripe payment method


class PaymentConfirmResponse(BaseModel):
    """Payment confirmation result."""
    intent_id: str
    status: str  # succeeded/failed
    amount_cents: int
    subscription_activated: bool = False


class WebhookEvent(BaseModel):
    """Generic webhook event (provider-agnostic)."""
    type: str
    data: dict
