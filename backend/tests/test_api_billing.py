"""Tests for AI endpoint credit deduction integration."""
import pytest
import pytest_asyncio
from uuid import uuid4


# Credit costs per AI operation (must match ai.py CREDIT_COSTS)
CREDIT_COSTS = {
    "text2img": 10,
    "tts": 5,
    "chat": 1,
    "video_compose": 50,
    "character_generate": 30,
}


@pytest.mark.asyncio
async def test_credit_costs_table_complete():
    """CREDIT_COSTS covers all AI operations."""
    from app.api.ai import CREDIT_COSTS
    assert "text2img" in CREDIT_COSTS
    assert "tts" in CREDIT_COSTS
    assert "chat" in CREDIT_COSTS
    assert "video_compose" in CREDIT_COSTS
    assert "character_generate" in CREDIT_COSTS
    # All costs positive
    for op, cost in CREDIT_COSTS.items():
        assert cost > 0, f"{op} cost must be positive"


@pytest.mark.asyncio
async def test_check_and_deduct_credits_sufficient(db_session):
    """check_and_deduct_credits succeeds when user has enough credits."""
    from app.models.user import User
    from app.core.security import hash_password
    from app.api.ai import check_and_deduct_credits

    user = User(
        username=f"credittest_{uuid4().hex[:8]}",
        email=f"cr_{uuid4().hex[:8]}@example.com",
        password_hash=hash_password("password123"),
        credits=100,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)

    new_balance = await check_and_deduct_credits(db_session, user, "text2img")
    assert new_balance == 90  # 100 - 10


@pytest.mark.asyncio
async def test_check_and_deduct_credits_insufficient(db_session):
    """check_and_deduct_credits raises HTTPException when insufficient."""
    from app.models.user import User
    from app.core.security import hash_password
    from app.api.ai import check_and_deduct_credits
    from fastapi import HTTPException

    user = User(
        username=f"poor_{uuid4().hex[:8]}",
        email=f"poor_{uuid4().hex[:8]}@example.com",
        password_hash=hash_password("password123"),
        credits=5,  # Not enough for text2img (costs 10)
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)

    with pytest.raises(HTTPException) as exc_info:
        await check_and_deduct_credits(db_session, user, "text2img")
    assert exc_info.value.status_code == 402  # Payment Required
    # User credits unchanged
    await db_session.refresh(user)
    assert user.credits == 5


@pytest.mark.asyncio
async def test_check_and_deduct_credits_unknown_operation(db_session):
    """check_and_deduct_credits raises ValueError for unknown operation."""
    from app.models.user import User
    from app.core.security import hash_password
    from app.api.ai import check_and_deduct_credits

    user = User(
        username=f"unk_{uuid4().hex[:8]}",
        email=f"unk_{uuid4().hex[:8]}@example.com",
        password_hash=hash_password("password123"),
        credits=100,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)

    with pytest.raises(ValueError):
        await check_and_deduct_credits(db_session, user, "unknown_op")


@pytest.mark.asyncio
async def test_check_and_deduct_credits_records_transaction(db_session):
    """check_and_deduct_credits records a CreditTransaction."""
    from app.models.user import User
    from app.models.billing import CreditTransaction
    from app.core.security import hash_password
    from app.api.ai import check_and_deduct_credits
    from sqlalchemy import select

    user = User(
        username=f"txntest_{uuid4().hex[:8]}",
        email=f"txn_{uuid4().hex[:8]}@example.com",
        password_hash=hash_password("password123"),
        credits=100,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)

    await check_and_deduct_credits(db_session, user, "tts")
    result = await db_session.execute(
        select(CreditTransaction).where(CreditTransaction.user_id == user.id)
    )
    txns = result.scalars().all()
    assert len(txns) == 1
    assert txns[0].amount == 5
    assert txns[0].reason == "tts"


@pytest.mark.asyncio
async def test_refund_on_failure(db_session):
    """refund_credits adds credits back."""
    from app.models.user import User
    from app.core.security import hash_password
    from app.api.ai import refund_credits

    user = User(
        username=f"reftest_{uuid4().hex[:8]}",
        email=f"ref_{uuid4().hex[:8]}@example.com",
        password_hash=hash_password("password123"),
        credits=100,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)

    await refund_credits(db_session, user, 10, reason="failure_refund")
    await db_session.refresh(user)
    assert user.credits == 110


@pytest.mark.asyncio
async def test_check_and_deduct_credits_admin_free(db_session):
    """Admin users (role == 'admin') bypass credit deduction."""
    from app.models.user import User
    from app.core.security import hash_password
    from app.api.ai import check_and_deduct_credits

    user = User(
        username=f"admintest_{uuid4().hex[:8]}",
        email=f"admin_{uuid4().hex[:8]}@example.com",
        password_hash=hash_password("password123"),
        credits=0,
        role="admin",
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)

    await check_and_deduct_credits(db_session, user, "text2img")
    await db_session.refresh(user)
    assert user.credits == 0


@pytest.mark.asyncio
async def test_check_and_deduct_credits_text2img(db_session):
    """text2img costs 10 credits."""
    from app.models.user import User
    from app.core.security import hash_password
    from app.api.ai import check_and_deduct_credits

    user = User(
        username=f"imgtest_{uuid4().hex[:8]}",
        email=f"img_{uuid4().hex[:8]}@example.com",
        password_hash=hash_password("password123"),
        credits=100,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)

    await check_and_deduct_credits(db_session, user, "text2img")
    await db_session.refresh(user)
    assert user.credits == 90


@pytest.mark.asyncio
async def test_check_and_deduct_credits_video_compose(db_session):
    """video_compose costs 50 credits."""
    from app.models.user import User
    from app.core.security import hash_password
    from app.api.ai import check_and_deduct_credits

    user = User(
        username=f"vidtest_{uuid4().hex[:8]}",
        email=f"vid_{uuid4().hex[:8]}@example.com",
        password_hash=hash_password("password123"),
        credits=100,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)

    await check_and_deduct_credits(db_session, user, "video_compose")
    await db_session.refresh(user)
    assert user.credits == 50


@pytest.mark.asyncio
async def test_production_blocks_unpublished_commercial_operations(db_session, monkeypatch):
    """An unpublished catalog must fail before any local or shared-ledger debit."""
    from fastapi import HTTPException

    from app.api.ai import check_and_deduct_credits
    from app.core.config import settings
    from app.core.security import hash_password
    from app.models.user import User

    user = User(
        username=f"blocked_{uuid4().hex[:8]}",
        email=f"blocked_{uuid4().hex[:8]}@example.com",
        password_hash=hash_password("password123"),
        credits=100,
    )
    db_session.add(user)
    await db_session.flush()

    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "commercial_operations_enabled", False)
    with pytest.raises(HTTPException) as exc:
        await check_and_deduct_credits(db_session, user, "text2img")

    assert exc.value.status_code == 503
    await db_session.refresh(user)
    assert user.credits == 100
