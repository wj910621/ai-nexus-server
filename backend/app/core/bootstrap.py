"""First-run bootstrap for desktop mode.

Creates required directories, initializes the SQLite database, and writes
a version.txt for diagnostics. Safe to call multiple times (idempotent).
"""
import os

from loguru import logger

from app import __version__


async def bootstrap_desktop() -> bool:
    """Run first-run setup for desktop mode.

    Returns:
        True if bootstrap ran (desktop mode), False if skipped (not desktop mode).
    """
    if os.environ.get("CS_DESKTOP_MODE", "").lower() not in ("1", "true", "yes"):
        logger.debug("Bootstrap skipped: not in desktop mode")
        return False

    logger.info("Running desktop bootstrap...")

    # 1. Create data directories
    from app.core.desktop_config import (
        get_desktop_data_dir,
        get_desktop_uploads_dir,
    )
    data_dir = get_desktop_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    get_desktop_uploads_dir().mkdir(parents=True, exist_ok=True)
    (data_dir / "logs").mkdir(parents=True, exist_ok=True)

    # Pre-create upload subdirs
    for subdir in ("images", "audio", "datasets", "lora_adapters"):
        (get_desktop_uploads_dir() / subdir).mkdir(parents=True, exist_ok=True)

    # 2. Initialize JWT secret (auto-generates if missing)
    from app.core.desktop_config import get_desktop_jwt_secret
    get_desktop_jwt_secret()

    # 3. Initialize database (create_all is idempotent)
    # Force reimport to pick up desktop mode env vars
    import importlib

    import app.core.config
    importlib.reload(app.core.config)
    import app.core.database
    importlib.reload(app.core.database)
    # Import all models so they register with Base.metadata
    # NOTE: app.models.Base is the DeclarativeBase that models actually register
    # with (distinct from app.core.database.Base, whose metadata is empty).
    import app.models  # noqa: F401
    from app.core.database import close_db, engine
    from app.models import Base as ModelsBase
    try:
        async with engine.begin() as conn:
            await conn.run_sync(ModelsBase.metadata.create_all)
        logger.info("Database initialized (create_all)")
    except Exception as e:
        logger.error(f"Database init failed: {e}")
        raise
    finally:
        await close_db()

    # 4. Write version.txt for diagnostics
    version_file = data_dir / "version.txt"
    version_file.write_text(
        f"Y·NEX Story Studio Backend\nVersion: {__version__}\nMode: desktop\n",
        encoding="utf-8",
    )

    logger.info(f"Desktop bootstrap complete. Data dir: {data_dir}")
    return True
