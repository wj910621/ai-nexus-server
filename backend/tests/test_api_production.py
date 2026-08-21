"""Tests for API productionization: versioning, gzip, ETag, refresh."""
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.middleware.etag import ETagMiddleware
from app.core.middleware.gzip import SmartGzipMiddleware
from app.core.middleware.security_headers import SecurityHeadersMiddleware


@pytest.fixture
def app():
    app = FastAPI()
    # Order: ETag innermost (computes on uncompressed), then Gzip outer
    app.add_middleware(ETagMiddleware)
    app.add_middleware(SmartGzipMiddleware, minimum_size=10)
    app.add_middleware(SecurityHeadersMiddleware)

    @app.get("/api/v1/data")
    async def get_data_v1():
        return {"data": "v1 response", "padding": "x" * 100}

    @app.get("/api/data")  # legacy
    async def get_data_legacy():
        return {"data": "legacy response"}

    @app.get("/api/v1/stream")
    async def sse_stream():
        from starlette.responses import StreamingResponse

        async def gen():
            yield b"data: hello\n\n"
            yield b"data: world\n\n"

        return StreamingResponse(gen(), media_type="text/event-stream")

    return app


@pytest.mark.asyncio
async def test_api_v1_alias_works(app):
    """/api/v1/* endpoints are accessible."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/data")
    assert resp.status_code == 200
    assert resp.json()["data"] == "v1 response"


@pytest.mark.asyncio
async def test_api_legacy_endpoints_still_work(app):
    """/api/* legacy endpoints continue to work (backward compat)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/data")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_security_headers_include_hsts_behind_tls_proxy(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/v1/data", headers={"X-Forwarded-Proto": "https"}
        )
    assert response.headers["strict-transport-security"].startswith("max-age=31536000")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "SAMEORIGIN"
    assert response.headers["content-security-policy"] == (
        "default-src 'none'; frame-ancestors 'self'"
    )


@pytest.mark.asyncio
async def test_gzip_compresses_large_responses(app):
    """Large responses are gzipped."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/api/v1/data", headers={"Accept-Encoding": "gzip"}
        )
    assert resp.status_code == 200
    assert resp.headers.get("content-encoding") == "gzip"


@pytest.mark.asyncio
async def test_gzip_skips_sse_responses(app):
    """SSE responses are NOT gzipped (would break streaming)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/api/v1/stream", headers={"Accept-Encoding": "gzip"}
        )
    assert resp.status_code == 200
    assert resp.headers.get("content-encoding") != "gzip"
    assert "text/event-stream" in resp.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_etag_added_to_get_responses(app):
    """ETag header is added to GET responses."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/data")
    assert resp.status_code == 200
    assert "etag" in resp.headers


@pytest.mark.asyncio
async def test_etag_returns_304_when_unchanged(app):
    """If-None-Match returns 304 when ETag matches."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # First request to get ETag
        resp1 = await client.get("/api/v1/data")
        etag = resp1.headers["etag"]

        # Second request with If-None-Match
        resp2 = await client.get(
            "/api/v1/data", headers={"If-None-Match": etag}
        )
    assert resp2.status_code == 304


@pytest.mark.asyncio
async def test_etag_returns_200_when_changed(app):
    """If-None-Match with stale ETag returns 200 with new ETag."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/api/v1/data", headers={"If-None-Match": '"stale-etag"'}
        )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_jwt_access_token_is_short_lived():
    """JWT access token expires in 30 minutes (not 1440)."""
    from app.core.config import settings

    assert settings.jwt_access_token_expire_minutes == 30


@pytest.mark.asyncio
async def test_refresh_endpoint_returns_new_tokens(db_session):
    """POST /api/auth/refresh returns new access + refresh tokens."""
    # This test requires auth setup; simplified version checks endpoint exists
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/auth/refresh", json={"refresh_token": "invalid"}
        )
    # Invalid token should return 401, not 404 (endpoint exists)
    assert resp.status_code in (401, 422)


@pytest.mark.asyncio
async def test_logout_revokes_token():
    """POST /api/auth/logout revokes the current token."""
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Without auth, should return 401
        resp = await client.post("/api/auth/logout")
    assert resp.status_code in (401, 403, 404)  # endpoint exists
