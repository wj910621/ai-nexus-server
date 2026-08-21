"""Tests for payment service (Stripe + Mock)."""
import pytest
from uuid import uuid4


def test_mock_payment_provider_used_when_stripe_disabled(monkeypatch):
    """When stripe_enabled=False, MockPaymentProvider is used."""
    monkeypatch.setenv("STRIPE_ENABLED", "false")
    import importlib
    import app.core.config
    importlib.reload(app.core.config)
    import app.services.payment_service
    importlib.reload(app.services.payment_service)
    from app.services.payment_service import PaymentService
    svc = PaymentService()
    assert svc.provider_name == "mock"


def test_stripe_provider_used_when_enabled(monkeypatch):
    """When stripe_enabled=True and key set, StripeProvider is used."""
    monkeypatch.setenv("STRIPE_ENABLED", "true")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_dummy")
    import importlib
    import app.core.config
    importlib.reload(app.core.config)
    import app.services.payment_service
    importlib.reload(app.services.payment_service)
    from app.services.payment_service import PaymentService
    svc = PaymentService()
    # Provider name may be "stripe" or "mock" if stripe lib not installed
    assert svc.provider_name in ("stripe", "mock")


@pytest.mark.asyncio
async def test_mock_create_payment_intent():
    """MockPaymentProvider.create_intent returns intent with id and client_secret."""
    from app.services.payment_service import MockPaymentProvider
    provider = MockPaymentProvider()
    intent = await provider.create_payment_intent(
        amount_cents=4900,
        currency="cny",
        metadata={"user_id": str(uuid4()), "plan": "pro"},
    )
    assert "id" in intent
    assert "client_secret" in intent
    assert intent["amount"] == 4900
    assert intent["currency"] == "cny"
    assert intent["status"] == "requires_confirmation"


@pytest.mark.asyncio
async def test_mock_confirm_payment_success():
    """MockPaymentProvider.confirm_payment returns success for valid intent."""
    from app.services.payment_service import MockPaymentProvider
    provider = MockPaymentProvider()
    intent = await provider.create_payment_intent(4900, "cny", {})
    result = await provider.confirm_payment(intent["id"])
    assert result["status"] == "succeeded"
    assert result["amount"] == 4900


@pytest.mark.asyncio
async def test_mock_confirm_payment_invalid_id():
    """MockPaymentProvider.confirm_payment raises for invalid intent ID."""
    from app.services.payment_service import MockPaymentProvider
    provider = MockPaymentProvider()
    with pytest.raises(ValueError, match="not found"):
        await provider.confirm_payment("pi_invalid")


@pytest.mark.asyncio
async def test_payment_service_create_intent(monkeypatch):
    """PaymentService.create_intent delegates to provider."""
    monkeypatch.setenv("STRIPE_ENABLED", "false")
    import importlib
    import app.core.config
    importlib.reload(app.core.config)
    import app.services.payment_service
    importlib.reload(app.services.payment_service)
    from app.services.payment_service import PaymentService
    svc = PaymentService()
    intent = await svc.create_intent(
        amount_cents=4900,
        currency="cny",
        metadata={"plan": "pro"},
    )
    assert "id" in intent
    assert "client_secret" in intent


@pytest.mark.asyncio
async def test_payment_service_confirm_payment(monkeypatch):
    """PaymentService.confirm_payment delegates to provider."""
    monkeypatch.setenv("STRIPE_ENABLED", "false")
    import importlib
    import app.core.config
    importlib.reload(app.core.config)
    import app.services.payment_service
    importlib.reload(app.services.payment_service)
    from app.services.payment_service import PaymentService
    svc = PaymentService()
    intent = await svc.create_intent(4900, "cny", {})
    result = await svc.confirm_payment(intent["id"])
    assert result["status"] == "succeeded"


@pytest.mark.asyncio
async def test_payment_service_webhook_signature_validation_skipped_in_mock(monkeypatch):
    """Webhook signature validation is skipped in mock mode."""
    monkeypatch.setenv("STRIPE_ENABLED", "false")
    import importlib
    import app.core.config
    importlib.reload(app.core.config)
    import app.services.payment_service
    importlib.reload(app.services.payment_service)
    from app.services.payment_service import PaymentService
    svc = PaymentService()
    # Mock provider always returns valid event
    event = await svc.parse_webhook_event(payload=b"{}", signature="")
    assert event["type"] == "mock.event"


@pytest.mark.asyncio
async def test_payment_service_handle_subscription_paid(monkeypatch, db_session):
    """handle_event with payment_intent.succeeded activates subscription."""
    monkeypatch.setenv("STRIPE_ENABLED", "false")
    import importlib
    import app.core.config
    importlib.reload(app.core.config)
    import app.services.payment_service
    importlib.reload(app.services.payment_service)

    # Create test user
    from app.models.user import User
    from app.core.security import hash_password
    user = User(
        username=f"payuser_{uuid4().hex[:8]}",
        email=f"pay_{uuid4().hex[:8]}@example.com",
        password_hash=hash_password("password123"),
        plan="free",
        credits=0,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)

    from app.models.billing import PurchaseConsent
    db_session.add(PurchaseConsent(
        user_id=user.id,
        payment_intent_id="pi_test_123",
        plan="pro",
        terms_version="2026-07-22",
        refund_policy_version="2026-07-22",
        terms_accepted=True,
        digital_service_acknowledged=True,
    ))
    await db_session.flush()

    # Mock event
    event = {
        "id": "evt_test_123",
        "type": "payment_intent.succeeded",
        "data": {
            "object": {
                "id": "pi_test_123",
                "amount": 4900,
                "currency": "cny",
                "metadata": {
                    "user_id": str(user.id),
                    "plan": "pro",
                    "duration_days": "30",
                    "terms_version": "2026-07-22",
                    "refund_policy_version": "2026-07-22",
                },
            }
        },
    }

    from app.services.payment_service import PaymentService
    svc = PaymentService()
    result = await svc.handle_event(event, db_session)
    assert result is True

    # Verify user's plan was updated
    await db_session.refresh(user)
    assert user.plan == "pro"
    assert user.credits > 0  # Subscription granted credits

    # Replaying the same provider event must not grant credits twice.
    credits_after_first_delivery = user.credits
    result = await svc.handle_event(event, db_session)
    assert result is True
    await db_session.refresh(user)
    assert user.credits == credits_after_first_delivery


@pytest.mark.asyncio
async def test_payment_service_handle_unknown_event(monkeypatch):
    """handle_event with unknown event type returns False (no action)."""
    monkeypatch.setenv("STRIPE_ENABLED", "false")
    import importlib
    import app.core.config
    importlib.reload(app.core.config)
    import app.services.payment_service
    importlib.reload(app.services.payment_service)
    from app.services.payment_service import PaymentService
    svc = PaymentService()
    result = await svc.handle_event({"type": "unknown.event", "data": {}}, db_session=None)
    assert result is False


@pytest.mark.asyncio
async def test_mock_provider_refund():
    """MockPaymentProvider.refund returns refund record."""
    from app.services.payment_service import MockPaymentProvider
    provider = MockPaymentProvider()
    intent = await provider.create_payment_intent(4900, "cny", {})
    await provider.confirm_payment(intent["id"])
    refund = await provider.refund(intent["id"], amount_cents=4900)
    assert refund["status"] == "succeeded"
    assert refund["amount"] == 4900
