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
