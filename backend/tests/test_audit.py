"""Tests for audit logging."""
import pytest
import pytest_asyncio
from uuid import uuid4


@pytest_asyncio.fixture
async def test_user(db_session):
    from app.models.user import User
    from app.core.security import hash_password
    user = User(
        username=f"audituser_{uuid4().hex[:8]}",
        email=f"audit_{uuid4().hex[:8]}@example.com",
        password_hash=hash_password("password123"),
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest.mark.asyncio
async def test_audit_log_create(db_session, test_user):
    """AuditService.log creates an AuditLog entry."""
    from app.services.audit_service import AuditService
    svc = AuditService(db_session)
    log = await svc.log(
        actor_id=test_user.id,
        action="user.login",
        resource_type="user",
        resource_id=test_user.id,
        metadata={"ip": "1.2.3.4"},
    )
    assert log.id is not None
    assert log.actor_id == test_user.id
    assert log.action == "user.login"


@pytest.mark.asyncio
async def test_audit_log_with_no_actor(db_session):
    """AuditService.log allows anonymous actions (actor_id=None)."""
    from app.services.audit_service import AuditService
    svc = AuditService(db_session)
    log = await svc.log(
        actor_id=None,
        action="system.startup",
        resource_type="system",
        resource_id=None,
    )
    assert log.actor_id is None
    assert log.action == "system.startup"


@pytest.mark.asyncio
async def test_audit_log_list_by_actor(db_session, test_user):
    """AuditService.list_by_actor returns user's actions."""
    from app.services.audit_service import AuditService
    svc = AuditService(db_session)
    await svc.log(test_user.id, "user.login", "user", test_user.id)
    await svc.log(test_user.id, "billing.deduct", "credit_transaction", uuid4())
    await svc.log(test_user.id, "project.create", "project", uuid4())

    logs = await svc.list_by_actor(test_user.id, limit=10)
    assert len(logs) == 3


@pytest.mark.asyncio
async def test_audit_log_list_by_action(db_session, test_user):
    """AuditService.list_by_action returns matching actions."""
    from app.services.audit_service import AuditService
    svc = AuditService(db_session)
    await svc.log(test_user.id, "user.login", "user", test_user.id)
    await svc.log(test_user.id, "user.login", "user", test_user.id)
    await svc.log(test_user.id, "billing.deduct", "credit_transaction", uuid4())

    login_logs = await svc.list_by_action("user.login", limit=10)
    assert len(login_logs) == 2


@pytest.mark.asyncio
async def test_audit_log_list_all_with_pagination(db_session, test_user):
    """AuditService.list_all supports pagination."""
    from app.services.audit_service import AuditService
    svc = AuditService(db_session)
    for i in range(5):
        await svc.log(test_user.id, f"test.action_{i}", "test", None)

    page1 = await svc.list_all(limit=2, offset=0)
    page2 = await svc.list_all(limit=2, offset=2)
    assert len(page1) == 2
    assert len(page2) == 2


@pytest.mark.asyncio
async def test_audit_log_metadata_persisted(db_session, test_user):
    """AuditLog stores metadata as JSON."""
    from app.services.audit_service import AuditService
    svc = AuditService(db_session)
    log = await svc.log(
        actor_id=test_user.id,
        action="billing.deduct",
        resource_type="credit_transaction",
        resource_id=uuid4(),
        metadata={"amount": 30, "reason": "text2img", "ip": "1.2.3.4"},
    )
    await db_session.refresh(log)
    assert log.metadata is not None
    assert log.metadata["amount"] == 30
    assert log.metadata["reason"] == "text2img"


@pytest.mark.asyncio
async def test_audit_log_ordered_by_created_at_desc(db_session, test_user):
    """Audit logs are returned newest first."""
    from app.services.audit_service import AuditService
    import time
    svc = AuditService(db_session)
    await svc.log(test_user.id, "first", "test", None)
    time.sleep(0.01)  # Ensure distinct timestamps
    await svc.log(test_user.id, "second", "test", None)
    time.sleep(0.01)
    await svc.log(test_user.id, "third", "test", None)

    logs = await svc.list_all(limit=10)
    actions = [l.action for l in logs]
    assert actions == ["third", "second", "first"]


@pytest.mark.asyncio
async def test_audit_log_count(db_session, test_user):
    """AuditService.count returns total log count."""
    from app.services.audit_service import AuditService
    svc = AuditService(db_session)
    for i in range(3):
        await svc.log(test_user.id, f"action_{i}", "test", None)
    count = await svc.count()
    assert count == 3
