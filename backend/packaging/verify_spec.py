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
