"""Y·NEX Story Studio - FastAPI 应用入口"""
import asyncio
import signal
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from app.api.router import api_router, v1_router
from app.core.config import settings
from app.core.database import close_db, init_db
from app.core.middleware.access_log import AccessLogMiddleware
from app.core.middleware.etag import ETagMiddleware
from app.core.middleware.gzip import SmartGzipMiddleware
from app.core.middleware.request_id import RequestIDMiddleware
from app.core.middleware.security_headers import SecurityHeadersMiddleware
from app.core.response import ApiResponse
from app.core.sentry import init_sentry

# Configure loguru (Task 4)
logger.remove()
if settings.log_format == "json" and settings.is_production:
    logger.add(
        sys.stdout,
        serialize=True,  # JSON format
        level=settings.log_level,
        backtrace=False,
        diagnose=False,
    )
else:
    logger.add(
        sys.stdout,
        level=settings.log_level,
        backtrace=settings.is_development,
        diagnose=settings.is_development,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # Graceful shutdown signal handling (Task 5)
    # The yield's cleanup block performs the actual shutdown (close_db,
    # close_cache_service). This handler only flags intent so long-running
    # background work can poll and exit early.
    shutdown_event = asyncio.Event()
    storage_cleanup_task = None

    def _signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, initiating graceful shutdown")
        shutdown_event.set()

    # Register signal handlers (Linux/Windows both support SIGINT)
    original_sigint = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, _signal_handler)
    original_sigterm = None
    if hasattr(signal, "SIGTERM"):
        original_sigterm = signal.getsignal(signal.SIGTERM)
        signal.signal(signal.SIGTERM, _signal_handler)

    logger.info(f"启动 {settings.app_name} ({settings.app_env})")

    # 生产环境配置启动校验 (Phase 8 P7 A7)
    try:
        from app.core.config_validator import validate_production_settings
        validate_production_settings(settings)
    except RuntimeError as e:
        logger.error(f"配置校验失败，拒绝启动: {e}")
        raise

    # Initialize Sentry (Task 4)
    try:
        init_sentry()
    except Exception as e:
        logger.warning(f"Sentry初始化失败: {e}")

    # Initialize Prometheus metrics (Task 4)
    if settings.metrics_enabled:
        try:
            from prometheus_fastapi_instrumentator import Instrumentator
            Instrumentator().instrument(app).expose(
                app, endpoint=settings.metrics_path, include_in_schema=False
            )
            logger.info(f"Prometheus metrics exposed at {settings.metrics_path}")
        except Exception as e:
            logger.warning(f"Prometheus初始化失败: {e}")

    # 桌面模式: 运行首次启动引导
    import os
    if os.environ.get("CS_DESKTOP_MODE", "").lower() in ("1", "true", "yes"):
        try:
            from app.core.bootstrap import bootstrap_desktop
            await bootstrap_desktop()
            logger.info("桌面模式引导完成")
        except Exception as e:
            logger.error(f"桌面模式引导失败: {e}")
    elif settings.is_development:
        # 开发环境: 运行数据库迁移 (Task 6)
        try:
            if settings.run_migrations_on_startup:
                from app.core.database import run_migrations_on_startup
                await run_migrations_on_startup()
                logger.info("数据库迁移已应用")
            else:
                await init_db()
                logger.info("数据库表已就绪 (create_all)")
        except Exception as e:
            logger.warning(f"数据库初始化失败 (请确保 PostgreSQL 已启动): {e}")

    # Initialize rate limiter (no-op in desktop mode or when Redis unavailable)
    try:
        from app.core.rate_limit import init_limiter
        await init_limiter(app)
    except Exception as e:
        if settings.is_production:
            logger.error(f"Production rate limiter initialization failed: {e}")
            raise
        logger.warning(f"限流器初始化失败（不影响应用启动）: {e}")

    # Initialize cache service (in-memory in desktop mode, Redis in cloud)
    try:
        from app.core.cache import get_cache_service
        cache = await get_cache_service()
        logger.info(f"缓存服务已就绪 (backend={cache.backend})")
    except Exception as e:
        if settings.is_production:
            logger.error(f"Production cache initialization failed: {e}")
            raise
        logger.warning(f"缓存服务初始化失败（不影响应用启动）: {e}")

    # Recover interrupted tasks (mark pending/running as failed on boot)
    try:
        from app.core.database import AsyncSessionLocal
        from app.services.task_service import task_service
        async with AsyncSessionLocal() as db:
            recovered = await task_service.recover_interrupted(db)
            if recovered > 0:
                logger.info(f"恢复 {recovered} 个中断的任务")
    except Exception as e:
        logger.warning(f"任务恢复失败（不影响应用启动）: {e}")

    # Recover durable workflow state and retry transactional file deletions.
    try:
        from app.core.database import AsyncSessionLocal
        from app.services.storage_cleanup_service import retry_pending_storage_deletions
        from app.services.workflow_service import WorkflowExecutionService
        async with AsyncSessionLocal() as db:
            interrupted = await WorkflowExecutionService(db).recover_interrupted()
            deleted, failed = await retry_pending_storage_deletions(db)
            if interrupted or deleted or failed:
                logger.info(
                    "启动恢复完成: workflow_interrupted={}, files_deleted={}, files_failed={}",
                    interrupted,
                    deleted,
                    failed,
                )
        from app.services.storage_cleanup_service import storage_cleanup_loop
        storage_cleanup_task = asyncio.create_task(
            storage_cleanup_loop(settings.storage_cleanup_interval_seconds),
            name="storage-cleanup-loop",
        )
    except Exception as e:
        logger.warning(f"持久化恢复失败（不影响应用启动）: {e}")

    yield
    if storage_cleanup_task is not None:
        storage_cleanup_task.cancel()
        try:
            await storage_cleanup_task
        except asyncio.CancelledError:
            pass
    logger.info("关闭缓存服务")
    try:
        from app.core.cache import close_cache_service
        await close_cache_service()
    except Exception as e:
        logger.warning(f"缓存服务关闭失败: {e}")
    logger.info("关闭 HTTP 客户端工厂 (Task 11)")
    try:
        from app.core.http_client import http_client_factory
        await http_client_factory.close_all()
    except Exception as e:
        logger.warning(f"HTTP 客户端工厂关闭失败: {e}")
    logger.info("关闭数据库连接")
    await close_db()

    # Restore original signal handlers
    signal.signal(signal.SIGINT, original_sigint)
    if original_sigterm is not None:
        signal.signal(signal.SIGTERM, original_sigterm)


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="商业化漫剧生成软件 - 后端 API",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS 中间件 (Phase 8 P7 A2: 收敛 allow_methods/allow_headers/expose_headers)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-Subscription-JWT"],
    expose_headers=["X-Request-ID", "X-Subscription-JWT"],
)

