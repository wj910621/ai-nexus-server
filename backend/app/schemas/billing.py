"""Billing schemas (credits, transactions)."""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class CreditBalanceResponse(BaseModel):
    """User's current credit balance."""
    user_id: UUID
    credits: int
    plan: str


class DeductRequest(BaseModel):
    """Internal request to deduct credits (not exposed via API)."""
    amount: int = Field(..., gt=0, description="Credits to deduct")
    reason: str = Field(..., max_length=50, description="Reason code (e.g. 'text2img')")
    description: str = Field(default="", max_length=200)
    related_id: Optional[UUID] = None
    related_type: Optional[str] = None


class RechargeRequest(BaseModel):
    """Request to recharge credits (admin or payment-triggered)."""
    amount: int = Field(..., gt=0)
    reason: str = Field(default="recharge", max_length=50)
    description: str = Field(default="", max_length=200)


class CreditTransactionResponse(ORMModel):
    """A single credit transaction record."""
    id: UUID
    user_id: UUID
    type: str  # recharge/deduct/bonus/refund
    amount: int
    balance_after: int
    reason: Optional[str] = None
    description: Optional[str] = None
    related_id: Optional[UUID] = None
    related_type: Optional[str] = None
    created_at: datetime


class TransactionListResponse(BaseModel):
    """Paginated transaction list."""
    items: list[CreditTransactionResponse]
    total: int
    page: int = 1
    page_size: int = 20
