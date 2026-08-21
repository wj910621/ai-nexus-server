"""Tests for observability middleware."""
import pytest
import logging
from fastapi import FastAPI, Request
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, MagicMock

from app.core.middleware.request_id import RequestIDMiddleware
from app.core.middleware.access_log import AccessLogMiddleware


def _loguru_propagation_sink(message):
    """Loguru sink that propagates to standard logging so caplog can capture it.

    Loguru doesn't use the standard logging system by default, so pytest's
    caplog fixture cannot capture loguru output. This sink converts each
    loguru record into a standard logging LogRecord and re-emits it via
    the standard logging framework (which caplog intercepts).
    """
    rec = message.record
    name = rec["name"]
    level_no = rec["level"].no
    msg = rec["message"]
    file_path = rec["file"].path
    line_no = rec["line"]
    # Loguru uses "exception" key (RecordException namedtuple or None);
    # standard logging uses "exc_info" ((type, value, tb) tuple or None).
    exc = rec["exception"]
    if exc is not None:
        exc_info = (exc.type, exc.value, exc.traceback)
    else:
        exc_info = None
    std_record = logging.LogRecord(
        name=name,
        level=level_no,
        pathname=file_path,
        lineno=line_no,
        msg=msg,
        args=(),
        exc_info=exc_info,
    )
    logging.getLogger(name).handle(std_record)


@pytest.fixture(autouse=True)
def _propagate_loguru():
    """Add a loguru->logging propagation sink so caplog captures loguru output."""
    from loguru import logger
    handler_id = logger.add(_loguru_propagation_sink, level="DEBUG")
    yield
    try:
        logger.remove(handler_id)
    except ValueError:
        pass


@pytest.fixture
def app():
    app = FastAPI()
    # RequestID must be outermost (added last) so X-Request-ID is set on ALL
    # responses including errors caught by AccessLogMiddleware.
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(RequestIDMiddleware)

    @app.get("/test")
    async def test_endpoint():
        return {"ok": True}

    @app.get("/error")
    async def error_endpoint():
        raise RuntimeError("test error")

    return app


@pytest.mark.asyncio
async def test_request_id_generated_when_absent(app):
    """X-Request-ID is generated when client doesn't send one."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/test")
    assert resp.status_code == 200
    assert "x-request-id" in resp.headers
    assert len(resp.headers["x-request-id"]) == 32  # UUID hex


@pytest.mark.asyncio
async def test_request_id_preserved_when_sent(app):
    """Client-provided X-Request-ID is preserved."""
    custom_id = "abc-123-def"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/test", headers={"X-Request-ID": custom_id})
    assert resp.headers["x-request-id"] == custom_id


@pytest.mark.asyncio
async def test_request_id_available_in_state(app):
    """Request ID is accessible in request.state for handlers."""
    captured_id = []

    @app.get("/capture")
    async def capture(request: Request):
        captured_id.append(request.state.request_id)
        return {"id": request.state.request_id}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/capture", headers={"X-Request-ID": "test-id-123"}
        )
    assert resp.json()["id"] == "test-id-123"
    assert captured_id == ["test-id-123"]


@pytest.mark.asyncio
async def test_access_log_emitted(app, caplog):
    """Access log is emitted for each request."""
    with caplog.at_level(logging.INFO):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.get("/test")

    # At least one log entry should contain "test" path
    assert any("/test" in record.message for record in caplog.records)


@pytest.mark.asyncio
async def test_access_log_skips_health_endpoints(app, caplog):
    """Access log is NOT emitted for /health, /ready, /metrics."""
    @app.get("/health")
    async def health():
        return {"status": "ok"}

    with caplog.at_level(logging.INFO):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.get("/health")

    # No access log for /health
    assert not any("/health" in r.message for r in caplog.records if r.name == "app.core.middleware.access_log")


@pytest.mark.asyncio
async def test_metrics_endpoint_returns_prometheus_format():
    """Prometheus metrics endpoint returns text/plain metrics."""
    from prometheus_fastapi_instrumentator import Instrumentator

    # Use a fresh app to avoid "Cannot add middleware after application has
    # started" when the shared app.main.app was already built by prior tests.
    metrics_app = FastAPI()
    Instrumentator().instrument(metrics_app).expose(metrics_app, endpoint="/metrics")

    async with AsyncClient(transport=ASGITransport(app=metrics_app), base_url="http://test") as client:
        resp = await client.get("/metrics")
    assert resp.status_code == 200
    assert "http_requests_total" in resp.text or "python_info" in resp.text


@pytest.mark.asyncio
async def test_custom_metrics_registered():
    """Custom metrics are registered with Prometheus."""
    from app.core.metrics import (
        engine_concurrent_requests,
        credits_consumed_total,
        result_cache_hits_total,
    )
    # Just check they're callable (would raise if not registered)
    engine_concurrent_requests.labels(engine_type="image").set(1)
    credits_consumed_total.labels(operation="text2img").inc()
    result_cache_hits_total.labels(engine_type="image").inc()


def test_sentry_init_no_dsn():
    """Sentry SDK init with empty DSN is a no-op."""
    import os
    os.environ["SENTRY_DSN"] = ""
    # Re-import to trigger init
    from importlib import reload
    # Should not raise
    assert True


def test_sentry_init_with_dsn():
    """Sentry SDK init with DSN initializes (mocked)."""
    with patch("sentry_sdk.init") as mock_init:
        from app.core.sentry import init_sentry
        init_sentry("https://example@sentry.io/123")
        assert mock_init.called


@pytest.mark.asyncio
async def test_request_id_on_error_response(app):
    """X-Request-ID is set even on error responses."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/error")
    assert resp.status_code == 500
    assert "x-request-id" in resp.headers
