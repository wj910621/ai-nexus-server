"""Tests for SubscriptionService."""
import pytest
import pytest_asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.models.user import User
from app.models.billing import Subscription


@pytest_asyncio.fixture
async def test_user(db_session):
    from app.core.security import hash_password
    user = User(
        username=f"subuser_{uuid4().hex[:8]}",
        email=f"sub_{uuid4().hex[:8]}@example.com",
        password_hash=hash_password("password123"),
        plan="free",
        credits=100,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest.mark.asyncio
async def test_list_plans(db_session):
    """list_plans returns all available plans with correct fields."""
    from app.services.subscription_service import SubscriptionService, PLAN_DEFINITIONS
    svc = SubscriptionService(db_session)
    plans = svc.list_plans()
    assert len(plans) >= 3
    plan_ids = {p.plan_id for p in plans}
    assert {"free", "pro", "enterprise"} <= plan_ids
    # Free plan has 0 price
    free_plan = next(p for p in plans if p.plan_id == "free")
    assert free_plan.price_cents == 0
    assert free_plan.credits_per_month > 0


@pytest.mark.asyncio
async def test_get_plan_info(db_session):
    """get_plan_info returns specific plan details."""
    from app.services.subscription_service import SubscriptionService
    svc = SubscriptionService(db_session)
    pro = svc.get_plan_info("pro")
    assert pro is not None
    assert pro.plan_id == "pro"
    assert pro.price_cents > 0


@pytest.mark.asyncio
async def test_get_plan_info_nonexistent(db_session):
    """get_plan_info returns None for unknown plan."""
    from app.services.subscription_service import SubscriptionService
    svc = SubscriptionService(db_session)
    assert svc.get_plan_info("nonexistent") is None


@pytest.mark.asyncio
async def test_subscribe_user_to_pro(db_session, test_user):
    """subscribe creates a Subscription and updates user.plan."""
    from app.services.subscription_service import SubscriptionService
    svc = SubscriptionService(db_session)
    sub = await svc.subscribe(
        user_id=test_user.id,
        plan="pro",
        duration_days=30,
        payment_method="stripe",
        payment_id="pi_test_123",
    )
    assert sub.plan == "pro"
    assert sub.status == "active"
    assert sub.user_id == test_user.id
    # User's plan should be updated
    await db_session.refresh(test_user)
    assert test_user.plan == "pro"
    assert test_user.plan_expires_at is not None


@pytest.mark.asyncio
async def test_subscribe_credits_granted(db_session, test_user):
    """subscribe grants monthly credits to user."""
    from app.services.subscription_service import SubscriptionService, PLAN_DEFINITIONS
    svc = SubscriptionService(db_session)
    initial_credits = test_user.credits
    await svc.subscribe(test_user.id, "pro", duration_days=30)
    await db_session.refresh(test_user)
    pro_credits = PLAN_DEFINITIONS["pro"].credits_per_month
    assert test_user.credits == initial_credits + pro_credits


@pytest.mark.asyncio
async def test_subscribe_unknown_plan_raises(db_session, test_user):
    """subscribe raises ValueError for unknown plan."""
    from app.services.subscription_service import SubscriptionService
    svc = SubscriptionService(db_session)
    with pytest.raises(ValueError, match="Unknown plan"):
        await svc.subscribe(test_user.id, "platinum", duration_days=30)


@pytest.mark.asyncio
async def test_subscribe_creates_credit_transaction(db_session, test_user):
    """subscribe grants credits via BillingService (records transaction)."""
    from app.services.subscription_service import SubscriptionService
    from app.models.billing import CreditTransaction
    from sqlalchemy import select
    svc = SubscriptionService(db_session)
    await svc.subscribe(test_user.id, "pro", duration_days=30)
    result = await db_session.execute(
        select(CreditTransaction).where(CreditTransaction.user_id == test_user.id)
    )
    txns = result.scalars().all()
    assert len(txns) == 1
    assert txns[0].type == "bonus"
    assert txns[0].reason == "subscription_grant"


@pytest.mark.asyncio
async def test_cancel_subscription(db_session, test_user):
    """cancel marks subscription as cancelled and sets cancelled_at."""
    from app.services.subscription_service import SubscriptionService
    svc = SubscriptionService(db_session)
    sub = await svc.subscribe(test_user.id, "pro", duration_days=30)
    await svc.cancel(sub.id, user_id=test_user.id)
    await db_session.refresh(sub)
    assert sub.status == "cancelled"
    assert sub.cancelled_at is not None
    assert sub.auto_renew is False


@pytest.mark.asyncio
async def test_cancel_nonexistent_raises(db_session, test_user):
    """cancel raises ValueError for nonexistent subscription."""
    from app.services.subscription_service import SubscriptionService
    svc = SubscriptionService(db_session)
    with pytest.raises(ValueError):
        await svc.cancel(uuid4(), user_id=test_user.id)


@pytest.mark.asyncio
async def test_get_active_subscription(db_session, test_user):
    """get_active returns the user's active subscription."""
    from app.services.subscription_service import SubscriptionService
    svc = SubscriptionService(db_session)
    await svc.subscribe(test_user.id, "pro", duration_days=30)
    active = await svc.get_active(test_user.id)
    assert active is not None
    assert active.plan == "pro"
    assert active.status == "active"


@pytest.mark.asyncio
async def test_get_active_returns_none_when_no_subscription(db_session, test_user):
    """get_active returns None when user has no active subscription."""
    from app.services.subscription_service import SubscriptionService
    svc = SubscriptionService(db_session)
    active = await svc.get_active(test_user.id)
    assert active is None


@pytest.mark.asyncio
async def test_get_active_excludes_cancelled(db_session, test_user):
    """get_active excludes cancelled subscriptions."""
    from app.services.subscription_service import SubscriptionService
    svc = SubscriptionService(db_session)
    sub = await svc.subscribe(test_user.id, "pro", duration_days=30)
    await svc.cancel(sub.id, user_id=test_user.id)
    active = await svc.get_active(test_user.id)
    assert active is None
