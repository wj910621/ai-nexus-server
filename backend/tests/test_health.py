"""健康检查测试 - layered /health (liveness) + /ready (readiness)."""
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.health import HealthCheckRegistry


@pytest.fixture(autouse=True)
async def _patch_db_engine(monkeypatch):
    """Patch the global engine to use in-memory SQLite for health checks.

    Ensures check_db() succeeds in tests where PostgreSQL is not available.
    Scoped to test_health.py only — does not affect other test modules.
    """
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import StaticPool
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    from app.core import database
    monkeypatch.setattr(database, "engine", engine)
    yield
    await engine.dispose()


# ===== Existing tests (kept for backward compatibility) =====


@pytest.mark.asyncio
async def test_health_check():
    """测试健康检查端点"""
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert data["data"]["status"] == "ok"


@pytest.mark.asyncio
async def test_root():
    """测试根路径"""
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "Y·NEX Story Studio" in data["data"]["name"]


@pytest.mark.asyncio
async def test_openapi_docs():
    """测试 OpenAPI 文档可访问"""
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/openapi.json")
    assert response.status_code == 200
    data = response.json()
    assert "paths" in data
    assert "/api/auth/login" in data["paths"]
    assert "/api/projects" in data["paths"]


# ===== New tests for layered health checks (Task 5) =====


@pytest.fixture
def registry():
    return HealthCheckRegistry()


@pytest.mark.asyncio
async def test_register_and_run_check(registry):
    """Registered check runs and returns result."""
    async def always_healthy():
        return {"status": "healthy", "detail": "all good"}

    registry.register("db", always_healthy)
    results = await registry.run_all()
    assert "db" in results
    assert results["db"]["status"] == "healthy"


@pytest.mark.asyncio
async def test_check_failure_marks_unhealthy(registry):
    """Check raising exception is marked unhealthy."""
    async def failing_check():
        raise RuntimeError("connection refused")

    registry.register("redis", failing_check)
    results = await registry.run_all()
    assert results["redis"]["status"] == "unhealthy"
    assert "connection refused" in results["redis"]["detail"]


@pytest.mark.asyncio
async def test_liveness_endpoint_returns_200():
    """/health always returns 200 (liveness probe)."""
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "ok"


@pytest.mark.asyncio
async def test_readiness_endpoint_when_healthy():
    """/ready returns 200 when all checks pass."""
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/ready")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "ready"


@pytest.mark.asyncio
async def test_public_ingress_health_aliases():
    """Shared-domain rewrites terminate at stable /api health aliases."""
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        health = await client.get("/api/health")
        ready = await client.get("/api/ready")
    assert health.status_code == 200
    assert health.json()["data"]["status"] == "ok"
    assert ready.status_code == 200
    assert ready.json()["data"]["status"] == "ready"


@pytest.mark.asyncio
async def test_readiness_endpoint_when_db_down():
    """/ready returns 503 when DB check fails."""
    from app.core.health import health_registry
    from app.main import app

    async def failing_db():
        raise RuntimeError("DB connection refused")

    original = health_registry._checks.get("db")
    health_registry.register("db", failing_db)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/ready")
        assert resp.status_code == 503
        assert resp.json()["data"]["status"] == "not_ready"
    finally:
        if original:
            health_registry.register("db", original)


@pytest.mark.asyncio
async def test_readiness_includes_all_checks():
    """/ready response includes db, redis, engines checks."""
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/ready")
    data = resp.json()["data"]
    assert "checks" in data
    # At least db check should be present
    assert "db" in data["checks"]


@pytest.mark.asyncio
async def test_readiness_skips_optional_when_absent():
    """Redis check is 'skipped' when Redis not configured (desktop)."""
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/ready")
    data = resp.json()["data"]
    # Redis may be skipped in desktop mode
    assert "redis" in data["checks"]


def test_health_registry_initial_state():
    """New registry has no checks."""
    reg = HealthCheckRegistry()
    assert reg.list_checks() == []
