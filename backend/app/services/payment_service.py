"""Payment service with Stripe and Mock providers.

In desktop mode or when stripe_enabled=False, MockPaymentProvider is used.
Mock provider simulates the full flow without external API calls.
"""
import os
import secrets
from typing import Optional

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings


class MockPaymentProvider:
    """In-memory mock payment provider for tests and desktop mode."""

    name = "mock"
    _shared_intents: dict[str, dict] = {}

    def __init__(self):
        # Shared for the lifetime of the desktop process so create and confirm
        # requests handled by different service instances see the same intent.
        self._intents = self._shared_intents

    async def create_payment_intent(
        self,
        amount_cents: int,
        currency: str = "cny",
        metadata: Optional[dict] = None,
    ) -> dict:
        intent_id = f"pi_mock_{secrets.token_hex(12)}"
        client_secret = f"{intent_id}_secret_{secrets.token_hex(8)}"
        intent = {
            "id": intent_id,
            "client_secret": client_secret,
            "amount": amount_cents,
            "currency": currency,
            "status": "requires_confirmation",
            "metadata": metadata or {},
        }
        self._intents[intent_id] = intent
        return intent

    async def confirm_payment(self, intent_id: str) -> dict:
        if intent_id not in self._intents:
            raise ValueError(f"Payment intent {intent_id} not found")
        intent = self._intents[intent_id]
        intent["status"] = "succeeded"
        return intent

    async def refund(self, intent_id: str, amount_cents: int) -> dict:
        if intent_id not in self._intents:
            raise ValueError(f"Payment intent {intent_id} not found")
        return {
            "id": f"re_mock_{secrets.token_hex(8)}",
            "intent_id": intent_id,
            "amount": amount_cents,
            "status": "succeeded",
        }

    async def parse_webhook_event(self, payload: bytes, signature: str) -> dict:
        return {"id": f"evt_mock_{secrets.token_hex(12)}", "type": "mock.event", "data": {}}


class StripePaymentProvider:
    """Stripe payment provider (real API calls)."""

    name = "stripe"

    def __init__(self):
        try:
            import stripe  # noqa: F401
            stripe.api_key = settings.stripe_secret_key
            self._stripe = stripe
        except ImportError:
            logger.warning("stripe package not installed; falling back to mock")
            raise

    async def create_payment_intent(
        self,
        amount_cents: int,
        currency: str = "cny",
        metadata: Optional[dict] = None,
    ) -> dict:
        intent = self._stripe.PaymentIntent.create(
            amount=amount_cents,
            currency=currency,
            metadata=metadata or {},
            automatic_payment_methods={"enabled": True},
        )
        return {
            "id": intent.id,
            "client_secret": intent.client_secret,
            "amount": intent.amount,
            "currency": intent.currency,
            "status": intent.status,
            "metadata": dict(intent.metadata or {}),
        }

    async def confirm_payment(self, intent_id: str) -> dict:
        intent = self._stripe.PaymentIntent.retrieve(intent_id)
        return {
            "id": intent.id,
            "amount": intent.amount,
            "currency": intent.currency,
            "status": intent.status,
            "metadata": dict(intent.metadata or {}),
        }

    async def refund(self, intent_id: str, amount_cents: int) -> dict:
        refund = self._stripe.Refund.create(
            payment_intent=intent_id,
            amount=amount_cents,
        )
        return {
            "id": refund.id,
            "intent_id": intent_id,
            "amount": refund.amount,
            "status": refund.status,
        }

    async def parse_webhook_event(self, payload: bytes, signature: str) -> dict:
        if not signature:
            raise ValueError("Missing Stripe webhook signature")
        try:
            event = self._stripe.Webhook.construct_event(
                payload, signature, settings.stripe_webhook_secret,
            )
        except Exception as exc:
            logger.warning("Stripe webhook verification failed")
            raise ValueError("Invalid Stripe webhook") from exc
        return {"id": event["id"], "type": event["type"], "data": event["data"]}


