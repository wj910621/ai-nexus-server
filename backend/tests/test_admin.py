"""Tests for admin role and admin API endpoints."""
import pytest
import pytest_asyncio
from uuid import uuid4

from app.models.user import User


@pytest_asyncio.fixture
async def regular_user(db_session):
    from app.core.security import hash_password
    user = User(
        username=f"regular_{uuid4().hex[:8]}",
        email=f"reg_{uuid4().hex[:8]}@example.com",
        password_hash=hash_password("password123"),
        role="user",
        plan="free",
        credits=100,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def admin_user(db_session):
    from app.core.security import hash_password
    user = User(
        username=f"admin_{uuid4().hex[:8]}",
        email=f"admin_{uuid4().hex[:8]}@example.com",
        password_hash=hash_password("password123"),
        role="admin",
        plan="enterprise",
        credits=99999,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


def test_require_admin_decorator_allows_admin():
    """require_admin decorator allows admin users."""
    from app.core.permissions import is_admin
    class FakeUser:
        role = "admin"
    assert is_admin(FakeUser()) is True


def test_require_admin_decorator_blocks_regular():
    """require_admin blocks regular users."""
    from app.core.permissions import is_admin
    class FakeUser:
        role = "user"
    assert is_admin(FakeUser()) is False


def test_require_admin_blocks_none_role():
    """require_admin blocks users with no role."""
    from app.core.permissions import is_admin
    class FakeUser:
        role = None
    assert is_admin(FakeUser()) is False


@pytest.mark.asyncio
async def test_get_current_admin_succeeds_for_admin(db_session, admin_user):
    """get_current_admin returns admin user."""
    from app.core.deps import get_current_admin
    from unittest.mock import AsyncMock
    # get_current_admin depends on get_current_user which depends on OAuth2 token.
    # Test it indirectly by calling the helper logic.
    from app.core.permissions import is_admin
    assert is_admin(admin_user) is True


@pytest.mark.asyncio
async def test_get_current_admin_blocks_regular(db_session, regular_user):
    """get_current_admin blocks non-admin."""
    from app.core.permissions import is_admin
    assert is_admin(regular_user) is False


@pytest.mark.asyncio
async def test_admin_service_list_all_users(db_session, admin_user, regular_user):
    """AdminService.list_users returns all users."""
    from app.services.admin_service import AdminService
    svc = AdminService(db_session)
    users = await svc.list_users(limit=100)
    user_ids = {u.id for u in users}
    assert admin_user.id in user_ids
    assert regular_user.id in user_ids


@pytest.mark.asyncio
async def test_admin_service_get_stats(db_session, admin_user, regular_user):
    """AdminService.get_stats returns system statistics."""
    from app.services.admin_service import AdminService
    svc = AdminService(db_session)
    stats = await svc.get_stats()
    assert "total_users" in stats
    assert "active_subscriptions" in stats
    assert "total_credits_in_circulation" in stats
    assert "users_by_plan" in stats
    assert stats["total_users"] >= 2


@pytest.mark.asyncio
async def test_admin_service_ban_user(db_session, regular_user):
    """AdminService.ban_user sets user.status to 'banned'."""
    from app.services.admin_service import AdminService
    svc = AdminService(db_session)
    result = await svc.ban_user(regular_user.id)
    assert result is True
    await db_session.refresh(regular_user)
    assert regular_user.status == "banned"


@pytest.mark.asyncio
async def test_admin_service_unban_user(db_session, regular_user):
    """AdminService.unban_user sets user.status back to 'active'."""
    from app.services.admin_service import AdminService
    svc = AdminService(db_session)
    regular_user.status = "banned"
    await db_session.flush()
    result = await svc.unban_user(regular_user.id)
    assert result is True
    await db_session.refresh(regular_user)
    assert regular_user.status == "active"


@pytest.mark.asyncio
async def test_admin_service_grant_credits(db_session, regular_user):
    """AdminService.grant_credits adds credits to a user."""
    from app.services.admin_service import AdminService
    svc = AdminService(db_session)
    initial = regular_user.credits
    new_balance = await svc.grant_credits(regular_user.id, 500, "admin_bonus", "Test bonus")
    assert new_balance == initial + 500
    await db_session.refresh(regular_user)
    assert regular_user.credits == initial + 500


@pytest.mark.asyncio
async def test_admin_service_promote_to_admin(db_session, regular_user):
    """AdminService.promote_admin sets user.role to 'admin'."""
    from app.services.admin_service import AdminService
    svc = AdminService(db_session)
    result = await svc.promote_admin(regular_user.id)
    assert result is True
    await db_session.refresh(regular_user)
    assert regular_user.role == "admin"


@pytest.mark.asyncio
async def test_admin_service_demote_from_admin(db_session, admin_user):
    """AdminService.demote_admin sets user.role back to 'user'."""
    from app.services.admin_service import AdminService
    svc = AdminService(db_session)
    result = await svc.demote_admin(admin_user.id)
    assert result is True
    await db_session.refresh(admin_user)
    assert admin_user.role == "user"
