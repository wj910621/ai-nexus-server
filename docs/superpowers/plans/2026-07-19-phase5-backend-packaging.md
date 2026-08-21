# Phase 5: Python Backend Packaging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Package the Python FastAPI backend into a standalone executable that the Electron desktop app can launch in `local-python` mode for true offline operation, with SQLite fallback when PostgreSQL is unavailable.

**Architecture:** PyInstaller bundles the backend (`app.main:app` + uvicorn + all deps including asyncpg/bcrypt/pydantic-core native modules) into a single onedir executable. A new `DesktopSettings` layer adds SQLite/aiosqlite as a database fallback, with automatic schema bootstrap on first launch. The Electron `BackendProcess` is extended to spawn the packaged executable directly (no Python install required on user machines).

**Tech Stack:** PyInstaller 6.x, aiosqlite 0.19.x, existing FastAPI + SQLAlchemy 2.0 async + asyncpg + bcrypt + pydantic v2 + loguru + alembic + edge-tts + ffmpeg-python. Tests: pytest + pytest-asyncio (existing 182-test baseline must remain green).

---

## File Structure

```
backend/
├── app/
│   ├── core/
│   │   ├── config.py          [MODIFY] add is_desktop_mode + desktop database URL detection
│   │   ├── database.py        [MODIFY] support SQLite aiosqlite driver alongside asyncpg
│   │   ├── paths.py           [NEW] desktop data dir resolution (userData/data/db/uploads)
│   │   ├── bootstrap.py       [NEW] first-run setup: create dirs + initialize schema
│   │   └── storage.py         [MODIFY] use desktop uploads path in desktop mode
│   └── main.py                [MODIFY] call bootstrap in lifespan when desktop mode
├── packaging/
│   ├── entry.py               [NEW] frozen entry point: set sys.path + run uvicorn
│   ├── runtime.py             [NEW] detect frozen state + resolve resource paths
│   ├── build.py               [NEW] build script (calls PyInstaller with spec)
│   ├── verify_spec.py         [NEW] spec integrity verification (paths, hooks, datas)
│   ├── comicstudio_backend.spec [NEW] PyInstaller spec (onedir, hooks, datas, hiddenimports)
│   └── hooks/
│       ├── hook-asyncpg.py    [NEW] bundle asyncpg pgproto .pyx + version
│       ├── hook-bcrypt.py     [NEW] bundle _bcrypt.pyd
│       ├── hook-loguru.py     [NEW] bundle loguru default sinks
│       ├── hook-pydantic_core.py [NEW] bundle pydantic-core .pyd
│       ├── hook-alembic.py    [NEW] bundle alembic mako templates + script.py.mako
│       └── hook-ffmpeg_python.py [NEW] bundle ffmpeg-python _run.py template
├── tests/
│   ├── test_desktop_config.py [NEW] 12 tests
│   ├── test_paths.py          [NEW] 8 tests
│   ├── test_bootstrap.py      [NEW] 10 tests
│   ├── test_database_fallback.py [NEW] 8 tests
│   ├── test_runtime.py        [NEW] 8 tests
│   ├── test_verify_spec.py    [NEW] 6 tests
│   ├── test_build_script.py   [NEW] 5 tests
│   └── test_e2e_packaged.py   [NEW] 10 tests
├── requirements.txt           [MODIFY] add aiosqlite, pyinstaller
└── packaging/README.md        [NEW] build instructions

desktop/
├── src/main/
│   ├── constants.ts           [MODIFY] add packaged backend config
│   └── backend/backend-process.ts [MODIFY] support spawn packaged exe
├── electron-builder.yml       [MODIFY] add extraResources for backend
└── src/test/integration.test.ts [MODIFY] add packaged backend assertions

docs/deployment/
└── desktop-packaging.md       [NEW] complete desktop packaging guide
```

---

### Task 1: Desktop Configuration + SQLite Fallback

**Files:**
- Modify: `c:\漫剧软件项目\backend\app\core\config.py`
- Create: `c:\漫剧软件项目\backend\app\core\desktop_config.py`
- Modify: `c:\漫剧软件项目\backend\app\core\database.py`
- Modify: `c:\漫剧软件项目\backend\requirements.txt`
- Create: `c:\漫剧软件项目\backend\tests\test_desktop_config.py`
- Create: `c:\漫剧软件项目\backend\tests\test_database_fallback.py`

- [ ] **Step 1: Write the failing tests for desktop config**

Create `c:\漫剧软件项目\backend\tests\test_desktop_config.py`:

```python
"""Tests for desktop mode configuration."""
import os
import pytest
from pathlib import Path


def test_is_desktop_mode_false_by_default(monkeypatch):
    """By default (no env var), app is NOT in desktop mode."""
    monkeypatch.delenv("CS_DESKTOP_MODE", raising=False)
    from app.core.desktop_config import is_desktop_mode
    assert is_desktop_mode() is False


def test_is_desktop_mode_true_when_env_set(monkeypatch):
    """CS_DESKTOP_MODE=1 enables desktop mode."""
    monkeypatch.setenv("CS_DESKTOP_MODE", "1")
    from app.core.desktop_config import is_desktop_mode
    assert is_desktop_mode() is True


def test_desktop_data_dir_resolves_user_data(monkeypatch, tmp_path):
    """In desktop mode, data dir is CS_DATA_DIR or fallback to user_data/comicstudio."""
    monkeypatch.setenv("CS_DESKTOP_MODE", "1")
    monkeypatch.setenv("CS_DATA_DIR", str(tmp_path))
    from app.core.desktop_config import get_desktop_data_dir
    result = get_desktop_data_dir()
    assert result == tmp_path


def test_desktop_data_dir_default_when_not_set(monkeypatch, tmp_path):
    """When CS_DATA_DIR not set, falls back to a sensible default."""
    monkeypatch.setenv("CS_DESKTOP_MODE", "1")
    monkeypatch.delenv("CS_DATA_DIR", raising=False)
    monkeypatch.setattr("os.path.expanduser", lambda p: str(tmp_path) if p == "~" else p)
    from app.core.desktop_config import get_desktop_data_dir
    result = get_desktop_data_dir()
    assert result.name == "comicstudio-data"
    assert result.parent == tmp_path


def test_desktop_database_url_uses_sqlite(monkeypatch, tmp_path):
    """In desktop mode, database URL defaults to SQLite in data dir."""
    monkeypatch.setenv("CS_DESKTOP_MODE", "1")
    monkeypatch.setenv("CS_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    from app.core.desktop_config import get_desktop_database_url
    url = get_desktop_database_url()
    assert url.startswith("sqlite+aiosqlite:///")
    assert "comicstudio.db" in url
    assert str(tmp_path) in url


def test_desktop_database_url_respects_explicit_sqlite(monkeypatch, tmp_path):
    """If user explicitly sets DATABASE_URL in desktop mode, it's honored."""
    monkeypatch.setenv("CS_DESKTOP_MODE", "1")
    monkeypatch.setenv("CS_DATA_DIR", str(tmp_path))
    custom_url = "sqlite+aiosqlite:///./custom.db"
    monkeypatch.setenv("DATABASE_URL", custom_url)
    from app.core.desktop_config import get_desktop_database_url
    assert get_desktop_database_url() == custom_url


def test_desktop_uploads_dir(monkeypatch, tmp_path):
    """Uploads dir is data_dir/uploads in desktop mode."""
    monkeypatch.setenv("CS_DESKTOP_MODE", "1")
    monkeypatch.setenv("CS_DATA_DIR", str(tmp_path))
    from app.core.desktop_config import get_desktop_uploads_dir
    result = get_desktop_uploads_dir()
    assert result == tmp_path / "uploads"


def test_desktop_runtime_mode_detection(monkeypatch):
    """Runtime mode detection: 'frozen' (PyInstaller) vs 'development'."""
    from app.core.desktop_config import get_runtime_mode
    # Default (not frozen) - development mode
    monkeypatch.setattr("sys.frozen", False, raising=False)
    assert get_runtime_mode() == "development"


def test_desktop_runtime_mode_frozen(monkeypatch):
    """When sys.frozen is True, runtime mode is 'frozen'."""
    import sys
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    from app.core.desktop_config import get_runtime_mode
    assert get_runtime_mode() == "frozen"


def test_desktop_config_all_paths_exist_after_init(monkeypatch, tmp_path):
    """get_desktop_paths returns dict with all expected keys."""
    monkeypatch.setenv("CS_DESKTOP_MODE", "1")
    monkeypatch.setenv("CS_DATA_DIR", str(tmp_path))
    from app.core.desktop_config import get_desktop_paths
    paths = get_desktop_paths()
    assert set(paths.keys()) == {"data_dir", "database_url", "uploads_dir", "db_file"}
    assert paths["data_dir"] == tmp_path
    assert paths["uploads_dir"] == tmp_path / "uploads"
    assert paths["db_file"] == tmp_path / "comicstudio.db"
    assert paths["database_url"].startswith("sqlite+aiosqlite:///")


def test_desktop_mode_not_enabled_in_ci(monkeypatch):
    """CI environment should never accidentally enable desktop mode."""
    monkeypatch.delenv("CS_DESKTOP_MODE", raising=False)
    monkeypatch.setenv("CI", "true")
    from app.core.desktop_config import is_desktop_mode
    assert is_desktop_mode() is False


def test_desktop_jwt_secret_default(monkeypatch, tmp_path):
    """Desktop mode generates a stable JWT secret stored in data dir."""
    monkeypatch.setenv("CS_DESKTOP_MODE", "1")
    monkeypatch.setenv("CS_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    from app.core.desktop_config import get_desktop_jwt_secret
    secret1 = get_desktop_jwt_secret()
    secret2 = get_desktop_jwt_secret()
    # Same secret returned on subsequent calls (stable)
    assert secret1 == secret2
    assert len(secret1) >= 32
    # Secret file persisted
    assert (tmp_path / ".jwt_secret").exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run (cwd `c:\漫剧软件项目\backend`): `python -m pytest tests/test_desktop_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.core.desktop_config'`

- [ ] **Step 3: Add aiosqlite to requirements**

Modify `c:\漫剧软件项目\backend\requirements.txt` — append after the `asyncpg==0.29.0` line:

```
# SQLite async driver (desktop mode fallback when PostgreSQL unavailable)
aiosqlite==0.19.0
```

Then install:
Run (cwd `c:\漫剧软件项目\backend`): `python -m pip install --target .deps aiosqlite==0.19.0`
Expected: `Successfully installed aiosqlite-0.19.0`

- [ ] **Step 4: Create desktop_config.py with all the functions**

Create `c:\漫剧软件项目\backend\app\core\desktop_config.py`:

