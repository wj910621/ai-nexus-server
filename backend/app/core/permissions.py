"""Role-based permission helpers."""
from typing import Any

from fastapi import HTTPException, status

from app.models.user import User


def is_admin(user: Any) -> bool:
    """Check if user has admin role."""
    if user is None:
        return False
    return getattr(user, "role", None) == "admin"


def require_admin(user: User) -> None:
    """Raise 403 if user is not admin."""
    if not is_admin(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限",
        )
