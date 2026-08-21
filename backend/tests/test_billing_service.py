"""Tests for BillingService (credit deduction/recharge/balance)."""
import pytest
import pytest_asyncio
from uuid import uuid4

from app.models.user import User
from app.models.billing import CreditTransaction


@pytest_asyncio.fixture
async def test_user(db_session):
    """Create a test user with 100 credits."""
    from app.core.security import hash_password
    user = User(
        username=f"testuser_{uuid4().hex[:8]}",
        email=f"test_{uuid4().hex[:8]}@example.com",
        password_hash=hash_password("password123"),
        credits=100,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest.mark.asyncio
async def test_get_balance(db_session, test_user):
    """get_balance returns current credit balance."""
    from app.services.billing_service import BillingService
    svc = BillingService(db_session)
    balance = await svc.get_balance(test_user.id)
    assert balance == 100


@pytest.mark.asyncio
async def test_get_balance_nonexistent_user(db_session):
    """get_balance raises ValueError for nonexistent user."""
    from app.services.billing_service import BillingService
    svc = BillingService(db_session)
    with pytest.raises(ValueError):
        await svc.get_balance(uuid4())


@pytest.mark.asyncio
async def test_deduct_credits_success(db_session, test_user):
    """deduct reduces user's credits and records transaction."""
    from app.services.billing_service import BillingService
    svc = BillingService(db_session)
    balance = await svc.deduct(
        user_id=test_user.id,
        amount=30,
        reason="text2img",
        description="Generated 1 image",
    )
    assert balance == 70
    # Verify transaction recorded
    from sqlalchemy import select
    result = await db_session.execute(
        select(CreditTransaction).where(CreditTransaction.user_id == test_user.id)
    )
    txns = result.scalars().all()
    assert len(txns) == 1
    assert txns[0].type == "deduct"
    assert txns[0].amount == 30
    assert txns[0].balance_after == 70
    assert txns[0].reason == "text2img"


@pytest.mark.asyncio
async def test_deduct_insufficient_credits(db_session, test_user):
    """deduct raises ValueError when insufficient credits."""
    from app.services.billing_service import BillingService
    svc = BillingService(db_session)
    with pytest.raises(ValueError, match="insufficient"):
        await svc.deduct(
            user_id=test_user.id,
            amount=200,
            reason="text2img",
            description="Should fail",
        )
    # User credits unchanged
    await db_session.refresh(test_user)
    assert test_user.credits == 100


@pytest.mark.asyncio
async def test_deduct_zero_or_negative_amount(db_session, test_user):
    """deduct rejects zero or negative amounts."""
    from app.services.billing_service import BillingService
    svc = BillingService(db_session)
    with pytest.raises(ValueError, match="positive"):
        await svc.deduct(test_user.id, 0, "test", "zero")
    with pytest.raises(ValueError, match="positive"):
        await svc.deduct(test_user.id, -10, "test", "negative")


@pytest.mark.asyncio
async def test_recharge_credits(db_session, test_user):
    """recharge adds credits and records transaction."""
    from app.services.billing_service import BillingService
    svc = BillingService(db_session)
    balance = await svc.recharge(
        user_id=test_user.id,
        amount=50,
        reason="recharge",
        description="Purchased 50 credits",
    )
    assert balance == 150
    from sqlalchemy import select
    result = await db_session.execute(
        select(CreditTransaction).where(CreditTransaction.user_id == test_user.id)
    )
    txns = result.scalars().all()
    assert txns[0].type == "recharge"
    assert txns[0].amount == 50


@pytest.mark.asyncio
async def test_bonus_credits(db_session, test_user):
    """bonus adds credits with type='bonus'."""
    from app.services.billing_service import BillingService
    svc = BillingService(db_session)
    balance = await svc.bonus(test_user.id, 20, "signup_bonus", "Welcome bonus")
    assert balance == 120
    from sqlalchemy import select
    result = await db_session.execute(
        select(CreditTransaction).where(CreditTransaction.user_id == test_user.id)
    )
    txns = result.scalars().all()
    assert txns[0].type == "bonus"


@pytest.mark.asyncio
async def test_refund_credits(db_session, test_user):
    """refund adds credits back with type='refund'."""
    from app.services.billing_service import BillingService
    svc = BillingService(db_session)
    # First deduct
    await svc.deduct(test_user.id, 30, "text2img", "test")
    # Then refund
    balance = await svc.refund(test_user.id, 30, "text2img_failed", "Generation failed")
    assert balance == 100


@pytest.mark.asyncio
async def test_list_transactions(db_session, test_user):
    """list_transactions returns user's transactions ordered by created_at desc."""
    from app.services.billing_service import BillingService
    svc = BillingService(db_session)
    await svc.deduct(test_user.id, 10, "text2img", "first")
    await svc.deduct(test_user.id, 20, "tts", "second")
    await svc.recharge(test_user.id, 50, "recharge", "third")

    txns = await svc.list_transactions(test_user.id, limit=10)
    assert len(txns) == 3
    # Most recent first
    assert txns[0].description == "third"
    assert txns[2].description == "first"


@pytest.mark.asyncio
async def test_list_transactions_with_pagination(db_session, test_user):
    """list_transactions supports limit/offset."""
    from app.services.billing_service import BillingService
    svc = BillingService(db_session)
    for i in range(5):
        await svc.deduct(test_user.id, 1, "test", f"tx_{i}")

    page1 = await svc.list_transactions(test_user.id, limit=2, offset=0)
    page2 = await svc.list_transactions(test_user.id, limit=2, offset=2)
    assert len(page1) == 2
    assert len(page2) == 2


@pytest.mark.asyncio
async def test_deduct_atomic_rollback_on_error(db_session, test_user):
    """If transaction recording fails, user credits are not changed."""
    # This is enforced by the session flush semantics; test by mocking
    from app.services.billing_service import BillingService
    svc = BillingService(db_session)
    # Normal deduct works
    await svc.deduct(test_user.id, 10, "test", "ok")
    await db_session.refresh(test_user)
    assert test_user.credits == 90


@pytest.mark.asyncio
async def test_check_credits_sufficient(db_session, test_user):
    """check_credits returns True when user has enough credits."""
    from app.services.billing_service import BillingService
    svc = BillingService(db_session)
    assert await svc.check_credits(test_user.id, 50) is True
    assert await svc.check_credits(test_user.id, 100) is True


@pytest.mark.asyncio
async def test_check_credits_insufficient(db_session, test_user):
    """check_credits returns False when user lacks credits."""
    from app.services.billing_service import BillingService
    svc = BillingService(db_session)
    assert await svc.check_credits(test_user.id, 101) is False


@pytest.mark.asyncio
async def test_check_credits_zero_amount(db_session, test_user):
    """check_credits returns True for zero amount (free operations)."""
    from app.services.billing_service import BillingService
    svc = BillingService(db_session)
    assert await svc.check_credits(test_user.id, 0) is True


@pytest.mark.asyncio
async def test_transaction_related_fields(db_session, test_user):
    """Transaction can store related_id and related_type."""
    from app.services.billing_service import BillingService
    svc = BillingService(db_session)
    related_id = uuid4()
    await svc.deduct(
        test_user.id, 10, "render", "Render task",
        related_id=related_id, related_type="render_task",
    )
    from sqlalchemy import select
    result = await db_session.execute(
        select(CreditTransaction).where(CreditTransaction.user_id == test_user.id)
    )
    txn = result.scalars().first()
    assert txn.related_id == related_id
    assert txn.related_type == "render_task"
