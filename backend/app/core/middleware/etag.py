"""ETagMiddleware — conditional GET requests via ETag/If-None-Match."""
import hashlib

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class ETagMiddleware(BaseHTTPMiddleware):
    """Add ETag to GET responses; return 304 if unchanged.

    Only applies to GET requests with 200 status and a body.
    ETag computed as SHA256 of response body (truncated to 16 hex chars).
    """

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Only apply to GET, 200 responses
        if request.method != "GET" or response.status_code != 200:
            return response

        # Skip streaming (SSE) responses — they have content-type text/event-stream
        content_type = response.headers.get("content-type", "")
        if "text/event-stream" in content_type:
            return response

        # Buffer the body (BaseHTTPMiddleware wraps response as _StreamingResponse
        # without a `.body` attribute; consume the stream to materialize it).
        body_chunks = []
        async for chunk in response.body_iterator:
            if isinstance(chunk, (bytes, bytearray, memoryview)):
                body_chunks.append(bytes(chunk))
            elif isinstance(chunk, str):
                body_chunks.append(chunk.encode("utf-8"))
        body = b"".join(body_chunks)

        if not body:
            return response

        # Compute ETag
        etag = '"' + hashlib.sha256(body).hexdigest()[:16] + '"'

        # Check If-None-Match
        if_none_match = request.headers.get("if-none-match")
        if if_none_match and if_none_match == etag:
            # Return 304 Not Modified
            return Response(
                status_code=304,
                headers={
                    "ETag": etag,
                    "Content-Type": content_type,
                },
            )

        # Rebuild response with ETag header
        new_headers = dict(response.headers)
        new_headers["ETag"] = etag
        return Response(
            content=body,
            status_code=response.status_code,
            headers=new_headers,
            media_type=response.media_type,
        )
