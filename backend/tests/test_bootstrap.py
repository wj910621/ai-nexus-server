"""Tests for first-run bootstrap."""
import pytest
from pathlib import Path


@pytest.fixture(autouse=True)
def _restore_config_after_bootstrap():
    """Reload config/database singletons after each test.

    Bootstrap tests reload app.core.config and app.core.database, leaving the
    `settings` singleton in desktop-mode (SQLite) state. Without restoration,
    this leaks into subsequent test modules (e.g. test_database_fallback) and
    breaks tests that assume the default postgres settings. The teardown runs
    after monkeypatch undo, so env vars are already restored to defaults.
    """
    yield
    import importlib
    import app.core.config
    importlib.reload(app.core.config)
    import app.core.database
    importlib.reload(app.core.database)


@pytest.mark.asyncio
async def test_bootstrap_creates_dirs(monkeypatch, tmp_path):
    """Bootstrap creates data dir + uploads + logs."""
    monkeypatch.setenv("CS_DESKTOP_MODE", "1")
    monkeypatch.setenv("CS_DATA_DIR", str(tmp_path))
    from app.core.bootstrap import bootstrap_desktop
    await bootstrap_desktop()
    assert tmp_path.exists()
    assert (tmp_path / "uploads").exists()
    assert (tmp_path / "logs").exists()


