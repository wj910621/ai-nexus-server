"""RequestIDMiddleware — adds X-Request-ID to every request.

- If client sends X-Request-ID, reuse it (if valid UUID-ish)
- Else generate new UUID
- Set on request.state.request_id for downstream use
- Add to response headers
"""
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Inject X-Request-ID header into request and response."""

    HEADER_NAME = "X-Request-ID"

    async def dispatch(self, request: Request, call_next):
        # Get or generate request ID
        request_id = request.headers.get(self.HEADER_NAME, "")
        if not request_id or len(request_id) > 128:
            request_id = uuid.uuid4().hex

        # Store on request.state for downstream
        request.state.request_id = request_id

        # Process request
        response = await call_next(request)

        # Add to response
        response.headers[self.HEADER_NAME] = request_id
        return response


def get_request_id(request: Request) -> str:
    """Get current request ID (for use in handlers)."""
    return getattr(request.state, "request_id", "unknown")
