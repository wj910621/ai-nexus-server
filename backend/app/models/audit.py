"""Audit log model - records all sensitive operations."""
from sqlalchemy import JSON, Column, String
from sqlalchemy import Uuid as UUID

from app.models.base import Base, TimestampMixin, UUIDMixin


class _MetadataProxy:
    """Descriptor exposing AuditLog.meta as 'metadata' on instances.

    'metadata' is reserved by SQLAlchemy's Declarative API: at the class
    level it refers to the ``MetaData`` object the table is registered on.
    This descriptor returns the registry's MetaData on class access (so
    SQLAlchemy internals keep working) while exposing the JSON column value
    on instance access (so ``log.metadata`` and ``AuditLog(metadata=...)``
    behave as callers expect).
    """

    def __get__(self, instance, owner):
        if instance is None:
            return owner.registry.metadata
        return instance.meta

    def __set__(self, instance, value):
        instance.meta = value


class AuditLog(Base, UUIDMixin, TimestampMixin):
    """审计日志 - 记录所有敏感操作"""
    __tablename__ = "audit_logs"

    actor_id = Column(UUID(as_uuid=True), index=True, nullable=True)  # None = system
    action = Column(String(100), nullable=False, index=True)  # e.g. "user.login", "billing.deduct"
    resource_type = Column(String(50), nullable=True)  # e.g. "user", "credit_transaction"
    resource_id = Column(UUID(as_uuid=True), nullable=True)
    # 'metadata' is reserved by SQLAlchemy; map the JSON column under 'meta'
    # (DB column name still 'metadata') and expose it via _MetadataProxy.
    meta = Column("metadata", JSON, default=dict)
    metadata = _MetadataProxy()
