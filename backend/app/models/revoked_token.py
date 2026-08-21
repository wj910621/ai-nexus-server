"""RevokedToken — blacklist for revoked JWT tokens (logout/refresh rotation)."""
from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class RevokedToken(Base):
    """JWT tokens that have been revoked before natural expiry.

    Used for: logout, refresh token rotation (old refresh token revoked after use).
    """

    __tablename__ = "revoked_tokens"

    jti: Mapped[str] = mapped_column(String(128), primary_key=True)
    # JWT ID (unique per token — uses token hash when jti claim absent)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, default="0")
    # Subject (sub) claim — UUID for User, stored as string for portability
    token_type: Mapped[str] = mapped_column(String(16), default="access")
    # access | refresh
    revoked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # When the original token would have expired (for cleanup)