@pytest.mark.asyncio
async def test_bootstrap_creates_db(monkeypatch, tmp_path):
    """Bootstrap creates the SQLite database file."""
    monkeypatch.setenv("CS_DESKTOP_MODE", "1")
    monkeypatch.setenv("CS_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    # Force reload to pick up env
    import importlib
    import app.core.config
    importlib.reload(app.core.config)
    import app.core.database
    importlib.reload(app.core.database)
    from app.core.bootstrap import bootstrap_desktop
    await bootstrap_desktop()
    assert (tmp_path / "comicstudio.db").exists()


@pytest.mark.asyncio
async def test_bootstrap_idempotent(monkeypatch, tmp_path):
    """Running bootstrap twice is safe (no errors)."""
    monkeypatch.setenv("CS_DESKTOP_MODE", "1")
    monkeypatch.setenv("CS_DATA_DIR", str(tmp_path))
    from app.core.bootstrap import bootstrap_desktop
    await bootstrap_desktop()
    await bootstrap_desktop()  # Should not raise
    assert tmp_path.exists()


@pytest.mark.asyncio
async def test_bootstrap_creates_jwt_secret(monkeypatch, tmp_path):
    """Bootstrap generates a JWT secret if not present."""
    monkeypatch.setenv("CS_DESKTOP_MODE", "1")
    monkeypatch.setenv("CS_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    from app.core.bootstrap import bootstrap_desktop
    await bootstrap_desktop()
    assert (tmp_path / ".jwt_secret").exists()
    secret = (tmp_path / ".jwt_secret").read_text(encoding="utf-8")
    assert len(secret) >= 32


@pytest.mark.asyncio
async def test_bootstrap_not_in_desktop_mode(monkeypatch):
    """Bootstrap is a no-op when not in desktop mode."""
    monkeypatch.delenv("CS_DESKTOP_MODE", raising=False)
    from app.core.bootstrap import bootstrap_desktop
    result = await bootstrap_desktop()
    assert result is False  # Indicates skipped


@pytest.mark.asyncio
async def test_bootstrap_creates_uploads_subdirs(monkeypatch, tmp_path):
    """Bootstrap pre-creates uploads subdirs (images, audio)."""
    monkeypatch.setenv("CS_DESKTOP_MODE", "1")
    monkeypatch.setenv("CS_DATA_DIR", str(tmp_path))
    from app.core.bootstrap import bootstrap_desktop
    await bootstrap_desktop()
    assert (tmp_path / "uploads" / "images").exists()
    assert (tmp_path / "uploads" / "audio").exists()


@pytest.mark.asyncio
async def test_bootstrap_writes_version_file(monkeypatch, tmp_path):
    """Bootstrap writes a version.txt for diagnostic purposes."""
    monkeypatch.setenv("CS_DESKTOP_MODE", "1")
    monkeypatch.setenv("CS_DATA_DIR", str(tmp_path))
    from app.core.bootstrap import bootstrap_desktop
    await bootstrap_desktop()
    version_file = tmp_path / "version.txt"
    assert version_file.exists()
    content = version_file.read_text(encoding="utf-8")
    assert "0.1.0" in content


@pytest.mark.asyncio
async def test_bootstrap_runs_migrations_safe(monkeypatch, tmp_path):
    """Bootstrap runs schema migrations (create_all) safely."""
    monkeypatch.setenv("CS_DESKTOP_MODE", "1")
    monkeypatch.setenv("CS_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    import importlib
    import app.core.config
    importlib.reload(app.core.config)
    import app.core.database
    importlib.reload(app.core.database)
    from app.core.bootstrap import bootstrap_desktop
    await bootstrap_desktop()
    # Verify tables exist by querying sqlite_master
    from sqlalchemy import text
    from app.core.database import engine
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
        table_names = [row[0] for row in result.fetchall()]
    await engine.dispose()
    # Should have at least users table (from app.models.user)
    assert "users" in table_names


def test_bootstrap_returns_true_when_run(monkeypatch, tmp_path):
    """Bootstrap returns True when it actually ran (desktop mode)."""
    import asyncio
    monkeypatch.setenv("CS_DESKTOP_MODE", "1")
    monkeypatch.setenv("CS_DATA_DIR", str(tmp_path))
    from app.core.bootstrap import bootstrap_desktop
    result = asyncio.run(bootstrap_desktop())
    assert result is True


@pytest.mark.asyncio
async def test_bootstrap_handles_existing_db(monkeypatch, tmp_path):
    """Bootstrap handles existing database without corruption."""
    monkeypatch.setenv("CS_DESKTOP_MODE", "1")
    monkeypatch.setenv("CS_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    import importlib
    import app.core.config
    importlib.reload(app.core.config)
    import app.core.database
    importlib.reload(app.core.database)
    from app.core.bootstrap import bootstrap_desktop
    # First run
    await bootstrap_desktop()
    # Insert data
    from sqlalchemy import text
    from app.core.database import engine
    async with engine.begin() as conn:
        await conn.execute(text("CREATE TABLE persist_test (id INTEGER PRIMARY KEY)"))
        await conn.execute(text("INSERT INTO persist_test (id) VALUES (42)"))
    await engine.dispose()
    # Second run - should not drop existing data
    import importlib
    import app.core.database
    importlib.reload(app.core.database)
    await bootstrap_desktop()
    from app.core.database import engine
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT id FROM persist_test"))
        rows = result.fetchall()
    await engine.dispose()
    assert rows == [(42,)]


def test_bootstrap_creates_datasets_and_lora_dirs(tmp_path, monkeypatch):
    """P3: bootstrap 应预创建 datasets 和 lora_adapters 子目录"""
    import os
    monkeypatch.setenv("CS_DESKTOP_MODE", "1")

    # 指向临时目录
    from app.core import desktop_config
    monkeypatch.setattr(
        desktop_config, "get_desktop_data_dir", lambda: tmp_path
    )
    monkeypatch.setattr(
        desktop_config, "get_desktop_uploads_dir", lambda: tmp_path / "uploads"
    )
    monkeypatch.setattr(
        desktop_config, "get_desktop_jwt_secret", lambda: "test-secret"
    )

    import asyncio
    from app.core.bootstrap import bootstrap_desktop
    result = asyncio.run(bootstrap_desktop())

    assert result is True
    assert (tmp_path / "uploads" / "datasets").exists()
    assert (tmp_path / "uploads" / "lora_adapters").exists()
    # 既有目录不受影响
    assert (tmp_path / "uploads" / "images").exists()
    assert (tmp_path / "uploads" / "audio").exists()