class PaymentService:
    """Payment service facade - delegates to configured provider."""

    def __init__(self):
        self._provider = self._select_provider()

    def _select_provider(self):
        """Select payment provider based on configuration."""
        # Desktop mode always uses mock
        if os.environ.get("CS_DESKTOP_MODE", "").lower() in ("1", "true", "yes"):
            return MockPaymentProvider()
        if settings.is_production:
            if not (
                settings.stripe_enabled
                and settings.stripe_secret_key
                and settings.stripe_webhook_secret
            ):
                raise RuntimeError(
                    "Production payments require Stripe and a webhook secret"
                )
            return StripePaymentProvider()
        # Stripe enabled only when explicitly configured outside production.
        if settings.stripe_enabled and settings.stripe_secret_key:
            try:
                return StripePaymentProvider()
            except Exception as e:
                logger.warning(f"Stripe init failed, using mock: {e}")
                return MockPaymentProvider()
        return MockPaymentProvider()

    @property
    def provider_name(self) -> str:
        return self._provider.name

    async def create_intent(
        self,
        amount_cents: int,
        currency: str = "cny",
        metadata: Optional[dict] = None,
    ) -> dict:
        return await self._provider.create_payment_intent(amount_cents, currency, metadata)

    async def confirm_payment(self, intent_id: str) -> dict:
        return await self._provider.confirm_payment(intent_id)

    async def refund(self, intent_id: str, amount_cents: int) -> dict:
        return await self._provider.refund(intent_id, amount_cents)

    async def parse_webhook_event(self, payload: bytes, signature: str) -> dict:
        """Verify and normalize a provider webhook event."""
        return await self._provider.parse_webhook_event(payload, signature)

    async def handle_event(self, event: dict, db_session: AsyncSession) -> bool:
        """Handle a payment event. Returns True if action taken.

        For 'payment_intent.succeeded': activates subscription for the user
        specified in metadata.
        """
        event_type = event.get("type")
        if event_type != "payment_intent.succeeded":
            logger.debug(f"Ignoring event type: {event_type}")
            return False

        data = event.get("data", {}).get("object", {})
        metadata = data.get("metadata", {})
        user_id_str = metadata.get("user_id")
        plan = metadata.get("plan")
        try:
            duration_days = int(metadata.get("duration_days", "30"))
        except (TypeError, ValueError):
            logger.error("Webhook contains an invalid subscription duration")
            return False
        if duration_days < 1 or duration_days > 365:
            logger.error("Webhook subscription duration is outside allowed bounds")
            return False
        payment_id = data.get("id", "")

        event_id = event.get("id")
        if not event_id:
            logger.error("Webhook event is missing a provider event ID")
            return False

        if not user_id_str or not plan:
            logger.error(f"Webhook missing user_id or plan in metadata: {metadata}")
            return False

        from uuid import UUID

        from app.models.billing import PaymentEvent, PurchaseConsent
        from app.services.subscription_service import PLAN_DEFINITIONS, SubscriptionService
        try:
            user_id = UUID(user_id_str)
        except ValueError:
            logger.error(f"Invalid user_id in metadata: {user_id_str}")
            return False

        plan_info = PLAN_DEFINITIONS.get(plan)
        if plan_info is None or plan == "free":
            logger.error(f"Invalid paid plan in webhook: {plan}")
            return False
        if data.get("amount") != plan_info.price_cents or data.get("currency") != "cny":
            logger.error("Webhook amount or currency does not match the plan catalog")
            return False

        consent_result = await db_session.execute(
            select(PurchaseConsent).where(
                PurchaseConsent.payment_intent_id == payment_id,
                PurchaseConsent.user_id == user_id,
            )
        )
        consent = consent_result.scalar_one_or_none()
        if (
            consent is None
            or not consent.terms_accepted
            or not consent.digital_service_acknowledged
            or metadata.get("terms_version") != consent.terms_version
            or metadata.get("refund_policy_version") != consent.refund_policy_version
        ):
            logger.error("Payment has no matching, versioned purchase consent")
            return False

        existing = await db_session.execute(
            select(PaymentEvent).where(PaymentEvent.event_id == event_id)
        )
        if existing.scalar_one_or_none() is not None:
            logger.info(f"Ignoring replayed payment event: {event_id}")
            return True

        sub_svc = SubscriptionService(db_session)
        try:
            await sub_svc.subscribe(
                user_id=user_id,
                plan=plan,
                duration_days=duration_days,
                payment_method=self._provider.name,
                payment_id=payment_id,
                auto_renew=metadata.get("auto_renew", "false").lower() == "true",
            )
            db_session.add(PaymentEvent(
                provider=self._provider.name,
                event_id=event_id,
                event_type=event_type,
                payment_id=payment_id,
                user_id=user_id,
            ))
            await db_session.flush()
            logger.info(f"Subscription activated for user {user_id}: plan={plan}")
            return True
        except Exception as e:
            logger.error(f"Failed to activate subscription: {e}")
            raise
