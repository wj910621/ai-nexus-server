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
    """Run PyInstaller with the spec file.

    The subprocess runs from a neutral cwd (the parent of PROJECT_ROOT)
    with PYTHONPATH restricted to .deps. This avoids a name collision
    between the project's ``packaging/`` folder (containing this build
    script) and the PyPA ``packaging`` library that PyInstaller's hooks
    import (``import packaging.requirements``). If cwd were PROJECT_ROOT,
    Python's ``-m`` flag would put PROJECT_ROOT on sys.path[0] and
    ``backend/packaging/`` would shadow ``.deps/packaging/``.
    """
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

    # Build a clean env for the subprocess: PYTHONPATH only points at .deps
    # so PyInstaller's own imports (and hooks) resolve the PyPA packaging
    # library instead of the project's packaging/ folder. The spec's
    # ``pathex=[PROJECT_ROOT]`` still lets analysis find the app.* modules.
    env = os.environ.copy()
    deps_dir = str(PROJECT_ROOT / ".deps")
    env["PYTHONPATH"] = deps_dir

    # Neutral cwd: the parent of PROJECT_ROOT has no packaging/ subfolder,
    # so it cannot shadow .deps/packaging/.
    neutral_cwd = str(PROJECT_ROOT.parent)
    print(f"Subprocess cwd: {neutral_cwd}")
    print(f"Subprocess PYTHONPATH: {deps_dir}")
    return subprocess.call(cmd, cwd=neutral_cwd, env=env)


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