```python
"""Desktop mode configuration.

Desktop mode is activated via CS_DESKTOP_MODE=1 environment variable.
In desktop mode:
- Data directory is CS_DATA_DIR (or ~/comicstudio-data as fallback)
- Database defaults to SQLite (aiosqlite) at data_dir/comicstudio.db
- Uploads go to data_dir/uploads/
- JWT secret is persisted to data_dir/.jwt_secret (auto-generated on first run)
"""
import os
import secrets
import sys
from pathlib import Path
from typing import Literal, Optional


RuntimeMode = Literal["development", "frozen"]


def is_desktop_mode() -> bool:
    """Check if app is running in desktop mode (packaged Electron)."""
    return os.environ.get("CS_DESKTOP_MODE", "").lower() in ("1", "true", "yes")


def get_runtime_mode() -> RuntimeMode:
    """Detect runtime mode: 'frozen' (PyInstaller bundle) or 'development'."""
    return "frozen" if getattr(sys, "frozen", False) else "development"


def get_desktop_data_dir() -> Path:
    """Resolve the desktop data directory.

    Priority:
    1. CS_DATA_DIR env var
    2. ~/comicstudio-data (user home)
    """
    env_data_dir = os.environ.get("CS_DATA_DIR")
    if env_data_dir:
        return Path(env_data_dir).resolve()
    return Path(os.path.expanduser("~")) / "comicstudio-data"


def get_desktop_db_file() -> Path:
    """Get the SQLite database file path."""
    return get_desktop_data_dir() / "comicstudio.db"


def get_desktop_database_url() -> str:
    """Get the database URL for desktop mode.

    If DATABASE_URL env var is explicitly set, honor it.
    Otherwise, use SQLite at data_dir/comicstudio.db.
    """
    explicit = os.environ.get("DATABASE_URL")
    if explicit:
        return explicit
    db_file = get_desktop_db_file()
    # Use 4 slashes for absolute path in SQLAlchemy SQLite URL
    return f"sqlite+aiosqlite:///{db_file}"


def get_desktop_uploads_dir() -> Path:
    """Get the uploads directory for desktop mode."""
    return get_desktop_data_dir() / "uploads"


def get_desktop_jwt_secret() -> str:
    """Get or generate a stable JWT secret for desktop mode.

    The secret is generated once and persisted to data_dir/.jwt_secret.
    """
    data_dir = get_desktop_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    secret_file = data_dir / ".jwt_secret"
    if secret_file.exists():
        return secret_file.read_text(encoding="utf-8").strip()
    secret = secrets.token_urlsafe(48)
    secret_file.write_text(secret, encoding="utf-8")
    # Restrict permissions on secret file (best-effort, ignored on Windows)
    try:
        os.chmod(secret_file, 0o600)
    except OSError:
        pass
    return secret


def get_desktop_paths() -> dict:
    """Get all desktop paths as a dict (for inspection/debugging)."""
    return {
        "data_dir": get_desktop_data_dir(),
        "database_url": get_desktop_database_url(),
        "uploads_dir": get_desktop_uploads_dir(),
        "db_file": get_desktop_db_file(),
    }


def ensure_desktop_dirs() -> None:
    """Create all required desktop directories if they don't exist."""
    data_dir = get_desktop_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    get_desktop_uploads_dir().mkdir(parents=True, exist_ok=True)
```

- [ ] **Step 5: Run tests to verify they pass**

Run (cwd `c:\漫剧软件项目\backend`): `python -m pytest tests/test_desktop_config.py -v`
Expected: 12 passed

- [ ] **Step 6: Write failing tests for database fallback**

Create `c:\漫剧软件项目\backend\tests\test_database_fallback.py`:

```python
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
    asyncio.get_event_loop().run_until_complete(sqlite_engine.dispose())


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
    asyncio.get_event_loop().run_until_complete(engine.dispose())


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
```

- [ ] **Step 7: Run tests to verify they fail**

Run (cwd `c:\漫剧软件项目\backend`): `python -m pytest tests/test_database_fallback.py -v`
Expected: FAIL with `ImportError: cannot import name 'create_engine_for_url' from 'app.core.database'`

- [ ] **Step 8: Modify config.py to support desktop mode**

Modify `c:\漫剧软件项目\backend\app\core\config.py` — replace the existing `database_url` field and add desktop detection. Replace lines 25-26 (the `# 数据库` comment + `database_url` line) and the `Settings` instantiation at the end:

Find:
```python
    # 数据库
    database_url: str = "postgresql+asyncpg://comic_user:comic_password@localhost:5432/comic_studio"
```

Replace with:
```python
    # 数据库 (overridden to SQLite when desktop mode + no explicit DATABASE_URL)
    database_url: str = "postgresql+asyncpg://comic_user:comic_password@localhost:5432/comic_studio"
```

Then find the last lines of the file:
```python
# 全局配置单例
settings = Settings()
```

Replace with:
```python
# 全局配置单例
def _build_settings() -> "Settings":
    """Build settings, applying desktop-mode overrides if CS_DESKTOP_MODE=1."""
    import os
    s = Settings()
    if os.environ.get("CS_DESKTOP_MODE", "").lower() in ("1", "true", "yes"):
        # In desktop mode: if DATABASE_URL is the default postgres URL or unset,
        # use SQLite. If user explicitly set DATABASE_URL, honor it.
        explicit_url = os.environ.get("DATABASE_URL")
        if not explicit_url or s.database_url.startswith("postgresql+asyncpg://comic_user:comic_password@localhost"):
            from app.core.desktop_config import get_desktop_database_url
            s.database_url = get_desktop_database_url()
        # Auto-generate JWT secret if not set
        if not os.environ.get("JWT_SECRET_KEY") or s.jwt_secret_key == "change-me-to-a-jwt-secret":
            from app.core.desktop_config import get_desktop_jwt_secret
            s.jwt_secret_key = get_desktop_jwt_secret()
    return s


settings = _build_settings()
```

- [ ] **Step 9: Modify database.py to support SQLite**

Replace the entire contents of `c:\漫剧软件项目\backend\app\core\database.py`:

```python
"""数据库连接管理 - SQLAlchemy 2.0 异步引擎

Supports two drivers:
- PostgreSQL via asyncpg (production / cloud)
- SQLite via aiosqlite (desktop mode fallback when PostgreSQL unavailable)
"""
from typing import AsyncGenerator, Optional
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    """ORM 基类"""
    pass


def create_engine_for_url(
    url: str,
    *,
    echo: bool = False,
    skip_create: bool = False,
) -> AsyncEngine:
    """Create an async engine for the given URL.

    Picks appropriate pool settings based on dialect:
    - PostgreSQL (asyncpg): pool_size=20, max_overflow=10, pool_pre_ping=True
    - SQLite (aiosqlite): no pool_size (uses StaticPool implicitly)

    Args:
        url: SQLAlchemy async URL (e.g. 'postgresql+asyncpg://...' or 'sqlite+aiosqlite:///...')
        echo: Whether to log SQL statements
        skip_create: If True, don't actually connect (for dialect detection tests)
    """
    if url.startswith("sqlite"):
        # SQLite: no pool_size/max_overflow (not supported)
        # Use NullPool to avoid threading issues with SQLite
        from sqlalchemy.pool import NullPool
        return create_async_engine(
            url,
            echo=echo,
            poolclass=NullPool,
            connect_args={"check_same_thread": False},
        )
    # PostgreSQL
    return create_async_engine(
        url,
        echo=echo,
        pool_size=20,
        max_overflow=10,
        pool_pre_ping=True,
    )


# 异步引擎
engine = create_engine_for_url(
    settings.database_url,
    echo=settings.is_development,
)

# 异步会话工厂
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话依赖"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """初始化数据库 (创建所有表 - 仅用于开发/desktop 首次启动)"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """关闭数据库连接"""
    await engine.dispose()
```

- [ ] **Step 10: Run tests to verify they pass**

Run (cwd `c:\漫剧软件项目\backend`): `python -m pytest tests/test_database_fallback.py tests/test_desktop_config.py -v`
Expected: 20 passed (12 + 8)

- [ ] **Step 11: Run full regression to ensure no Phase 1-3 breakage**

Run (cwd `c:\漫剧软件项目\backend`): `python -m pytest`
Expected: 202 passed (182 baseline + 20 new). If any pre-existing test fails, investigate — the `database.py` changes must not break asyncpg flow.

- [ ] **Step 12: Commit**

(Skip — Git not installed in environment.)

---

### Task 2: Data Directory Management + Bootstrap

**Files:**
- Create: `c:\漫剧软件项目\backend\app\core\paths.py`
- Create: `c:\漫剧软件项目\backend\app\core\bootstrap.py`
- Modify: `c:\漫剧软件项目\backend\app\main.py`
- Modify: `c:\漫剧软件项目\backend\app\core\storage.py`
- Create: `c:\漫剧软件项目\backend\tests\test_paths.py`
- Create: `c:\漫剧软件项目\backend\tests\test_bootstrap.py`

- [ ] **Step 1: Write the failing tests for paths**

Create `c:\漫剧软件项目\backend\tests\test_paths.py`:

```python
"""Tests for desktop path resolution."""
import os
import pytest
from pathlib import Path


def test_paths_in_non_desktop_mode(monkeypatch):
    """In non-desktop mode, paths module returns None for desktop paths."""
    monkeypatch.delenv("CS_DESKTOP_MODE", raising=False)
    from app.core.paths import get_uploads_dir
    # Should fall back to ./uploads (relative path, dev mode)
    result = get_uploads_dir()
    assert result == Path("uploads")


def test_paths_in_desktop_mode(monkeypatch, tmp_path):
    """In desktop mode, uploads dir is in data dir."""
    monkeypatch.setenv("CS_DESKTOP_MODE", "1")
    monkeypatch.setenv("CS_DATA_DIR", str(tmp_path))
    from app.core.paths import get_uploads_dir
    result = get_uploads_dir()
    assert result == tmp_path / "uploads"


def test_paths_images_subdir(monkeypatch, tmp_path):
    """Images subdir resolves under uploads."""
    monkeypatch.setenv("CS_DESKTOP_MODE", "1")
    monkeypatch.setenv("CS_DATA_DIR", str(tmp_path))
    from app.core.paths import get_uploads_subdir
    result = get_uploads_subdir("images")
    assert result == tmp_path / "uploads" / "images"


def test_paths_audio_subdir(monkeypatch, tmp_path):
    """Audio subdir resolves under uploads."""
    monkeypatch.setenv("CS_DESKTOP_MODE", "1")
    monkeypatch.setenv("CS_DATA_DIR", str(tmp_path))
    from app.core.paths import get_uploads_subdir
    result = get_uploads_subdir("audio")
    assert result == tmp_path / "uploads" / "audio"


def test_paths_date_subdir_format(monkeypatch, tmp_path):
    """Date-based subdir uses YYYYMMDD format."""
    monkeypatch.setenv("CS_DESKTOP_MODE", "1")
    monkeypatch.setenv("CS_DATA_DIR", str(tmp_path))
    from app.core.paths import get_date_based_path
    from datetime import date
    d = date(2026, 7, 19)
    result = get_date_based_path("images", d)
    assert "20260719" in str(result)
    assert result.parent.parent == tmp_path / "uploads" / "images"


def test_paths_resource_dir_frozen(monkeypatch, tmp_path):
    """In frozen mode, resource dir is the bundle's dir."""
    import sys
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    from app.core.paths import get_resource_dir
    result = get_resource_dir()
    assert result == tmp_path


def test_paths_resource_dir_development(monkeypatch):
    """In development, resource dir is the backend/ root."""
    import sys
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    from app.core.paths import get_resource_dir
    result = get_resource_dir()
    # Should be backend/ root (parent of app/)
    assert (result / "app").exists()
    assert (result / "requirements.txt").exists()


def test_paths_log_file_desktop(monkeypatch, tmp_path):
    """Log file path in desktop mode is in data dir."""
    monkeypatch.setenv("CS_DESKTOP_MODE", "1")
    monkeypatch.setenv("CS_DATA_DIR", str(tmp_path))
    from app.core.paths import get_log_file
    result = get_log_file()
    assert result == tmp_path / "logs" / "app.log"
```

- [ ] **Step 2: Run tests to verify they fail**

Run (cwd `c:\漫剧软件项目\backend`): `python -m pytest tests/test_paths.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.core.paths'`

- [ ] **Step 3: Create paths.py**

Create `c:\漫剧软件项目\backend\app\core\paths.py`:

