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
    env = {**os.environ, "PYTHONPATH": "c:\\漫剧软件项目\\backend\\.deps;c:\\漫剧软件项目\\backend"}
    result = subprocess.run(
        [sys.executable, str(BUILD_SCRIPT), "--help"],
        capture_output=True,
        text=True,
        cwd=str(PACKAGING_DIR.parent),
        env=env,
        timeout=30,
    )
    assert result.returncode == 0
    assert "usage" in result.stdout.lower() or "usage" in result.stderr.lower()
