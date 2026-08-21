"""ORM 模型基类与混入"""
import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, Uuid
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """ORM 基类 - 与 database.py 中的 Base 共用"""
    pass


def utc_now() -> datetime:
    """Return a naive UTC value for existing TIMESTAMP WITHOUT TIME ZONE columns."""
    return datetime.now(UTC).replace(tzinfo=None)


class UUIDMixin:
    """UUID 主键混入"""
    # SQLAlchemy's generic Uuid compiles to PostgreSQL UUID in production and
    # a portable CHAR representation in SQLite desktop/test deployments.
    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)


class TimestampMixin:
    """时间戳混入"""
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(
        DateTime,
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )


class SoftDeleteMixin:
    """软删除混入"""
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)
    deleted_at = Column(DateTime, nullable=True)