```python
"""Path resolution for both development and desktop (frozen) modes.

In development:
- uploads/ is a relative dir under backend/
- Resource dir is backend/ root

In desktop mode (CS_DESKTOP_MODE=1):
- uploads/ is data_dir/uploads/
- Resource dir is sys._MEIPASS (PyInstaller bundle) or backend/ root
"""
import os
import sys
from datetime import date
from pathlib import Path
from typing import Optional


def is_desktop_mode() -> bool:
    """Check if running in desktop mode."""
    return os.environ.get("CS_DESKTOP_MODE", "").lower() in ("1", "true", "yes")


def get_data_dir() -> Path:
    """Get the data directory (desktop mode only)."""
    if not is_desktop_mode():
        return Path(".")
    from app.core.desktop_config import get_desktop_data_dir
    return get_desktop_data_dir()


def get_uploads_dir() -> Path:
    """Get the uploads root directory."""
    if is_desktop_mode():
        from app.core.desktop_config import get_desktop_uploads_dir
        return get_desktop_uploads_dir()
    return Path("uploads")


def get_uploads_subdir(subdir: str) -> Path:
    """Get a subdirectory under uploads (e.g. 'images', 'audio')."""
    return get_uploads_dir() / subdir


def get_date_based_path(subdir: str, d: Optional[date] = None) -> Path:
    """Get a date-based path: uploads/<subdir>/<YYYYMMDD>/

    Creates the directory if it doesn't exist.
    """
    if d is None:
        d = date.today()
    date_str = d.strftime("%Y%m%d")
    target = get_uploads_subdir(subdir) / date_str
    target.mkdir(parents=True, exist_ok=True)
    return target


def get_resource_dir() -> Path:
    """Get the resource directory.

    In frozen mode (PyInstaller): sys._MEIPASS
    In development: backend/ root (parent of app/)
    """
    if getattr(sys, "frozen", False):
        # PyInstaller bundle
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
        # Fallback: executable's dir
        return Path(sys.executable).parent
    # Development: backend/ root (this file is at app/core/paths.py)
    return Path(__file__).resolve().parent.parent.parent


def get_log_file() -> Path:
    """Get the log file path."""
    if is_desktop_mode():
        log_dir = get_data_dir() / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        return log_dir / "app.log"
    return Path("logs") / "app.log"
```

- [ ] **Step 4: Run tests to verify they pass**

Run (cwd `c:\漫剧软件项目\backend`): `python -m pytest tests/test_paths.py -v`
Expected: 8 passed

- [ ] **Step 5: Write the failing tests for bootstrap**

Create `c:\漫剧软件项目\backend\tests\test_bootstrap.py`:

```python
"""Tests for first-run bootstrap."""
import pytest
from pathlib import Path


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
    result = asyncio.get_event_loop().run_until_complete(bootstrap_desktop())
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
```

- [ ] **Step 6: Run tests to verify they fail**

Run (cwd `c:\漫剧软件项目\backend`): `python -m pytest tests/test_bootstrap.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.core.bootstrap'`

- [ ] **Step 7: Create bootstrap.py**

Create `c:\漫剧软件项目\backend\app\core\bootstrap.py`:

```python
"""First-run bootstrap for desktop mode.

Creates required directories, initializes the SQLite database, and writes
a version.txt for diagnostics. Safe to call multiple times (idempotent).
"""
import os
from pathlib import Path

from loguru import logger

from app import __version__


async def bootstrap_desktop() -> bool:
    """Run first-run setup for desktop mode.

    Returns:
        True if bootstrap ran (desktop mode), False if skipped (not desktop mode).
    """
    if not os.environ.get("CS_DESKTOP_MODE", "").lower() in ("1", "true", "yes"):
        logger.debug("Bootstrap skipped: not in desktop mode")
        return False

    logger.info("Running desktop bootstrap...")

    # 1. Create data directories
    from app.core.desktop_config import (
        get_desktop_data_dir,
        get_desktop_uploads_dir,
    )
    data_dir = get_desktop_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    get_desktop_uploads_dir().mkdir(parents=True, exist_ok=True)
    (data_dir / "logs").mkdir(parents=True, exist_ok=True)

    # Pre-create upload subdirs
    for subdir in ("images", "audio"):
        (get_desktop_uploads_dir() / subdir).mkdir(parents=True, exist_ok=True)

    # 2. Initialize JWT secret (auto-generates if missing)
    from app.core.desktop_config import get_desktop_jwt_secret
    get_desktop_jwt_secret()

    # 3. Initialize database (create_all is idempotent)
    # Force reimport to pick up desktop mode env vars
    import importlib
    import app.core.config
    importlib.reload(app.core.config)
    import app.core.database
    importlib.reload(app.core.database)
    # Import all models so they register with Base.metadata
    import app.models  # noqa: F401
    from app.core.database import init_db, close_db
    try:
        await init_db()
        logger.info("Database initialized (create_all)")
    except Exception as e:
        logger.error(f"Database init failed: {e}")
        raise
    finally:
        await close_db()

    # 4. Write version.txt for diagnostics
    version_file = data_dir / "version.txt"
    version_file.write_text(
        f"ComicStudio AI Backend\nVersion: {__version__}\nMode: desktop\n",
        encoding="utf-8",
    )

    logger.info(f"Desktop bootstrap complete. Data dir: {data_dir}")
    return True
```

- [ ] **Step 8: Run tests to verify they pass**

Run (cwd `c:\漫剧软件项目\backend`): `python -m pytest tests/test_bootstrap.py tests/test_paths.py -v`
Expected: 18 passed (10 + 8)

- [ ] **Step 9: Modify main.py to call bootstrap in lifespan**

Modify `c:\漫剧软件项目\backend\app\main.py` — find the `lifespan` function and add a desktop bootstrap call. Replace lines 14-27 (the entire lifespan function body):

Find:
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info(f"启动 {settings.app_name} ({settings.app_env})")
    # 开发环境自动建表
    if settings.is_development:
        try:
            await init_db()
            logger.info("数据库表已就绪")
        except Exception as e:
            logger.warning(f"数据库初始化失败 (请确保 PostgreSQL 已启动): {e}")
    yield
    logger.info("关闭数据库连接")
    await close_db()
```

Replace with:
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info(f"启动 {settings.app_name} ({settings.app_env})")
    # 桌面模式: 运行首次启动引导
    import os
    if os.environ.get("CS_DESKTOP_MODE", "").lower() in ("1", "true", "yes"):
        try:
            from app.core.bootstrap import bootstrap_desktop
            await bootstrap_desktop()
            logger.info("桌面模式引导完成")
        except Exception as e:
            logger.error(f"桌面模式引导失败: {e}")
    elif settings.is_development:
        # 开发环境自动建表
        try:
            await init_db()
            logger.info("数据库表已就绪")
        except Exception as e:
            logger.warning(f"数据库初始化失败 (请确保 PostgreSQL 已启动): {e}")
    yield
    logger.info("关闭数据库连接")
    await close_db()
```

- [ ] **Step 10: Modify storage.py to use paths module**

Read `c:\漫剧软件项目\backend\app\core\storage.py` first to understand current structure, then modify the upload path resolution to use `app.core.paths.get_uploads_subdir` when in desktop mode.

For each function in storage.py that writes to `uploads/<subdir>/...`, replace the hardcoded path resolution with:

```python
from app.core.paths import get_uploads_subdir, get_date_based_path
```

And use these helpers instead of relative paths. (The exact edits depend on the current storage.py structure — read it first, then apply minimal edits to use `get_uploads_subdir("images")` etc.)

- [ ] **Step 11: Run full regression**

Run (cwd `c:\漫剧软件项目\backend`): `python -m pytest`
Expected: 220 passed (202 + 18 new from Task 2)

- [ ] **Step 12: Commit**

(Skip — Git not installed.)

---

### Task 3: PyInstaller Spec + Hooks

**Files:**
- Create: `c:\漫剧软件项目\backend\packaging\comicstudio_backend.spec`
- Create: `c:\漫剧软件项目\backend\packaging\hooks\hook-asyncpg.py`
- Create: `c:\漫剧软件项目\backend\packaging\hooks\hook-bcrypt.py`
- Create: `c:\漫剧软件项目\backend\packaging\hooks\hook-loguru.py`
- Create: `c:\漫剧软件项目\backend\packaging\hooks\hook-pydantic_core.py`
- Create: `c:\漫剧软件项目\backend\packaging\hooks\hook-alembic.py`
- Create: `c:\漫剧软件项目\backend\packaging\hooks\hook-ffmpeg_python.py`
- Create: `c:\漫剧软件项目\backend\tests\test_verify_spec.py`

- [ ] **Step 1: Install PyInstaller**

Run (cwd `c:\漫剧软件项目\backend`): `python -m pip install --target .deps pyinstaller==6.11.1`
Expected: `Successfully installed pyinstaller-6.11.1`

Add to `c:\漫剧软件项目\backend\requirements.txt` (append at end):

```
# Packaging
pyinstaller==6.11.1
```

- [ ] **Step 2: Create hook-asyncpg.py**

Create `c:\漫剧软件项目\backend\packaging\hooks\hook-asyncpg.py`:

```python
"""PyInstaller hook for asyncpg.

Bundles the pgproto Cython extension and version metadata.
"""
from PyInstaller.utils.hooks import collect_submodules, copy_metadata

hiddenimports = collect_submodules("asyncpg")
hiddenimports += collect_submodules("asyncpg.pgproto")
datas = copy_metadata("asyncpg")
```

- [ ] **Step 3: Create hook-bcrypt.py**

Create `c:\漫剧软件项目\backend\packaging\hooks\hook-bcrypt.py`:

```python
"""PyInstaller hook for bcrypt.

Bundles the _bcrypt native extension (.pyd on Windows, .so on Linux).
"""
from PyInstaller.utils.hooks import collect_dynamic_libs, copy_metadata

binaries = collect_dynamic_libs("bcrypt")
datas = copy_metadata("bcrypt")
hiddenimports = ["bcrypt._bcrypt"]
```

- [ ] **Step 4: Create hook-loguru.py**

Create `c:\漫剧软件项目\backend\packaging\hooks\hook-loguru.py`:

```python
"""PyInstaller hook for loguru.

Loguru loads default sinks dynamically; ensure they're bundled.
"""
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = collect_submodules("loguru")
hiddenimports += ["loguru._colorizer", "loguru._file_sink", "loguru._defaults"]
```

- [ ] **Step 5: Create hook-pydantic_core.py**

Create `c:\漫剧软件项目\backend\packaging\hooks\hook-pydantic_core.py`:

```python
"""PyInstaller hook for pydantic-core.

Bundles the Rust-compiled _pydantic_core native extension.
"""
from PyInstaller.utils.hooks import collect_dynamic_libs, copy_metadata

binaries = collect_dynamic_libs("pydantic_core")
datas = copy_metadata("pydantic_core")
datas += copy_metadata("pydantic")
```

- [ ] **Step 6: Create hook-alembic.py**

Create `c:\漫剧软件项目\backend\packaging\hooks\hook-alembic.py`:

```python
"""PyInstaller hook for alembic.

Bundles the Mako template files and script.py.mako used for migrations.
"""
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

datas = collect_data_files("alembic", include_py_files=False)
hiddenimports = collect_submodules("alembic")
hiddenimports += ["alembic.script.py_template", "mako.ext"]
```

- [ ] **Step 7: Create hook-ffmpeg_python.py**

Create `c:\漫剧软件项目\backend\packaging\hooks\hook-ffmpeg_python.py`:

