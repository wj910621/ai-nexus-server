"""计费模型 (Subscription + CreditTransaction)"""
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy import Uuid as UUID

from app.models.base import Base, TimestampMixin, UUIDMixin


class Subscription(Base, UUIDMixin, TimestampMixin):
    """订阅记录"""
    __tablename__ = "subscriptions"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    plan = Column(String(20), nullable=False)  # free/pro/enterprise
    status = Column(String(20), default="active")  # active/cancelled/expired

    started_at = Column(DateTime, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    cancelled_at = Column(DateTime, nullable=True)

    amount = Column(Integer)  # 金额（分）
    payment_method = Column(String(50))
    payment_id = Column(String(200))

    auto_renew = Column(Boolean, default=False)


class CreditTransaction(Base, UUIDMixin, TimestampMixin):
    """积分交易记录"""
    __tablename__ = "credit_transactions"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    type = Column(String(20), nullable=False)  # recharge/deduct/bonus/refund
    amount = Column(Integer, nullable=False)
    balance_after = Column(Integer, nullable=False)

    reason = Column(String(50))  # create_character/render/lora_train/recharge
    description = Column(String(200))

    related_id = Column(UUID(as_uuid=True), nullable=True)
    related_type = Column(String(50))


class PaymentEvent(Base, UUIDMixin, TimestampMixin):
    """Durable payment webhook receipt used to reject replayed events."""
    __tablename__ = "payment_events"

    provider = Column(String(32), nullable=False)
    event_id = Column(String(200), nullable=False, unique=True, index=True)
    event_type = Column(String(100), nullable=False)
    payment_id = Column(String(200), nullable=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)


class PurchaseConsent(Base, UUIDMixin, TimestampMixin):
    """Auditable acceptance captured immediately before payment creation."""
    __tablename__ = "purchase_consents"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    payment_intent_id = Column(String(200), nullable=False, unique=True, index=True)
    plan = Column(String(20), nullable=False)
    terms_version = Column(String(20), nullable=False)
    refund_policy_version = Column(String(20), nullable=False)
    terms_accepted = Column(Boolean, nullable=False, default=False)
    digital_service_acknowledged = Column(Boolean, nullable=False, default=False)
