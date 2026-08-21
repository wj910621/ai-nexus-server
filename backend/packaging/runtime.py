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