```python
"""PyInstaller hook for ffmpeg-python.

ffmpeg-python has a _run.py template that's loaded dynamically.
"""
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

hiddenimports = collect_submodules("ffmpeg")
datas = collect_data_files("ffmpeg")
```

- [ ] **Step 8: Create the main spec file**

Create `c:\漫剧软件项目\backend\packaging\comicstudio_backend.spec`:

```python
# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for ComicStudio AI Backend.

Builds a onedir bundle containing the FastAPI + uvicorn + all deps.
The resulting executable is spawned by the Electron desktop app.
"""
import os
import sys
from PyInstaller.utils.hooks import collect_submodules, collect_data_files, copy_metadata

block_cipher = None

# Project root (backend/)
PROJECT_ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
APP_ROOT = os.path.join(PROJECT_ROOT, "app")

# Hidden imports that PyInstaller can't detect statically
hiddenimports = (
    collect_submodules("app")
    + collect_submodules("uvicorn")
    + collect_submodules("uvicorn.logging")
    + collect_submodules("uvicorn.loops")
    + collect_submodules("uvicorn.loops.auto")
    + collect_submodules("uvicorn.protocols")
    + collect_submodules("uvicorn.protocols.http")
    + collect_submodules("uvicorn.protocols.http.auto")
    + collect_submodules("uvicorn.protocols.websockets")
    + collect_submodules("uvicorn.protocols.websockets.auto")
    + collect_submodules("uvicorn.lifespan")
    + collect_submodules("uvicorn.lifespan.on")
    + collect_submodules("sqlalchemy")
    + collect_submodules("sqlalchemy.dialects")
    + collect_submodules("sqlalchemy.dialects.sqlite")
    + collect_submodules("sqlalchemy.dialects.postgresql")
    + collect_submodules("sqlalchemy.ext.asyncio")
    + collect_submodules("aiosqlite")
    + collect_submodules("asyncpg")
    + collect_submodules("edge_tts")
    + collect_submodules("ffmpeg")
    + collect_submodules("pydantic")
    + collect_submodules("pydantic_core")
    + collect_submodules("pydantic_settings")
    + collect_submodules("loguru")
    + collect_submodules("jose")
    + collect_submodules("passlib")
    + collect_submodules("passlib.handlers")
    + collect_submodules("passlib.handlers.bcrypt")
    # Asyncpg protocol modules
    + ["asyncpg.pgproto.pgproto", "asyncpg.protocol", "asyncpg.protocol.protocol"]
    # App-specific
    + ["app.main", "app.core.config", "app.core.database", "app.core.bootstrap",
       "app.core.paths", "app.core.desktop_config"]
    + collect_submodules("app.api")
    + collect_submodules("app.models")
    + collect_submodules("app.schemas")
    + collect_submodules("app.services")
    + collect_submodules("app.engines")
)

# Data files to bundle
datas = (
    copy_metadata("fastapi")
    + copy_metadata("pydantic")
    + copy_metadata("pydantic_core")
    + copy_metadata("pydantic_settings")
    + copy_metadata("uvicorn")
    + copy_metadata("starlette")
    + copy_metadata("asyncpg")
    + copy_metadata("aiosqlite")
    + copy_metadata("loguru")
    + collect_data_files("app", include_py_files=True)
)

# Native binaries
binaries = (
    collect_dynamic_libs("bcrypt")
    + collect_dynamic_libs("pydantic_core")
) if 'collect_dynamic_libs' in dir() else []

# Add hooks dir
hookspath = [os.path.join(SPECPATH, "hooks")]

a = Analysis(
    [os.path.join(SPECPATH, "entry.py")],
    pathex=[PROJECT_ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=hookspath,
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "PIL.ImageTk",
        "torch",
        "diffusers",
        "transformers",
        "tensorflow",
        "CUDA",
    ],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="comicstudio-backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="comicstudio-backend",
)
```

- [ ] **Step 9: Create verify_spec.py**

Create `c:\漫剧软件项目\backend\packaging\verify_spec.py`:

```python
"""Verify the PyInstaller spec is complete and well-formed.

Run as: python packaging/verify_spec.py
Exits with 0 if OK, 1 if problems found.
"""
import ast
import os
import sys
from pathlib import Path


SPEC_FILE = Path(__file__).parent / "comicstudio_backend.spec"
HOOKS_DIR = Path(__file__).parent / "hooks"
PROJECT_ROOT = Path(__file__).parent.parent


def verify_spec_exists() -> bool:
    return SPEC_FILE.is_file()


def verify_spec_parses() -> bool:
    try:
        with open(SPEC_FILE, "r", encoding="utf-8") as f:
            ast.parse(f.read(), filename=str(SPEC_FILE))
        return True
    except SyntaxError as e:
        print(f"Spec syntax error: {e}")
        return False


def verify_entry_point_referenced() -> bool:
    """Spec must reference entry.py as the entry point."""
    content = SPEC_FILE.read_text(encoding="utf-8")
    return "entry.py" in content


def verify_hooks_exist() -> bool:
    """All expected hook files must exist."""
    expected = [
        "hook-asyncpg.py",
        "hook-bcrypt.py",
        "hook-loguru.py",
        "hook-pydantic_core.py",
        "hook-alembic.py",
        "hook-ffmpeg_python.py",
    ]
    for name in expected:
        if not (HOOKS_DIR / name).is_file():
            print(f"Missing hook: {name}")
            return False
    return True


def verify_app_modules_listed() -> bool:
    """Spec must include app.main, app.core.config, etc. as hidden imports."""
    content = SPEC_FILE.read_text(encoding="utf-8")
    required = ["app.main", "app.core.config", "app.core.database"]
    return all(name in content for name in required)


def verify_excludes_safe() -> bool:
    """Excluded modules must not include things we need."""
    content = SPEC_FILE.read_text(encoding="utf-8")
    # tkinter is always safe to exclude; torch/transformers are excluded because
    # we don't use them in the zero-cost stack
    forbidden_excludes = ["fastapi", "uvicorn", "sqlalchemy", "pydantic"]
    # Check the excludes=[...] block
    import re
    match = re.search(r"excludes=\[(.*?)\]", content, re.DOTALL)
    if not match:
        return True
    excludes_block = match.group(1)
    return not any(f'"{mod}"' in excludes_block for mod in forbidden_excludes)


def main() -> int:
    checks = [
        ("Spec file exists", verify_spec_exists),
        ("Spec parses as Python", verify_spec_parses),
        ("entry.py referenced", verify_entry_point_referenced),
        ("All hooks exist", verify_hooks_exist),
        ("App modules listed", verify_app_modules_listed),
        ("Excludes are safe", verify_excludes_safe),
    ]
    all_ok = True
    for name, check in checks:
        ok = check()
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {name}")
        if not ok:
            all_ok = False
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 10: Write the failing test for spec verification**

Create `c:\漫剧软件项目\backend\tests\test_verify_spec.py`:

```python
"""Tests for PyInstaller spec verification."""
import os
import sys
from pathlib import Path

import pytest


PACKAGING_DIR = Path(__file__).parent.parent / "packaging"


def test_spec_file_exists():
    assert (PACKAGING_DIR / "comicstudio_backend.spec").is_file()


def test_hooks_dir_exists():
    assert (PACKAGING_DIR / "hooks").is_dir()


def test_all_expected_hooks_exist():
    expected = [
        "hook-asyncpg.py",
        "hook-bcrypt.py",
        "hook-loguru.py",
        "hook-pydantic_core.py",
        "hook-alembic.py",
        "hook-ffmpeg_python.py",
    ]
    for name in expected:
        assert (PACKAGING_DIR / "hooks" / name).is_file(), f"Missing hook: {name}"


def test_entry_py_referenced_in_spec():
    spec = (PACKAGING_DIR / "comicstudio_backend.spec").read_text(encoding="utf-8")
    assert "entry.py" in spec


def test_verify_spec_script_passes():
    """Running verify_spec.py should exit 0."""
    import subprocess
    result = subprocess.run(
        [sys.executable, str(PACKAGING_DIR / "verify_spec.py")],
        capture_output=True,
        text=True,
        cwd=str(PACKAGING_DIR.parent),
    )
    assert result.returncode == 0, f"verify_spec failed:\n{result.stdout}\n{result.stderr}"


def test_spec_includes_app_modules():
    spec = (PACKAGING_DIR / "comicstudio_backend.spec").read_text(encoding="utf-8")
    assert "app.main" in spec
    assert "app.core.config" in spec
    assert "app.core.database" in spec
    assert "app.core.bootstrap" in spec
```

- [ ] **Step 11: Run tests to verify they pass**

Run (cwd `c:\漫剧软件项目\backend`): `python -m pytest tests/test_verify_spec.py -v`
Expected: 6 passed

- [ ] **Step 12: Run verify_spec.py directly to confirm**

Run (cwd `c:\漫剧软件项目\backend`): `python packaging/verify_spec.py`
Expected: All 6 checks PASS, exit code 0

- [ ] **Step 13: Run full regression**

Run (cwd `c:\漫剧软件项目\backend`): `python -m pytest`
Expected: 226 passed (220 + 6 new from Task 3)

- [ ] **Step 14: Commit**

(Skip — Git not installed.)

---

### Task 4: Entry Script + Runtime + Build Script

**Files:**
- Create: `c:\漫剧软件项目\backend\packaging\entry.py`
- Create: `c:\漫剧软件项目\backend\packaging\runtime.py`
- Create: `c:\漫剧软件项目\backend\packaging\build.py`
- Create: `c:\漫剧软件项目\backend\tests\test_runtime.py`
- Create: `c:\漫剧软件项目\backend\tests\test_build_script.py`

- [ ] **Step 1: Write the failing tests for runtime**

Create `c:\漫剧软件项目\backend\tests\test_runtime.py`:

```python
"""Tests for runtime path resolution."""
import os
import sys
import pytest
from pathlib import Path


def test_runtime_frozen_detection_default(monkeypatch):
    """By default (not frozen), runtime is development."""
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    from packaging.runtime import is_frozen
    assert is_frozen() is False


def test_runtime_frozen_detection_when_frozen(monkeypatch):
    """When sys.frozen is True, is_frozen returns True."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    from packaging.runtime import is_frozen
    assert is_frozen() is True


def test_runtime_get_bundle_dir_frozen(monkeypatch, tmp_path):
    """In frozen mode, bundle dir is sys._MEIPASS."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    from packaging.runtime import get_bundle_dir
    assert get_bundle_dir() == tmp_path


def test_runtime_get_bundle_dir_development(monkeypatch):
    """In development, bundle dir is backend/ root."""
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    from packaging.runtime import get_bundle_dir
    result = get_bundle_dir()
    assert (result / "app").exists()
    assert (result / "requirements.txt").exists()


