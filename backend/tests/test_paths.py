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
    assert result.parent == tmp_path / "uploads" / "images"


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
