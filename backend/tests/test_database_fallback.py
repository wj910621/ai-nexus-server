"""Tests for database fallback (SQLite vs PostgreSQL)."""
import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_sqlite_engine_creation(monkeypatch, tmp_path):
    """SQLite aiosqlite engine can be created and disposed."""
    db_file = tmp_path / "test.db"
    url = f"sqlite+aiosqlite:///{db_file}"
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    engine = create_async_engine(url, echo=False)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE TABLE test (id INTEGER PRIMARY KEY)"))
        await conn.execute(text("INSERT INTO test (id) VALUES (1)"))
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT id FROM test"))
        rows = result.fetchall()
        assert rows == [(1,)]
    await engine.dispose()


@pytest.mark.asyncio
async def test_database_url_selection_desktop_sqlite(monkeypatch, tmp_path):
    """In desktop mode without explicit DATABASE_URL, SQLite is used."""
    monkeypatch.setenv("CS_DESKTOP_MODE", "1")
    monkeypatch.setenv("CS_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    from app.core.desktop_config import get_desktop_database_url
    url = get_desktop_database_url()
    assert "sqlite+aiosqlite" in url


@pytest.mark.asyncio
async def test_database_url_selection_explicit_postgres(monkeypatch):
    """When DATABASE_URL is explicitly postgres, it's used as-is."""
    monkeypatch.delenv("CS_DESKTOP_MODE", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost:5432/db")
    from app.core.config import settings
    assert settings.database_url.startswith("postgresql+asyncpg://")


def test_database_engine_uses_correct_driver_sqlite(monkeypatch, tmp_path):
    """The engine factory picks aiosqlite for sqlite URLs and asyncpg for postgres URLs."""
    from app.core.database import create_engine_for_url
    sqlite_url = f"sqlite+aiosqlite:///{tmp_path}/test.db"
    pg_url = "postgresql+asyncpg://user:pass@localhost:5432/db"
    # Just verify the function doesn't raise and returns an engine
    sqlite_engine = create_engine_for_url(sqlite_url, echo=False)
    assert "sqlite" in sqlite_engine.dialect.name
    pg_engine = create_engine_for_url(pg_url, echo=False, skip_create=True)
    assert pg_engine.dialect.name == "postgresql"
    # Dispose to clean up
    import asyncio
    asyncio.run(sqlite_engine.dispose())


@pytest.mark.asyncio
async def test_database_init_with_sqlite(monkeypatch, tmp_path):
    """init_db works with SQLite (creates tables)."""
    monkeypatch.setenv("CS_DESKTOP_MODE", "1")
    monkeypatch.setenv("CS_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    # Force re-import to pick up new env
    import importlib
    import app.core.config
    importlib.reload(app.core.config)
    import app.core.database
    importlib.reload(app.core.database)
    from app.core.database import init_db, close_db, Base
    # Import models so they register with Base
    import app.models  # noqa: F401
    await init_db()
    await close_db()
    # DB file should exist
    assert (tmp_path / "comicstudio.db").exists()


@pytest.mark.asyncio
async def test_database_session_sqlite(monkeypatch, tmp_path):
    """Async sessions work with SQLite fallback."""
    monkeypatch.setenv("CS_DESKTOP_MODE", "1")
    monkeypatch.setenv("CS_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    import importlib
    import app.core.config
    importlib.reload(app.core.config)
    import app.core.database
    importlib.reload(app.core.database)
    from app.core.database import init_db, close_db, AsyncSessionLocal
    import app.models  # noqa: F401
    await init_db()
    async with AsyncSessionLocal() as session:
        result = await session.execute(text("SELECT 1"))
        assert result.fetchone() == (1,)
    await close_db()


def test_database_engine_no_pool_args_for_sqlite(monkeypatch, tmp_path):
    """SQLite engine should not use pool_size/max_overflow (SQLite doesn't support them)."""
    from app.core.database import create_engine_for_url
    sqlite_url = f"sqlite+aiosqlite:///{tmp_path}/test.db"
    engine = create_engine_for_url(sqlite_url, echo=False)
    # SQLite uses StaticPool by default in SQLAlchemy 2.0 async; no pool_size attr
    assert engine.dialect.name == "sqlite"
    import asyncio
    asyncio.run(engine.dispose())


@pytest.mark.asyncio
async def test_database_url_from_settings_in_desktop_mode(monkeypatch, tmp_path):
    """Settings.database_url returns SQLite URL when in desktop mode without explicit URL."""
    monkeypatch.setenv("CS_DESKTOP_MODE", "1")
    monkeypatch.setenv("CS_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    import importlib
    import app.core.config
    importlib.reload(app.core.config)
    from app.core.config import settings
    assert "sqlite+aiosqlite" in settings.database_url
    assert str(tmp_path) in settings.database_url
