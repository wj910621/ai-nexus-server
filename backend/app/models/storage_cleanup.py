"""Transactional outbox entries for storage deletions."""
from sqlalchemy import Column, Integer, String, Text

from app.models.base import Base, TimestampMixin, UUIDMixin


class PendingStorageDeletion(Base, UUIDMixin, TimestampMixin):
    """A file that must be removed after its owning DB record is deleted."""

    __tablename__ = "pending_storage_deletions"

    path = Column(String(500), nullable=False, index=True)
    attempts = Column(Integer, nullable=False, default=0)
    last_error = Column(Text, nullable=True)
