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
    env = {**os.environ, "PYTHONPATH": "c:\\漫剧软件项目\\backend\\.deps;c:\\漫剧软件项目\\backend"}
    result = subprocess.run(
        [sys.executable, str(PACKAGING_DIR / "verify_spec.py")],
        capture_output=True,
        text=True,
        cwd=str(PACKAGING_DIR.parent),
        env=env,
    )
    assert result.returncode == 0, f"verify_spec failed:\n{result.stdout}\n{result.stderr}"


def test_spec_includes_app_modules():
    spec = (PACKAGING_DIR / "comicstudio_backend.spec").read_text(encoding="utf-8")
    assert "app.main" in spec
    assert "app.core.config" in spec
    assert "app.core.database" in spec
    assert "app.core.bootstrap" in spec
