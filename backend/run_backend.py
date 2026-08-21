"""PyInstaller entry point for the ComicStudio AI backend.

This module is the script referenced by `pyinstaller/desktop_gpu.spec` and
`pyinstaller/desktop_cpu.spec` (Analysis `script` argument). It boots a
uvicorn server hosting the FastAPI app `app.main:app`.

Design goals:
- Single-file entry so PyInstaller's dependency analysis is deterministic.
- Honors env vars for host/port so Electron's BackendProcess can control it.
- Desktop-mode defaults: SQLite fallback, local inference enabled, no Redis.
"""
import os
import sys


def _apply_desktop_env_defaults() -> None:
    """Apply desktop-friendly env defaults if not already set."""
    # Desktop mode: SQLite fallback when PostgreSQL unavailable
    os.environ.setdefault("CS_DESKTOP_MODE", "1")
    # Local inference enabled so EngineManager picks local providers
    os.environ.setdefault("LOCAL_INFERENCE_ENABLED", "true")
    # Cache: memory backend (no Redis on desktop)
    os.environ.setdefault("CACHE_REDIS_URL", "memory")
    # Disable cloud-only services by default
    os.environ.setdefault("CDN_PROVIDER", "none")
    os.environ.setdefault("BACKUP_ENABLED", "false")
    # Disable migrations on startup by default — desktop first-launch wizard
    # triggers them explicitly via /api/v1/admin/ops or by setting
    # RUN_MIGRATIONS_ON_STARTUP=true. This avoids double-init races when the
    # Electron process spawns the backend before the data dir is ready.
    os.environ.setdefault("RUN_MIGRATIONS_ON_STARTUP", "true")


def main() -> None:
    _apply_desktop_env_defaults()

    host = os.environ.get("CS_BACKEND_HOST", "127.0.0.1")
    port_str = os.environ.get("CS_BACKEND_PORT", "8000")
    try:
        port = int(port_str)
    except ValueError:
        print(f"[run_backend] invalid CS_BACKEND_PORT={port_str!r}, defaulting to 8000", file=sys.stderr)
        port = 8000

    workers_str = os.environ.get("CS_BACKEND_WORKERS", "1")
    try:
        workers = int(workers_str)
    except ValueError:
        workers = 1

    print(f"[run_backend] starting uvicorn on {host}:{port} (workers={workers})", file=sys.stderr)

    # Import here so env vars take effect before app load.
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        workers=workers,
        log_level=os.environ.get("CS_BACKEND_LOG_LEVEL", "info"),
        access_log=os.environ.get("CS_BACKEND_ACCESS_LOG", "false").lower() == "true",
        ws_max_size=int(os.environ.get("WS_MAX_MESSAGE_BYTES", "1048576")),
    )


if __name__ == "__main__":
    main()
