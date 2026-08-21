"""Tests for enhanced authentication (email verification, password reset)."""
import pytest
import pytest_asyncio
from uuid import uuid4

from app.models.user import User


@pytest_asyncio.fixture
async def test_user(db_session):
    from app.core.security import hash_password
    user = User(
        username=f"authuser_{uuid4().hex[:8]}",
        email=f"auth_{uuid4().hex[:8]}@example.com",
        password_hash=hash_password("OldPassword123"),
        email_verified=False,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest.mark.asyncio
async def test_email_service_noop_in_desktop_mode(monkeypatch):
    """EmailService is a no-op in desktop mode (no SMTP)."""
    monkeypatch.setenv("CS_DESKTOP_MODE", "1")
    import importlib
    import app.core.config
    importlib.reload(app.core.config)
    import app.services.email_service
    importlib.reload(app.services.email_service)
    from app.services.email_service import EmailService
    svc = EmailService()
    # Should not raise; should return True (silently skipped)
    result = await svc.send_verification_email("test@example.com", "123456")
    assert result is True


@pytest.mark.asyncio
async def test_email_service_skipped_when_smtp_not_configured(monkeypatch):
    """EmailService is a no-op when SMTP host is empty."""
    monkeypatch.delenv("CS_DESKTOP_MODE", raising=False)
    monkeypatch.setenv("SMTP_HOST", "")
    import importlib
    import app.core.config
    importlib.reload(app.core.config)
    import app.services.email_service
    importlib.reload(app.services.email_service)
    from app.services.email_service import EmailService
    svc = EmailService()
    result = await svc.send_verification_email("test@example.com", "123456")
    assert result is True  # Silently skipped


@pytest.mark.asyncio
async def test_generate_verification_code():
    """generate_verification_code returns 6-digit string."""
    from app.services.email_service import EmailService
    svc = EmailService()
    code = svc.generate_verification_code()
    assert len(code) == 6
    assert code.isdigit()


@pytest.mark.asyncio
async def test_generate_verification_code_uniqueness():
    """Two consecutive codes are different (probabilistic)."""
    from app.services.email_service import EmailService
    svc = EmailService()
    codes = {svc.generate_verification_code() for _ in range(20)}
    assert len(codes) > 1  # Not all the same


@pytest.mark.asyncio
async def test_request_email_verification_sets_code(db_session, test_user, monkeypatch):
    """request_email_verification generates code, stores on user, returns True."""
    monkeypatch.delenv("CS_DESKTOP_MODE", raising=False)
    from app.services.user_service import UserService
    svc = UserService(db_session)
    result = await svc.request_email_verification(test_user)
    assert result is True
    await db_session.refresh(test_user)
    assert test_user.email_verification_code is not None
    assert len(test_user.email_verification_code) == 6
    assert test_user.code_expires_at is not None


@pytest.mark.asyncio
async def test_verify_email_with_correct_code(db_session, test_user, monkeypatch):
    """verify_email succeeds with correct code within expiry."""
    monkeypatch.delenv("CS_DESKTOP_MODE", raising=False)
    from app.services.user_service import UserService
    svc = UserService(db_session)
    await svc.request_email_verification(test_user)
    await db_session.refresh(test_user)
    code = test_user.email_verification_code
    result = await svc.verify_email(test_user, code)
    assert result is True
    await db_session.refresh(test_user)
    assert test_user.email_verified is True
    assert test_user.email_verification_code is None  # Cleared after use


@pytest.mark.asyncio
async def test_verify_email_with_wrong_code(db_session, test_user, monkeypatch):
    """verify_email fails with wrong code."""
    monkeypatch.delenv("CS_DESKTOP_MODE", raising=False)
    from app.services.user_service import UserService
    svc = UserService(db_session)
    await svc.request_email_verification(test_user)
    result = await svc.verify_email(test_user, "000000")
    assert result is False
    await db_session.refresh(test_user)
    assert test_user.email_verified is False


@pytest.mark.asyncio
async def test_verify_email_with_expired_code(db_session, test_user, monkeypatch):
    """verify_email fails when code is expired."""
    monkeypatch.delenv("CS_DESKTOP_MODE", raising=False)
    from app.services.user_service import UserService
    from datetime import datetime, timedelta, timezone
    svc = UserService(db_session)
    await svc.request_email_verification(test_user)
    # Manually expire the code
    await db_session.refresh(test_user)
    test_user.code_expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    await db_session.flush()
    code = test_user.email_verification_code
    result = await svc.verify_email(test_user, code)
    assert result is False


@pytest.mark.asyncio
async def test_request_password_reset_sets_code(db_session, test_user, monkeypatch):
    """request_password_reset generates a reset code for the user."""
    monkeypatch.delenv("CS_DESKTOP_MODE", raising=False)
    from app.services.user_service import UserService
    svc = UserService(db_session)
    result = await svc.request_password_reset(test_user.email)
    assert result is True
    await db_session.refresh(test_user)
    assert test_user.reset_password_code is not None
    assert len(test_user.reset_password_code) == 6


@pytest.mark.asyncio
async def test_request_password_reset_nonexistent_email(db_session, monkeypatch):
    """request_password_reset returns False for nonexistent email (security: don't leak)."""
    monkeypatch.delenv("CS_DESKTOP_MODE", raising=False)
    from app.services.user_service import UserService
    svc = UserService(db_session)
    result = await svc.request_password_reset("nonexistent@example.com")
    assert result is False


@pytest.mark.asyncio
async def test_reset_password_with_correct_code(db_session, test_user, monkeypatch):
    """reset_password succeeds with correct code."""
    monkeypatch.delenv("CS_DESKTOP_MODE", raising=False)
    from app.services.user_service import UserService
    from app.core.security import verify_password
    svc = UserService(db_session)
    await svc.request_password_reset(test_user.email)
    await db_session.refresh(test_user)
    code = test_user.reset_password_code
    result = await svc.reset_password(test_user.email, code, "NewPassword456")
    assert result is True
    await db_session.refresh(test_user)
    assert verify_password("NewPassword456", test_user.password_hash)
    assert test_user.reset_password_code is None  # Cleared


@pytest.mark.asyncio
async def test_reset_password_with_wrong_code(db_session, test_user, monkeypatch):
    """reset_password fails with wrong code."""
    monkeypatch.delenv("CS_DESKTOP_MODE", raising=False)
    from app.services.user_service import UserService
    from app.core.security import verify_password
    svc = UserService(db_session)
    await svc.request_password_reset(test_user.email)
    result = await svc.reset_password(test_user.email, "000000", "NewPassword456")
    assert result is False
    await db_session.refresh(test_user)
    # Password unchanged
    assert verify_password("OldPassword123", test_user.password_hash)
