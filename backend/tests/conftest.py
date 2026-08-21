"""测试配置"""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture(autouse=True)
def _reset_cache_singleton():
    """Reset the global CacheService singleton between tests for isolation.

    Ensures cached values from one test do not leak into another (e.g. when
    @cached decorator is applied to service methods). Also forces in-memory
    backend so tests don't time out trying to reach Redis.
    """
    try:
        from app.core.cache import reset_cache_service
        from app.core.config import settings
        # Force in-memory backend for tests (avoid Redis connection timeout)
        original = settings.cache_redis_url
        original_jwt_secret = settings.jwt_secret_key
        settings.cache_redis_url = "memory"
        settings.jwt_secret_key = "test-jwt-secret-key-with-at-least-32-bytes"
        reset_cache_service()
    except ImportError:
        # cache module not yet created (early test collection)
        original = None
    yield
    try:
        from app.core.cache import reset_cache_service
        reset_cache_service()
        if original is not None:
            from app.core.config import settings
            settings.cache_redis_url = original
            settings.jwt_secret_key = original_jwt_secret
    except ImportError:
        pass


@pytest.fixture(autouse=True)
def _reset_http_client_factory():
    """Reset the global HttpClientFactory singleton between tests for isolation.

    Some tests (e.g. test_pollinations.test_provider_initialize) close the
    shared client via `provider.client.aclose()`. Without resetting the
    factory's cache, subsequent tests would receive the closed client from
    the cache and fail when trying to use it. Clearing the dict after each
    test ensures each test starts with a fresh factory state.
    """
    yield
    try:
        from app.core.http_client import http_client_factory
        # Synchronously clear the cache; clients are not real-networked in tests
        # so we skip aclose() for speed (resource cleanup is acceptable leak in tests).
        http_client_factory._clients.clear()
    except ImportError:
        # http_client module not yet created (early test collection)
        pass


@pytest.fixture
async def db_session(monkeypatch) -> AsyncSession:
    """数据库会话 fixture (用于集成测试)

    使用内存 SQLite + StaticPool，每个测试获得独立的数据库实例。
    避免依赖外部 PostgreSQL 服务（desktop mode 同样使用 SQLite 作为回退）。

    同时 patch `app.core.database.AsyncSessionLocal`，以便后台任务
    (TaskService._run_task) 使用同一个内存数据库，而非生产 engine。
    """
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from sqlalchemy.pool import StaticPool
    from app.models.base import Base
    import app.models  # noqa: F401 - 注册所有模型

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    # 创建所有表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    SessionLocal = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    # Patch global AsyncSessionLocal so background tasks (TaskService._run_task)
    # share the same in-memory SQLite engine as the test fixture.
    from app.core import database
    monkeypatch.setattr(database, "AsyncSessionLocal", SessionLocal)

    async with SessionLocal() as session:
        yield session
        await session.rollback()

    await engine.dispose()
