"""GzipMiddleware — compress responses, skip text/event-stream (SSE)."""
from starlette.datastructures import Headers
from starlette.middleware.gzip import GZipMiddleware, GZipResponder


class SmartGZipResponder(GZipResponder):
    """自定义 GZipResponder，跳过 SSE 响应。

    在 ``http.response.start`` 阶段检查 content-type，
    若为 ``text/event-stream`` 则标记为已编码，使后续 body 直接透传不压缩。
    """

    async def send_with_gzip(self, message):
        await super().send_with_gzip(message)
        # super() 在 http.response.start 时会重置 content_encoding_set，
        # 因此必须在 super() 之后覆盖，确保 SSE 后续 body 走直接透传路径
        if message["type"] == "http.response.start":
            headers = Headers(raw=message["headers"])
            content_type = headers.get("content-type", "")
            if "text/event-stream" in content_type:
                self.content_encoding_set = True


class SmartGzipMiddleware(GZipMiddleware):
    """GZip middleware that skips SSE responses.

    SSE responses must not be buffered (chunks must be sent immediately).
    Standard GZipMiddleware would buffer them, breaking streaming.

    注意：starlette 0.27.0 的 GZipMiddleware 使用纯 ASGI 的 ``__call__`` + GZipResponder，
    不调用 ``dispatch`` 方法。因此必须覆盖 ``__call__`` 并使用自定义 Responder。
    """

    def __init__(self, app, minimum_size=500, compresslevel=9):
        super().__init__(app, minimum_size=minimum_size, compresslevel=compresslevel)

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            headers = Headers(scope=scope)
            if "gzip" in headers.get("Accept-Encoding", ""):
                responder = SmartGZipResponder(
                    self.app, self.minimum_size, compresslevel=self.compresslevel
                )
                await responder(scope, receive, send)
                return
        await self.app(scope, receive, send)