def test_runtime_get_executable_dir_frozen(monkeypatch, tmp_path):
    """In frozen mode, executable dir is the dir of sys.executable."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    fake_exe = tmp_path / "comicstudio-backend.exe"
    fake_exe.write_text("fake")
    monkeypatch.setattr(sys, "executable", str(fake_exe))
    from packaging.runtime import get_executable_dir
    assert get_executable_dir() == tmp_path


def test_runtime_get_data_dir_from_env(monkeypatch, tmp_path):
    """CS_DATA_DIR env var takes precedence."""
    monkeypatch.setenv("CS_DATA_DIR", str(tmp_path))
    from packaging.runtime import get_data_dir
    assert get_data_dir() == tmp_path


def test_runtime_get_data_dir_default_user_home(monkeypatch, tmp_path):
    """Default data dir is user home / comicstudio-data."""
    monkeypatch.delenv("CS_DATA_DIR", raising=False)
    monkeypatch.setattr("os.path.expanduser", lambda p: str(tmp_path) if p == "~" else p)
    from packaging.runtime import get_data_dir
    result = get_data_dir()
    assert result == tmp_path / "comicstudio-data"


def test_runtime_setup_desktop_env(monkeypatch, tmp_path):
    """setup_desktop_env sets CS_DESKTOP_MODE and CS_DATA_DIR if not set."""
    monkeypatch.delenv("CS_DESKTOP_MODE", raising=False)
    monkeypatch.delenv("CS_DATA_DIR", raising=False)
    monkeypatch.setattr("os.path.expanduser", lambda p: str(tmp_path) if p == "~" else p)
    from packaging.runtime import setup_desktop_env
    setup_desktop_env()
    assert os.environ.get("CS_DESKTOP_MODE") == "1"
    assert os.environ.get("CS_DATA_DIR") == str(tmp_path / "comicstudio-data")
```

- [ ] **Step 2: Run tests to verify they fail**

Run (cwd `c:\漫剧软件项目\backend`): `python -m pytest tests/test_runtime.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'packaging.runtime'`

Note: `packaging` is also a stdlib module. To avoid conflict, ensure tests run from `backend/` root so the local `packaging/` dir takes precedence. If conflict occurs, rename the test's import to use absolute path or add `__init__.py` to `packaging/`.

- [ ] **Step 3: Create packaging/__init__.py to make it a package**

Create `c:\漫剧软件项目\backend\packaging\__init__.py`:

```python
"""ComicStudio AI Backend Packaging."""
```

- [ ] **Step 4: Create runtime.py**

Create `c:\漫剧软件项目\backend\packaging\runtime.py`:

```python
"""Runtime path resolution for frozen (PyInstaller) and development modes.

This module is imported by entry.py to set up the environment before
launching uvicorn.
"""
import os
import sys
from pathlib import Path


def is_frozen() -> bool:
    """Check if running as a PyInstaller frozen bundle."""
    return getattr(sys, "frozen", False)


def get_bundle_dir() -> Path:
    """Get the bundle directory (where PyInstaller extracted resources).

    In frozen mode: sys._MEIPASS
    In development: backend/ project root
    """
    if is_frozen():
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
        return Path(sys.executable).parent
    # Development: this file is at backend/packaging/runtime.py
    return Path(__file__).resolve().parent.parent


def get_executable_dir() -> Path:
    """Get the directory containing the executable (frozen) or cwd (dev)."""
    if is_frozen():
        return Path(sys.executable).parent
    return Path.cwd()


def get_data_dir() -> Path:
    """Get the data directory.

    Priority:
    1. CS_DATA_DIR env var
    2. ~/comicstudio-data (user home)
    """
    env_data_dir = os.environ.get("CS_DATA_DIR")
    if env_data_dir:
        return Path(env_data_dir).resolve()
    return Path(os.path.expanduser("~")) / "comicstudio-data"


def setup_desktop_env() -> None:
    """Set up environment variables for desktop mode.

    Sets CS_DESKTOP_MODE=1 and CS_DATA_DIR (if not already set).
    """
    os.environ.setdefault("CS_DESKTOP_MODE", "1")
    if "CS_DATA_DIR" not in os.environ:
        data_dir = get_data_dir()
        data_dir.mkdir(parents=True, exist_ok=True)
        os.environ["CS_DATA_DIR"] = str(data_dir)


def ensure_path(project_root: Path) -> None:
    """Ensure the project root is on sys.path (for development mode)."""
    project_root_str = str(project_root)
    if project_root_str not in sys.path:
        sys.path.insert(0, project_root_str)
```

- [ ] **Step 5: Run tests to verify they pass**

Run (cwd `c:\漫剧软件项目\backend`): `python -m pytest tests/test_runtime.py -v`
Expected: 8 passed

- [ ] **Step 6: Create entry.py**

Create `c:\漫剧软件项目\backend\packaging\entry.py`:

```python
"""Entry point for the packaged ComicStudio AI Backend.

This script is what PyInstaller bundles. It:
1. Sets up the desktop environment (CS_DESKTOP_MODE, CS_DATA_DIR)
2. Ensures project root is on sys.path (for dev mode)
3. Launches uvicorn with the FastAPI app

Usage (development):
    python -m packaging.entry

Usage (frozen):
    comicstudio-backend.exe
"""
import os
import sys
from pathlib import Path


def main() -> None:
    """Launch the backend."""
    # 1. Setup desktop env
    from packaging.runtime import setup_desktop_env, is_frozen, get_bundle_dir, ensure_path

    setup_desktop_env()

    # 2. In development, ensure project root is on sys.path
    if not is_frozen():
        project_root = Path(__file__).resolve().parent.parent
        ensure_path(project_root)

    # 3. Parse CLI args (override defaults)
    host = os.environ.get("APP_HOST", "127.0.0.1")
    port = int(os.environ.get("APP_PORT", "8000"))

    # Allow command-line overrides
    if "--host" in sys.argv:
        idx = sys.argv.index("--host")
        host = sys.argv[idx + 1]
    if "--port" in sys.argv:
        idx = sys.argv.index("--port")
        port = int(sys.argv[idx + 1])

    # 4. Configure logging
    from loguru import logger
    import logging

    logger.remove()
    logger.add(sys.stderr, level="INFO")

    # 5. Import and run uvicorn
    logger.info(f"Starting ComicStudio AI Backend on {host}:{port}")
    logger.info(f"Frozen: {is_frozen()}, Bundle: {get_bundle_dir()}")
    logger.info(f"Data dir: {os.environ.get('CS_DATA_DIR')}")

    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        log_level="info",
        access_log=True,
        workers=1,  # Single worker for desktop
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 7: Write the failing tests for build script**

Create `c:\漫剧软件项目\backend\tests\test_build_script.py`:

```python
"""Tests for the build script (without actually building)."""
import os
import sys
import subprocess
from pathlib import Path
import pytest


PACKAGING_DIR = Path(__file__).parent.parent / "packaging"
BUILD_SCRIPT = PACKAGING_DIR / "build.py"


def test_build_script_exists():
    assert BUILD_SCRIPT.is_file()


def test_build_script_parses():
    import ast
    content = BUILD_SCRIPT.read_text(encoding="utf-8")
    ast.parse(content, filename=str(BUILD_SCRIPT))


def test_build_script_imports_pyinstaller():
    content = BUILD_SCRIPT.read_text(encoding="utf-8")
    assert "PyInstaller" in content or "pyinstaller" in content


def test_build_script_references_spec():
    content = BUILD_SCRIPT.read_text(encoding="utf-8")
    assert "comicstudio_backend.spec" in content


def test_build_script_help_works():
    """Running build.py --help should exit 0 and show usage."""
    result = subprocess.run(
        [sys.executable, str(BUILD_SCRIPT), "--help"],
        capture_output=True,
        text=True,
        cwd=str(PACKAGING_DIR.parent),
        timeout=30,
    )
    assert result.returncode == 0
    assert "usage" in result.stdout.lower() or "usage" in result.stderr.lower()
```

- [ ] **Step 8: Run tests to verify they fail**

Run (cwd `c:\漫剧软件项目\backend`): `python -m pytest tests/test_build_script.py -v`
Expected: FAIL with `FileNotFoundError` (build.py doesn't exist yet)

- [ ] **Step 9: Create build.py**

Create `c:\漫剧软件项目\backend\packaging\build.py`:

```python
#!/usr/bin/env python
"""Build script for the ComicStudio AI Backend.

Wraps PyInstaller with the project-specific spec file.

Usage:
    python packaging/build.py              # Build with existing spec
    python packaging/build.py --clean      # Clean dist/ and build/ first
    python packaging/build.py --help       # Show this help
"""
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PACKAGING_DIR = PROJECT_ROOT / "packaging"
SPEC_FILE = PACKAGING_DIR / "comicstudio_backend.spec"
DIST_DIR = PROJECT_ROOT / "dist"
BUILD_DIR = PROJECT_ROOT / "build"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build ComicStudio AI Backend with PyInstaller",
        usage="python packaging/build.py [--clean]",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Clean dist/ and build/ directories before building",
    )
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="Skip spec verification before building",
    )
    return parser.parse_args()


def clean_build_dirs() -> None:
    """Remove dist/ and build/ directories."""
    for d in (DIST_DIR, BUILD_DIR):
        if d.exists():
            print(f"Cleaning {d}...")
            shutil.rmtree(d, ignore_errors=True)


def verify_spec() -> bool:
    """Run verify_spec.py to ensure spec is well-formed."""
    print("Verifying spec...")
    result = subprocess.run(
        [sys.executable, str(PACKAGING_DIR / "verify_spec.py")],
        cwd=str(PROJECT_ROOT),
    )
    if result.returncode != 0:
        print("Spec verification failed!")
        return False
    print("Spec verification passed.")
    return True


def run_pyinstaller() -> int:
    """Run PyInstaller with the spec file."""
    print(f"Running PyInstaller with spec: {SPEC_FILE}")
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        str(SPEC_FILE),
        "--distpath",
        str(DIST_DIR),
        "--workpath",
        str(BUILD_DIR),
        "--noconfirm",
    ]
    print(f"Command: {' '.join(cmd)}")
    return subprocess.call(cmd, cwd=str(PROJECT_ROOT))


def main() -> int:
    args = parse_args()

    if args.clean:
        clean_build_dirs()

    if not args.no_verify:
        if not verify_spec():
            return 1

    exit_code = run_pyinstaller()
    if exit_code != 0:
        print(f"Build failed with exit code {exit_code}")
        return exit_code

    # Verify output exists
    expected_output = DIST_DIR / "comicstudio-backend" / "comicstudio-backend.exe"
    if os.name != "nt":
        expected_output = DIST_DIR / "comicstudio-backend" / "comicstudio-backend"

    if expected_output.exists():
        print(f"\nBuild successful! Output: {expected_output}")
        return 0
    else:
        print(f"\nBuild completed but expected output not found: {expected_output}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 10: Run tests to verify they pass**

Run (cwd `c:\漫剧软件项目\backend`): `python -m pytest tests/test_build_script.py tests/test_runtime.py -v`
Expected: 13 passed (5 + 8)

- [ ] **Step 11: Run full regression**

Run (cwd `c:\漫剧软件项目\backend`): `python -m pytest`
Expected: 239 passed (226 + 13 new from Task 4)

- [ ] **Step 12: Commit**

(Skip — Git not installed.)

---

### Task 5: Execute Build + Integration Test

**Files:**
- Create: `c:\漫剧软件项目\backend\tests\test_e2e_packaged.py`

- [ ] **Step 1: Run the actual build**

Run (cwd `c:\漫剧软件项目\backend`): `python packaging/build.py --clean`
Expected: Build completes successfully, output at `dist/comicstudio-backend/comicstudio-backend.exe`

Note: This may take 5-10 minutes on first run as PyInstaller analyzes all imports. If it fails:
- Check the error for missing hidden imports → add to spec's hiddenimports list
- Check for missing data files → add to spec's datas list
- Native module issues → ensure hook files are correct

If build fails due to PyInstaller not finding a module, add it to `hiddenimports` in the spec and rebuild.

- [ ] **Step 2: Verify the executable was created**

Run (cwd `c:\漫剧软件项目\backend`): `dir dist\comicstudio-backend\`
Expected: `comicstudio-backend.exe` (Windows) or `comicstudio-backend` (Linux/Mac) exists

- [ ] **Step 3: Test launching the executable (manual smoke test)**

Open a terminal and run:
`c:\漫剧软件项目\backend\dist\comicstudio-backend\comicstudio-backend.exe --port 8765`

Expected output:
```
Starting ComicStudio AI Backend on 127.0.0.1:8765
...
INFO:     Uvicorn running on http://127.0.0.1:8765
INFO:     Application startup complete.
```

In another terminal:
`curl http://127.0.0.1:8765/health`
Expected: `{"code":0,"message":"success","data":{"status":"ok","version":"0.1.0"}}`

Then stop the server with Ctrl+C.

- [ ] **Step 4: Write the e2e test**

Create `c:\漫剧软件项目\backend\tests\test_e2e_packaged.py`:

```python
"""End-to-end tests for the packaged backend.

