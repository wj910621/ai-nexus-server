"""数据库连接管理 - SQLAlchemy 2.0 异步引擎

Supports two drivers:
- PostgreSQL via asyncpg (production / cloud)
- SQLite via aiosqlite (desktop mode fallback when PostgreSQL unavailable)
"""
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    """ORM 基类"""
    pass


def create_engine_for_url(
    url: str,
    *,
    echo: bool = False,
    skip_create: bool = False,
) -> AsyncEngine:
    """Create an async engine for the given URL.

    Picks appropriate pool settings based on dialect:
    - PostgreSQL (asyncpg): pool_size=20, max_overflow=10, pool_pre_ping=True
    - SQLite (aiosqlite): no pool_size (uses StaticPool implicitly)

    Args:
        url: SQLAlchemy async URL (e.g. 'postgresql+asyncpg://...' or 'sqlite+aiosqlite:///...')
        echo: Whether to log SQL statements
        skip_create: If True, don't actually connect (for dialect detection tests)
    """
    if url.startswith("sqlite"):
        # SQLite: no pool_size/max_overflow (not supported)
        # Use NullPool to avoid threading issues with SQLite
        from sqlalchemy.pool import NullPool
        return create_async_engine(
            url,
            echo=echo,
            poolclass=NullPool,
            connect_args={"check_same_thread": False},
        )
    # PostgreSQL
    return create_async_engine(
        url,
        echo=echo,
        pool_size=20,
        max_overflow=10,
        pool_pre_ping=True,
    )


# 异步引擎
engine = create_engine_for_url(
    settings.database_url,
    echo=settings.is_development,
)

# 异步会话工厂
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话依赖"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """初始化数据库 (创建所有表 - 仅用于开发/desktop 首次启动)"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """关闭数据库连接"""
    await engine.dispose()


async def run_migrations_on_startup() -> None:
    """Run Alembic migrations on startup (dev/desktop mode only).

    Production should use CLI: `alembic upgrade head`.
    """
    import os

    from alembic.config import Config
    from loguru import logger

    from alembic import command

    alembic_ini_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "alembic.ini"
    )
    if not os.path.exists(alembic_ini_path):
        logger.warning(f"alembic.ini not found at {alembic_ini_path}; skipping migrations")
        return

    try:
        alembic_cfg = Config(alembic_ini_path)
        # Override URL with current settings (handles desktop SQLite fallback)
        alembic_cfg.set_main_option("sqlalchemy.url", settings.database_url)
        command.upgrade(alembic_cfg, "head")
        logger.info("Alembic migrations applied successfully")
    except Exception as e:
        logger.error(f"Alembic migration failed: {e}", exc_info=True)
        # Fallback to create_all for desktop mode
        logger.warning("Falling back to Base.metadata.create_all()")
        await init_db()