# Observability middleware (Task 4)
# In Fast/Starlette, add_middleware prepends — last added = outermost.
# We want: RequestID (outermost) → AccessLog → CORS → app
# So AccessLog is added first (inner), RequestID second (outer).
if settings.access_log_enabled:
    app.add_middleware(AccessLogMiddleware)
app.add_middleware(RequestIDMiddleware)

# Production middleware (Task 7)
# Order (innermost → outermost): ETag → Gzip
# ETag computed on uncompressed body (innermost); Gzip compresses after (outer)
app.add_middleware(ETagMiddleware)
app.add_middleware(SmartGzipMiddleware, minimum_size=500)
app.add_middleware(SecurityHeadersMiddleware)


# 全局异常处理
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"未处理异常: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content=ApiResponse.error(message="服务器内部错误", code=-1).model_dump(),
    )


# 健康检查 (liveness probe — always 200 if process is alive)
@app.get("/health", tags=["系统"])
@app.get("/api/health", include_in_schema=False)
async def health_check():
    """Liveness probe — always returns 200 if process is alive."""
    return ApiResponse.success(data={"status": "ok", "version": "0.1.0"})


@app.get("/ready", tags=["系统"])
@app.get("/api/ready", include_in_schema=False)
async def readiness_check():
    """Readiness probe — returns 200 if all dependencies healthy, 503 otherwise."""
    from app.core.health import health_registry
    checks = await health_registry.run_all()
    all_healthy = all(
        c["status"] in ("healthy", "skipped") for c in checks.values()
    )
    status = "ready" if all_healthy else "not_ready"
    return JSONResponse(
        status_code=200 if all_healthy else 503,
        content=ApiResponse(
            code=0 if all_healthy else -1,
            message="success" if all_healthy else "not ready",
            data={"status": status, "checks": checks},
        ).model_dump(),
    )


@app.get("/", tags=["系统"])
async def root():
    """根路径"""
    return ApiResponse.success(
        data={"name": settings.app_name, "docs": "/docs"},
        message=f"欢迎使用 {settings.app_name}",
    )


# 注册路由
# /api/* legacy (backward compat) + /api/v1/* versioned alias (Task 7)
app.include_router(api_router)
app.include_router(v1_router)

# WebSocket 路由 (Task 10) — 挂载在根路径 /ws，不走 /api 前缀（与 nginx 配置一致）
from app.api.websocket import router as ws_router  # noqa: E402

app.include_router(ws_router)