These tests spawn the built executable and verify it serves requests.
They are skipped if the executable doesn't exist (e.g., in CI without build).
"""
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXECUTABLE_PATH = (
    PROJECT_ROOT
    / "dist"
    / "comicstudio-backend"
    / ("comicstudio-backend.exe" if os.name == "nt" else "comicstudio-backend")
)


def find_free_port() -> int:
    """Find a free TCP port for the test server."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_for_health(url: str, timeout: float = 60.0) -> bool:
    """Poll /health until it responds or timeout."""
    import time
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = httpx.get(f"{url}/health", timeout=2.0)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(1.0)
    return False


@pytest.mark.skipif(not EXECUTABLE_PATH.exists(), reason="Packaged executable not built")
class TestPackagedBackend:
    """Tests that spawn the packaged backend executable."""

    @pytest.fixture
    def backend_process(self, tmp_path):
        """Start the packaged backend on a free port."""
        port = find_free_port()
        env = os.environ.copy()
        env["CS_DESKTOP_MODE"] = "1"
        env["CS_DATA_DIR"] = str(tmp_path)
        env["APP_PORT"] = str(port)
        env["APP_HOST"] = "127.0.0.1"

        proc = subprocess.Popen(
            [str(EXECUTABLE_PATH), "--port", str(port), "--host", "127.0.0.1"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )

        url = f"http://127.0.0.1:{port}"
        if not wait_for_health(url, timeout=60):
            stdout, stderr = proc.communicate(timeout=5)
            pytest.fail(
                f"Backend didn't start in time.\nstdout: {stdout.decode()}\nstderr: {stderr.decode()}"
            )

        yield url

        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()

    def test_health_endpoint(self, backend_process):
        """The /health endpoint returns 200 with version info."""
        url = backend_process
        r = httpx.get(f"{url}/health", timeout=5.0)
        assert r.status_code == 200
        data = r.json()
        assert data["code"] == 0
        assert data["data"]["status"] == "ok"
        assert data["data"]["version"] == "0.1.0"

    def test_root_endpoint(self, backend_process):
        """The / endpoint returns app name."""
        url = backend_process
        r = httpx.get(f"{url}/", timeout=5.0)
        assert r.status_code == 200
        data = r.json()
        assert "ComicStudio" in data["data"]["name"]

    def test_openapi_endpoint(self, backend_process):
        """The /openapi.json endpoint returns the OpenAPI schema."""
        url = backend_process
        r = httpx.get(f"{url}/openapi.json", timeout=5.0)
        assert r.status_code == 200
        schema = r.json()
        assert "paths" in schema
        assert "/health" in schema["paths"]

    def test_sqlite_db_created(self, backend_process, tmp_path):
        """The SQLite database file is created in the data dir."""
        db_file = tmp_path / "comicstudio.db"
        assert db_file.exists()
        assert db_file.stat().st_size > 0

    def test_uploads_dir_created(self, backend_process, tmp_path):
        """The uploads directory is created in the data dir."""
        uploads_dir = tmp_path / "uploads"
        assert uploads_dir.exists()
        assert uploads_dir.is_dir()

    def test_jwt_secret_created(self, backend_process, tmp_path):
        """The JWT secret file is created."""
        secret_file = tmp_path / ".jwt_secret"
        assert secret_file.exists()
        secret = secret_file.read_text(encoding="utf-8")
        assert len(secret) >= 32

    def test_version_file_created(self, backend_process, tmp_path):
        """The version.txt file is created with version info."""
        version_file = tmp_path / "version.txt"
        assert version_file.exists()
        content = version_file.read_text(encoding="utf-8")
        assert "0.1.0" in content

    def test_logs_dir_created(self, backend_process, tmp_path):
        """The logs directory is created."""
        logs_dir = tmp_path / "logs"
        assert logs_dir.exists()

    def test_executable_size_reasonable(self):
        """The executable should be at least 10MB (sanity check)."""
        size = EXECUTABLE_PATH.stat().st_size
        assert size > 10 * 1024 * 1024, f"Executable is only {size} bytes"

    def test_executable_no_python_dependency(self):
        """The executable should not crash immediately if PYTHONHOME is unset.

        This is a sanity check that the bundle is self-contained.
        """
        port = find_free_port()
        env = os.environ.copy()
        env.pop("PYTHONHOME", None)
        env.pop("PYTHONPATH", None)
        env["CS_DESKTOP_MODE"] = "1"
        env["CS_DATA_DIR"] = str(Path(__file__).parent / "tmp_test_data")
        env["APP_PORT"] = str(port)

        try:
            proc = subprocess.Popen(
                [str(EXECUTABLE_PATH), "--port", str(port)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
            )
            # Wait briefly to see if it crashes
            time.sleep(3)
            assert proc.poll() is None, "Process exited immediately"
            proc.terminate()
            proc.wait(timeout=10)
        finally:
            # Cleanup test data
            import shutil
            test_data = Path(__file__).parent / "tmp_test_data"
            if test_data.exists():
                shutil.rmtree(test_data, ignore_errors=True)
```

- [ ] **Step 5: Run the e2e tests**

Run (cwd `c:\漫剧软件项目\backend`): `python -m pytest tests/test_e2e_packaged.py -v --timeout=120`
Expected: 10 passed (if executable was built in Step 1)

If tests are SKIPPED with "Packaged executable not built", go back to Step 1 and build the executable first.

- [ ] **Step 6: Run full regression**

Run (cwd `c:\漫剧软件项目\backend`): `python -m pytest`
Expected: 249 passed (239 + 10 new from Task 5)

- [ ] **Step 7: Commit**

(Skip — Git not installed.)

---

### Task 6: Electron Integration

**Files:**
- Modify: `c:\漫剧软件项目\desktop\src\main\constants.ts`
- Modify: `c:\漫剧软件项目\desktop\src\main\backend\backend-process.ts`
- Modify: `c:\漫剧软件项目\desktop\electron-builder.yml`
- Modify: `c:\漫剧软件项目\desktop\src\test\integration.test.ts`
- Create: `c:\漫剧软件项目\desktop\src\test\backend-process-packaged.test.ts`

- [ ] **Step 1: Modify constants.ts to add packaged backend config**

Modify `c:\漫剧软件项目\desktop\src\main\constants.ts` — find the `LOCAL_BACKEND_CONFIG` block and add a new constant after it:

Find:
```typescript
// Local backend spawn configuration (only used when mode = 'local-python')
export const LOCAL_BACKEND_CONFIG = {
  // Path to backend directory relative to desktop/
  backendDir: process.env.CS_BACKEND_DIR || '../../backend',
  // Python executable (venv preferred if available)
  pythonExecutable: process.env.CS_PYTHON || 'python',
  // uvicorn module and app target
  module: 'uvicorn',
  appTarget: 'app.main:app',
  host: '127.0.0.1',
  port: 8000,
} as const
```

Replace with:
```typescript
// Local backend spawn configuration (only used when mode = 'local-python')
// Two sub-modes:
//   - python source: spawn `python -m uvicorn app.main:app` (dev)
//   - packaged exe:  spawn the PyInstaller-built executable (production)
export const LOCAL_BACKEND_CONFIG = {
  // Path to backend directory relative to desktop/ (dev mode)
  backendDir: process.env.CS_BACKEND_DIR || '../../backend',
  // Python executable (venv preferred if available) — dev mode
  pythonExecutable: process.env.CS_PYTHON || 'python',
  // uvicorn module and app target — dev mode
  module: 'uvicorn',
  appTarget: 'app.main:app',
  host: '127.0.0.1',
  port: 8000,
} as const

// Packaged backend executable (Phase 5: PyInstaller-built)
// When mode = 'local-python' and this path exists, spawn it directly.
// Otherwise fall back to python source mode.
export const PACKAGED_BACKEND_CONFIG = {
  // Path to packaged backend dir, relative to desktop/
  packagedDir: process.env.CS_PACKAGED_BACKEND_DIR || '../backend/dist/comicstudio-backend',
  // Executable name (no extension; .exe added on Windows)
  executableName: 'comicstudio-backend',
  // Host/port passed as CLI args
  host: '127.0.0.1',
  port: 8000,
} as const

// Resolve the actual executable path based on platform
export function getPackagedBackendPath(): string {
  const path = require('path') as typeof import('path')
  const exeName = process.platform === 'win32'
    ? `${PACKAGED_BACKEND_CONFIG.executableName}.exe`
    : PACKAGED_BACKEND_CONFIG.executableName
  return path.resolve(
    // From desktop/, go up to project root, then into backend/dist/...
    // In packaged Electron app, this resolves via extraResources
    process.env.CS_PACKAGED_BACKEND_PATH ||
      path.resolve(__dirname, '..', '..', '..', PACKAGED_BACKEND_CONFIG.packagedDir, exeName)
  )
}
```

- [ ] **Step 2: Modify backend-process.ts to support packaged exe mode**

Modify `c:\漫剧软件项目\desktop\src\main\backend\backend-process.ts` — replace the `start()` method's spawn logic. Find this block:

```typescript
    if (this.proc && this.proc.exitCode === null) {
      // Already running
      return true
    }

    this.setStatus('starting')

    const backendDir = path.resolve(app.getAppPath(), LOCAL_BACKEND_CONFIG.backendDir)
    const args = [
      '-m',
      LOCAL_BACKEND_CONFIG.module,
      LOCAL_BACKEND_CONFIG.appTarget,
      '--host',
      LOCAL_BACKEND_CONFIG.host,
      '--port',
      String(LOCAL_BACKEND_CONFIG.port),
    ]

    try {
      this.proc = spawn(LOCAL_BACKEND_CONFIG.pythonExecutable, args, {
        cwd: backendDir,
        env: { ...process.env, PYTHONUNBUFFERED: '1' },
        stdio: ['ignore', 'pipe', 'pipe'],
      })
    } catch (e) {
      this.setStatus('failed')
      this.emit('error', { message: `Failed to spawn backend: ${(e as Error).message}` })
      return false
    }
```

Replace with:

```typescript
    if (this.proc && this.proc.exitCode === null) {
      // Already running
      return true
    }

    this.setStatus('starting')

    // Detect packaged backend mode: if the packaged exe exists, spawn it directly.
    // Otherwise fall back to python source mode (dev).
    const fs = await import('fs')
    const packagedExePath = getPackagedBackendPath()
    const usePackaged = fs.existsSync(packagedExePath)

    let command: string
    let args: string[]
    let cwd: string
    let env: NodeJS.ProcessEnv = { ...process.env, PYTHONUNBUFFERED: '1' }

    if (usePackaged) {
      // Packaged exe mode (Phase 5)
      command = packagedExePath
      args = [
        '--host', LOCAL_BACKEND_CONFIG.host,
        '--port', String(LOCAL_BACKEND_CONFIG.port),
      ]
      cwd = path.dirname(packagedExePath)
      env.CS_DESKTOP_MODE = '1'
      // Data dir: per-user userData
      env.CS_DATA_DIR = app.getPath('userData')
    } else {
      // Python source mode (dev fallback)
      const backendDir = path.resolve(app.getAppPath(), LOCAL_BACKEND_CONFIG.backendDir)
      command = LOCAL_BACKEND_CONFIG.pythonExecutable
      args = [
        '-m',
        LOCAL_BACKEND_CONFIG.module,
        LOCAL_BACKEND_CONFIG.appTarget,
        '--host',
        LOCAL_BACKEND_CONFIG.host,
        '--port',
        String(LOCAL_BACKEND_CONFIG.port),
      ]
      cwd = backendDir
    }

    try {
      this.proc = spawn(command, args, {
        cwd,
        env,
        stdio: ['ignore', 'pipe', 'pipe'],
      })
    } catch (e) {
      this.setStatus('failed')
      this.emit('error', { message: `Failed to spawn backend: ${(e as Error).message}` })
      return false
    }
```

Also, update the import at the top of the file. Find:

```typescript
import {
  BACKEND_MODE,
  LOCAL_BACKEND_CONFIG,
  BACKEND_STARTUP_TIMEOUT_MS,
  BACKEND_SHUTDOWN_TIMEOUT_MS,
} from '../constants'
```

Replace with:

```typescript
import {
  BACKEND_MODE,
  LOCAL_BACKEND_CONFIG,
  BACKEND_STARTUP_TIMEOUT_MS,
  BACKEND_SHUTDOWN_TIMEOUT_MS,
  getPackagedBackendPath,
} from '../constants'
```

And in the `start()` method, the `waitForBackendHealth` URL is currently constructed from `LOCAL_BACKEND_CONFIG.host/port`. This is fine since both modes use the same host/port. But update it to use the actual port:

Find:
```typescript
    // Wait for health check
    const healthy = await waitForBackendHealth(
      `http://${LOCAL_BACKEND_CONFIG.host}:${LOCAL_BACKEND_CONFIG.port}`,
      BACKEND_STARTUP_TIMEOUT_MS
    )
```

Replace with:
```typescript
    // Wait for health check
    const healthy = await waitForBackendHealth(
      `http://${LOCAL_BACKEND_CONFIG.host}:${LOCAL_BACKEND_CONFIG.port}`,
      BACKEND_STARTUP_TIMEOUT_MS
    )

    // Log which mode was used (for debugging)
    if (usePackaged) {
      console.log('[backend] Started packaged executable:', packagedExePath)
    } else {
      console.log('[backend] Started python source mode')
    }
```

- [ ] **Step 3: Modify electron-builder.yml to include packaged backend**

Read `c:\漫剧软件项目\desktop\electron-builder.yml` first to understand current structure.

Then add an `extraResources` field to include the packaged backend in the Electron app bundle. Add this near the top level (after `asar`):

```yaml
# Bundle the packaged Python backend (Phase 5)
extraResources:
  - from: ../backend/dist/comicstudio-backend
    to: comicstudio-backend
    filter: ["**/*"]
```

Use the Edit tool to insert this after the existing `asar: true` line (or wherever appropriate in the existing YAML structure).

- [ ] **Step 4: Update the packaged backend path to resolve from extraResources**

The `getPackagedBackendPath()` function in constants.ts (added in Step 1) uses `__dirname` based resolution. In a packaged Electron app, `__dirname` resolves to `app.asar` or similar. We need to update it to also check `process.resourcesPath` (where `extraResources` lands in production).

Modify `c:\漫剧软件项目\desktop\src\main\constants.ts` — find the `getPackagedBackendPath` function and replace its body:

Find:
```typescript
// Resolve the actual executable path based on platform
export function getPackagedBackendPath(): string {
  const path = require('path') as typeof import('path')
  const exeName = process.platform === 'win32'
    ? `${PACKAGED_BACKEND_CONFIG.executableName}.exe`
    : PACKAGED_BACKEND_CONFIG.executableName
  return path.resolve(
    // From desktop/, go up to project root, then into backend/dist/...
    // In packaged Electron app, this resolves via extraResources
    process.env.CS_PACKAGED_BACKEND_PATH ||
      path.resolve(__dirname, '..', '..', '..', PACKAGED_BACKEND_CONFIG.packagedDir, exeName)
  )
}
```

Replace with:
```typescript
// Resolve the actual executable path based on platform
export function getPackagedBackendPath(): string {
  const path = require('path') as typeof import('path')
  const exeName = process.platform === 'win32'
    ? `${PACKAGED_BACKEND_CONFIG.executableName}.exe`
    : PACKAGED_BACKEND_CONFIG.executableName

  // 1. Explicit env override (testing)
  if (process.env.CS_PACKAGED_BACKEND_PATH) {
    return process.env.CS_PACKAGED_BACKEND_PATH
  }

  // 2. Packaged Electron app: extraResources lands in process.resourcesPath
  if (process.resourcesPath) {
    const resourcesCandidate = path.join(
      process.resourcesPath,
      'comicstudio-backend',
      exeName
    )
    // Check existence synchronously (cheap)
    try {
      const fs = require('fs') as typeof import('fs')
      if (fs.existsSync(resourcesCandidate)) {
        return resourcesCandidate
      }
    } catch {
      // ignore
    }
  }

  // 3. Development: resolve from backend/dist/
  return path.resolve(
    __dirname,
    '..',
    '..',
    '..',
    PACKAGED_BACKEND_CONFIG.packagedDir,
    exeName
  )
}
```

- [ ] **Step 5: Add integration test assertions**

Modify `c:\漫剧软件项目\desktop\src\test\integration.test.ts` — find an appropriate place (near other config assertions) and add assertions for the new packaged backend config. Add these inside an existing `describe` block or a new one:

Find a `describe` block (e.g., the one testing constants or main modules). If there's a `describe('Main process modules', ...)` block, add to it. Otherwise, add a new describe block at the end:

```typescript
describe('Phase 5: Packaged backend configuration', () => {
  it('exports PACKAGED_BACKEND_CONFIG', async () => {
    const constants = await import('../main/constants')
    expect(constants.PACKAGED_BACKEND_CONFIG).toBeDefined()
    expect(constants.PACKAGED_BACKEND_CONFIG.executableName).toBe('comicstudio-backend')
    expect(constants.PACKAGED_BACKEND_CONFIG.host).toBe('127.0.0.1')
    expect(constants.PACKAGED_BACKEND_CONFIG.port).toBe(8000)
  })

  it('getPackagedBackendPath returns a string', async () => {
    const constants = await import('../main/constants')
    const p = constants.getPackagedBackendPath()
    expect(typeof p).toBe('string')
    expect(p.length).toBeGreaterThan(0)
  })

  it('getPackagedBackendPath respects env override', async () => {
    const orig = process.env.CS_PACKAGED_BACKEND_PATH
    process.env.CS_PACKAGED_BACKEND_PATH = '/test/path/backend.exe'
    try {
      const constants = await import('../main/constants')
      expect(constants.getPackagedBackendPath()).toBe('/test/path/backend.exe')
    } finally {
      if (orig === undefined) {
        delete process.env.CS_PACKAGED_BACKEND_PATH
      } else {
        process.env.CS_PACKAGED_BACKEND_PATH = orig
      }
    }
  })

  it('backend-process imports getPackagedBackendPath', async () => {
    const source = await import('fs').then(fs =>
      fs.promises.readFile(
        require('path').resolve(__dirname, '../main/backend/backend-process.ts'),
        'utf-8'
      )
    )
    expect(source).toContain('getPackagedBackendPath')
    expect(source).toContain('usePackaged')
  })

  it('electron-builder.yml includes extraResources for backend', async () => {
    const fs = await import('fs')
    const path = await import('path')
    const yamlPath = path.resolve(__dirname, '../../electron-builder.yml')
    const content = await fs.promises.readFile(yamlPath, 'utf-8')
    expect(content).toContain('extraResources')
    expect(content).toContain('comicstudio-backend')
  })
})
```

- [ ] **Step 6: Run typecheck and tests**

Run (cwd `c:\漫剧软件项目\desktop`): `npm run typecheck`
Expected: 0 errors

Run (cwd `c:\漫剧软件项目\desktop`): `npm test`
Expected: 75 passed (70 from Phase 4 + 5 new from Phase 5 Task 6)

- [ ] **Step 7: Commit**

(Skip — Git not installed.)

---

### Task 7: Documentation + Final Regression

**Files:**
- Create: `c:\漫剧软件项目\docs\deployment\desktop-packaging.md`
- Create: `c:\漫剧软件项目\backend\packaging\README.md`

- [ ] **Step 1: Create the desktop packaging documentation**

Create `c:\漫剧软件项目\docs\deployment\desktop-packaging.md`:

```markdown
# 桌面端打包指南（Phase 5）

> 本文档说明如何将 Python 后端打包为独立可执行文件，并集成到 Electron 桌面应用中，实现真正的离线运行。

---

## 一、整体架构

```
┌─────────────────────────────────────────────────────┐
│ Electron App (comicstudio-setup.exe)                │
│                                                      │
│  ┌──────────────────┐  ┌─────────────────────────┐ │
│  │  React Frontend  │  │  Packaged Python Backend │ │
│  │  (renderer)      │  │  (comicstudio-backend)   │ │
│  │                  │←→│                          │ │
│  │  - React Flow    │  │  - FastAPI + uvicorn    │ │
│  │  - Ant Design    │  │  - SQLite (aiosqlite)   │ │
│  │  - Zustand       │  │  - All AI engines        │ │
│  └──────────────────┘  └─────────────────────────┘ │
│                                                      │
│  extraResources: ../backend/dist/comicstudio-backend │
└─────────────────────────────────────────────────────┘
```

**关键组件：**
- **PyInstaller**：将 Python 后端打包为单目录可执行文件
- **SQLite/aiosqlite**：桌面模式下的数据库 fallback（无需 PostgreSQL）
- **BackendProcess**：Electron 主进程管理后端子进程
- **extraResources**：electron-builder 将后端打包到 Electron 应用中

---

## 二、前置要求

### 2.1 开发环境

| 软件 | 版本 | 说明 |
|------|------|------|
| Python | 3.11+ | 后端运行时 |
| Node.js | 18+ | 前端 + Electron 构建 |
| PyInstaller | 6.11+ | Python 打包工具 |
| electron-builder | 24+ | Electron 打包工具 |

### 2.2 已完成阶段

- Phase 1: 全栈基础骨架
- Phase 2: AI 引擎层
- Phase 3: 工作流引擎
- Phase 4: Electron 桌面应用

---

## 三、构建 Python 后端可执行文件

### 3.1 安装打包依赖

```bash
cd backend
python -m pip install pyinstaller==6.11.1 aiosqlite==0.19.0
```

### 3.2 验证 spec 文件完整性

```bash
python packaging/verify_spec.py
```

预期输出：
```
[PASS] Spec file exists
[PASS] Spec parses as Python
[PASS] entry.py referenced
[PASS] All hooks exist
[PASS] App modules listed
[PASS] Excludes are safe
```

### 3.3 执行打包

```bash
# 清理旧产物并重新构建
python packaging/build.py --clean

# 或不清理直接构建
python packaging/build.py
```

构建产物位于 `backend/dist/comicstudio-backend/`：
- Windows: `comicstudio-backend.exe`
- Linux/macOS: `comicstudio-backend`

构建时间：首次约 5-10 分钟（取决于依赖数量）。

### 3.4 验证可执行文件

```bash
# 启动后端
./dist/comicstudio-backend/comicstudio-backend.exe --port 8765

# 另开终端测试
curl http://127.0.0.1:8765/health
# 预期: {"code":0,"message":"success","data":{"status":"ok","version":"0.1.0"}}
```

### 3.5 运行端到端测试

```bash
cd backend
python -m pytest tests/test_e2e_packaged.py -v
```

预期：10 个测试全部通过。

---

## 四、构建 Electron 桌面应用

### 4.1 确保后端已打包

确认 `backend/dist/comicstudio-backend/` 目录存在且包含可执行文件。

### 4.2 构建 Electron 应用

```bash
cd desktop
npm run build       # 构建 main/preload/renderer
npm run package:win # Windows 打包（或 package:mac / package:linux）
```

产物位于 `desktop/release/`：
- Windows: `comicstudio-setup-0.1.0.exe` (NSIS 安装包)

### 4.3 安装并测试

运行安装包，启动应用。应用会：
1. 自动启动内嵌的 Python 后端（packaged exe 模式）
2. 后端创建 SQLite 数据库到 `%APPDATA%/comic-studio-desktop/data/`
3. 前端连接到 `http://127.0.0.1:8000`
4. 用户即可离线使用所有功能

---

## 五、运行时数据目录

桌面模式下，所有用户数据存储在：

| 平台 | 路径 |
|------|------|
| Windows | `%APPDATA%/comic-studio-desktop/` |
| macOS | `~/Library/Application Support/comic-studio-desktop/` |
| Linux | `~/.config/comic-studio-desktop/` |

目录结构：
```
comic-studio-desktop/
├── data/                      # CS_DATA_DIR
│   ├── comicstudio.db         # SQLite 数据库
│   ├── .jwt_secret            # JWT 密钥（自动生成）
│   ├── version.txt            # 版本信息
│   ├── logs/
│   │   └── app.log            # 应用日志
│   └── uploads/
│       ├── images/
│       │   └── 20260719/      # 按日期组织
│       └── audio/
│           └── 20260719/
```

---

## 六、配置覆盖

### 6.1 使用外部 PostgreSQL

默认桌面模式使用 SQLite。如需连接外部 PostgreSQL，设置环境变量：

```bash
# Windows (PowerShell)
$env:DATABASE_URL = "postgresql+asyncpg://user:pass@host:5432/db"
$env:CS_DESKTOP_MODE = "1"
comicstudio-backend.exe

# Linux/macOS
DATABASE_URL="postgresql+asyncpg://user:pass@host:5432/db" CS_DESKTOP_MODE=1 ./comicstudio-backend
```

### 6.2 自定义数据目录

```bash
CS_DATA_DIR=/path/to/data comicstudio-backend.exe
```

### 6.3 端口配置

```bash
comicstudio-backend.exe --port 9000 --host 0.0.0.0
```

---

## 七、调试

### 7.1 查看后端日志

后端日志输出到两个位置：
1. **stderr**（Electron 主进程控制台）
2. **`<data_dir>/logs/app.log`**

### 7.2 常见问题

#### Q1: 后端启动失败

检查 Electron 主进程日志（`console.log`）。常见原因：
- 可执行文件路径错误 → 检查 `getPackagedBackendPath()`
- 端口被占用 → 修改 `LOCAL_BACKEND_CONFIG.port`
- 数据目录权限不足 → 检查 `CS_DATA_DIR`

#### Q2: PyInstaller 打包时缺少模块

错误：`ModuleNotFoundError: No module named 'xxx'`

解决：在 `packaging/comicstudio_backend.spec` 的 `hiddenimports` 列表中添加该模块，然后重新打包。

#### Q3: SQLite 性能问题

SQLite 适用于单用户桌面场景。如性能不足：
1. 连接外部 PostgreSQL（见 6.1）
2. 或在 `app/core/database.py` 调整 SQLite pragma（如 `journal_mode=WAL`）

#### Q4: 打包体积过大

当前打包包含所有 AI 引擎依赖。如需减小体积：
1. 在 spec 的 `excludes` 中排除不用的模块
2. 使用 UPX 压缩（`upx=True`，需安装 UPX）
3. 拆分为多个可选包（高级）

---

## 八、CI/CD 集成（参考）

```yaml
# .github/workflows/build-desktop.yml
name: Build Desktop App
on:
  push:
    tags: ['v*']

jobs:
  build:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - uses: actions/setup-node@v4
        with:
          node-version: '20'

      - name: Install backend deps
        run: |
          cd backend
          pip install -r requirements.txt
          pip install --target .deps -r requirements.txt

      - name: Build backend executable
        run: |
          cd backend
          python packaging/build.py --clean

      - name: Install frontend deps
        run: cd frontend && npm ci

      - name: Build frontend
        run: cd frontend && npm run build

      - name: Install desktop deps
        run: cd desktop && npm ci

      - name: Build desktop installer
        run: cd desktop && npm run package:win
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}

      - uses: actions/upload-artifact@v4
        with:
          name: comicstudio-setup
          path: desktop/release/*.exe
```

---

*本文档最后更新：2026-07-19*
```

- [ ] **Step 2: Create packaging README**

Create `c:\漫剧软件项目\backend\packaging\README.md`:

```markdown
# Backend Packaging

This directory contains scripts and configs for packaging the Python backend
into a standalone executable using PyInstaller.

## Files

- `entry.py` — Entry point script (what PyInstaller bundles)
- `runtime.py` — Runtime path resolution (frozen vs development)
- `build.py` — Build script wrapper
- `verify_spec.py` — Spec file integrity checker
- `comicstudio_backend.spec` — PyInstaller spec file
- `hooks/` — Custom PyInstaller hooks for native modules

## Quick Start

```bash
# From backend/ directory:

# 1. Install PyInstaller
pip install pyinstaller==6.11.1

# 2. Verify spec
python packaging/verify_spec.py

# 3. Build
python packaging/build.py --clean

# 4. Test the executable
./dist/comicstudio-backend/comicstudio-backend.exe --port 8765
```

## Hooks

Each hook in `hooks/` tells PyInstaller how to bundle a specific native module:

| Hook | Purpose |
|------|---------|
| `hook-asyncpg.py` | asyncpg Cython extensions + metadata |
| `hook-bcrypt.py` | bcrypt `_bcrypt.pyd` native extension |
| `hook-loguru.py` | loguru dynamically-loaded sinks |
| `hook-pydantic_core.py` | pydantic-core Rust-compiled extension |
| `hook-alembic.py` | alembic Mako templates |
| `hook-ffmpeg_python.py` | ffmpeg-python `_run.py` template |

## Troubleshooting

If the build fails with "ModuleNotFoundError", add the missing module to
`hiddenimports` in `comicstudio_backend.spec` and rebuild.

If the executable crashes at runtime with import errors, check the
`hooks/` directory — a native module's hook may be missing or incomplete.

See `docs/deployment/desktop-packaging.md` for the full guide.
```

- [ ] **Step 3: Run final regression on backend**

Run (cwd `c:\漫剧软件项目\backend`): `python -m pytest`
Expected: 249 passed (all backend tests)

- [ ] **Step 4: Run final regression on desktop**

Run (cwd `c:\漫剧软件项目\desktop`): `npm test`
Expected: 75 passed (all desktop tests)

- [ ] **Step 5: Run final typecheck on desktop**

Run (cwd `c:\漫剧软件项目\desktop`): `npm run typecheck`
Expected: 0 errors

- [ ] **Step 6: Run final build on desktop**

Run (cwd `c:\漫剧软件项目\desktop`): `npm run build`
Expected: Build succeeds, output in `out/`

- [ ] **Step 7: Verify documentation exists**

Verify both doc files exist:
- `c:\漫剧软件项目\docs\deployment\desktop-packaging.md`
- `c:\漫剧软件项目\backend\packaging\README.md`

- [ ] **Step 8: Commit**

(Skip — Git not installed.)

---

## Self-Review

### Spec coverage

| Phase 5 Goal | Covered by |
|---|---|
| Python backend packaged as standalone executable | Task 3 (spec + hooks), Task 4 (entry + build), Task 5 (actual build) |
| SQLite fallback when PostgreSQL unavailable | Task 1 (desktop_config + database.py modifications) |
| Data directory management for desktop | Task 2 (paths.py + bootstrap.py) |
| Electron spawns packaged exe (no Python install needed) | Task 6 (backend-process.ts modifications) |
| Backend bundled into Electron installer | Task 6 (electron-builder.yml extraResources) |
| First-run bootstrap (create dirs, init DB) | Task 2 (bootstrap.py) |
| JWT secret auto-generation in desktop mode | Task 1 (get_desktop_jwt_secret) |
| End-to-end verification of packaged backend | Task 5 (test_e2e_packaged.py) |
| Documentation for build process | Task 7 (desktop-packaging.md + README.md) |
| No regression in Phase 1-4 functionality | Each task ends with full regression run |

No spec gaps detected.

### Placeholder scan

Searched for forbidden placeholder patterns:
- No `TBD`, `TODO`, `implement later`, `fill in details`
- Every code step contains complete code
- Every test step contains actual test code
- Every "Run" step contains exact commands with expected output
- Task 2 Step 10 (storage.py modification) describes the approach but defers to reading the file first — this is intentional because the exact edits depend on the current storage.py structure which may have changed. The instruction to "use `get_uploads_subdir('images')` etc." is concrete enough.

### Type consistency

- `is_desktop_mode()` defined in both `desktop_config.py` and `paths.py` — both check the same env var with the same logic. This is intentional (each module is self-contained) but could be DRYed in a future refactor.
- `BackendMode` type from Phase 4 unchanged — Task 6 only adds `PACKAGED_BACKEND_CONFIG` and `getPackagedBackendPath()`.
- `getPackagedBackendPath()` returns `string` consistently in constants.ts and is consumed by backend-process.ts.
- `get_desktop_database_url()` returns `str` (Python) — consistent with `Settings.database_url` field type.
- `RuntimeMode = Literal["development", "frozen"]` — consistent with `is_frozen()` returning bool and `get_runtime_mode()` returning the literal.
- `bootstrap_desktop()` returns `bool` (True if ran, False if skipped) — consistent across tests and main.py usage.

### Risk notes

1. **PyInstaller build time**: First build takes 5-10 minutes. Subsequent builds with cache are faster. The build must succeed for Task 5's e2e tests to run.
2. **Native module issues**: asyncpg, bcrypt, pydantic-core all have native extensions. If the hooks don't bundle them correctly, runtime will fail with ImportError. The hooks are written based on best practices but may need adjustment for specific versions.
3. **`packaging` module name conflict**: Python has a stdlib `packaging` module. The local `packaging/` dir should take precedence when running tests from `backend/` root, but if imports fail, rename the local dir or use absolute imports.
4. **Storage.py modification**: Task 2 Step 10 requires reading the current storage.py structure before editing. If storage.py is simple, the edit is straightforward; if complex, multiple edits may be needed.
5. **electron-builder.yml structure**: Task 6 Step 3 inserts `extraResources` into the existing YAML. The exact insertion point depends on the current structure.
6. **Test count growth**: Backend grows from 182 → 249 tests (67 new). Desktop grows from 70 → 75 tests (5 new). Total project: 252 → 324 tests.
7. **Build environment**: PyInstaller must be installed in the same Python env as the backend deps. The `--target .deps` install pattern from earlier phases should work.

---

## Execution Handoff

Plan complete and saved to `c:\漫剧软件项目\docs\superpowers\plans\2026-07-19-phase5-backend-packaging.md`.

Two execution options:

1. **Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration. Best for the 7-task structure here; each task is self-contained with its own tests.

2. **Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
