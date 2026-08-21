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
from typing import Literal

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
