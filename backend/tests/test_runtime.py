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
