"""Billing API - credit balance and transaction history."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_current_user, get_db
from app.core.response import ApiResponse
from app.models.user import User
from app.schemas.billing import (
    CreditBalanceResponse,
    CreditTransactionResponse,
    TransactionListResponse,
)
from app.services.billing_service import BillingService

router = APIRouter(prefix="/billing", tags=["计费"])


@router.get("/balance", response_model=ApiResponse[CreditBalanceResponse])
async def get_balance(
    current_user: User = Depends(get_current_user),
):
    """Get current user's credit balance."""
    if settings.billing_mode == "jarvis":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authoritative balance is held by YNEX/Jarvis; use the main-site account center",
        )
    return ApiResponse.success(
        data=CreditBalanceResponse(
            user_id=current_user.id,
            credits=current_user.credits,
            plan=current_user.plan,
        )
    )


@router.get("/transactions", response_model=ApiResponse[TransactionListResponse])
async def list_transactions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List current user's credit transactions (newest first)."""
    if settings.billing_mode == "jarvis":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authoritative transactions are held by YNEX/Jarvis",
        )
    svc = BillingService(db)
    offset = (page - 1) * page_size
    items = await svc.list_transactions(current_user.id, limit=page_size, offset=offset)

    # Count total
    from sqlalchemy import func, select

    from app.models.billing import CreditTransaction
    count_result = await db.execute(
        select(func.count(CreditTransaction.id)).where(
            CreditTransaction.user_id == current_user.id
        )
    )
    total = count_result.scalar_one()

    return ApiResponse.success(
        data=TransactionListResponse(
            items=[CreditTransactionResponse.model_validate(t) for t in items],
            total=total,
            page=page,
            page_size=page_size,
        )
    )
