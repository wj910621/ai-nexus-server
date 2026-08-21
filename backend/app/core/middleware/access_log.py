"""AccessLogMiddleware — structured JSON access logs.

Logs each request with: timestamp, request_id, method, path, status,
duration_ms, user_id (if authed), client_ip, user_agent.
"""
import json
import time
from datetime import datetime, timezone

from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class AccessLogMiddleware(BaseHTTPMiddleware):
    """Log every request with structured fields."""

    async def dispatch(self, request: Request, call_next):
        start_time = time.perf_counter()
        request_id = getattr(request.state, "request_id", "unknown")

        # Skip health checks (too noisy)
        path = request.url.path
        if path in ("/health", "/ready", "/metrics"):
            return await call_next(request)

        # Process request
        try:
            response = await call_next(request)
            status_code = response.status_code
            error = None
        except Exception as e:
            status_code = 500
            error = str(e)
            response = None

        duration_ms = (time.perf_counter() - start_time) * 1000

        # Extract user_id if available (set by auth dependency)
        user_id = getattr(request.state, "user_id", None)
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("User-Agent", "")

        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "request_id": request_id,
            "method": request.method,
            "path": path,
            "status": status_code,
            "duration_ms": round(duration_ms, 2),
            "user_id": user_id,
            "client_ip": client_ip,
            "user_agent": user_agent,
        }
        if error:
            log_entry["error"] = error

        if status_code >= 500:
            logger.error(json.dumps(log_entry))
        elif status_code >= 400:
            logger.warning(json.dumps(log_entry))
        else:
            logger.info(json.dumps(log_entry))

        if response is None:
            from starlette.responses import JSONResponse
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal Server Error"},
            )
        return response
