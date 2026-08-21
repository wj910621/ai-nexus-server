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
