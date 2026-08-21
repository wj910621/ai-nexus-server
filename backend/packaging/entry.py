"""Entry point for the packaged ComicStudio AI Backend.

This script is what PyInstaller bundles. It:
1. Sets up the desktop environment (CS_DESKTOP_MODE, CS_DATA_DIR)
2. Ensures project root is on sys.path (for dev mode)
3. Launches uvicorn with the FastAPI app

Usage (development):
    python -m packaging.entry

Usage (frozen):
    comicstudio-backend.exe

NOTE: Runtime helpers are inlined here (instead of imported from
``packaging.runtime``) to avoid a name collision with the PyPA
``packaging`` library at frozen runtime. The ``packaging.runtime``
module remains available for development/tests.
"""
import os
import sys
from pathlib import Path


def _is_frozen() -> bool:
    """Check if running as a PyInstaller frozen bundle."""
    return getattr(sys, "frozen", False)


def _get_bundle_dir() -> Path:
    """Get the bundle directory (where PyInstaller extracted resources)."""
    if _is_frozen():
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def _get_data_dir() -> Path:
    """Get the data directory (CS_DATA_DIR env or ~/comicstudio-data)."""
    env_data_dir = os.environ.get("CS_DATA_DIR")
    if env_data_dir:
        return Path(env_data_dir).resolve()
    return Path(os.path.expanduser("~")) / "comicstudio-data"


def _setup_desktop_env() -> None:
    """Set up environment variables for desktop mode."""
    os.environ.setdefault("CS_DESKTOP_MODE", "1")
    if "CS_DATA_DIR" not in os.environ:
        data_dir = _get_data_dir()
        data_dir.mkdir(parents=True, exist_ok=True)
        os.environ["CS_DATA_DIR"] = str(data_dir)


def _ensure_path(project_root: Path) -> None:
    """Ensure the project root is on sys.path (for development mode)."""
    project_root_str = str(project_root)
    if project_root_str not in sys.path:
        sys.path.insert(0, project_root_str)


def main() -> None:
    """Launch the backend."""
    # 1. Setup desktop env
    _setup_desktop_env()

    # 2. In development, ensure project root is on sys.path
    if not _is_frozen():
        project_root = Path(__file__).resolve().parent.parent
        _ensure_path(project_root)

    # 3. Parse CLI args (override defaults)
    host = os.environ.get("APP_HOST", "127.0.0.1")
    port = int(os.environ.get("APP_PORT", "8000"))

    # Allow command-line overrides
    if "--host" in sys.argv:
        idx = sys.argv.index("--host")
        host = sys.argv[idx + 1]
    if "--port" in sys.argv:
        idx = sys.argv.index("--port")
        port = int(sys.argv[idx + 1])

    # 4. Configure logging
    from loguru import logger
    import logging

    logger.remove()
    logger.add(sys.stderr, level="INFO")

    # 5. Import and run uvicorn
    logger.info(f"Starting ComicStudio AI Backend on {host}:{port}")
    logger.info(f"Frozen: {_is_frozen()}, Bundle: {_get_bundle_dir()}")
    logger.info(f"Data dir: {os.environ.get('CS_DATA_DIR')}")

    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        log_level="info",
        access_log=True,
        workers=1,  # Single worker for desktop
        ws_max_size=int(os.environ.get("WS_MAX_MESSAGE_BYTES", "1048576")),
    )


if __name__ == "__main__":
    main()
