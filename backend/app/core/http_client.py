"""HTTP 客户端工厂 - 共享 httpx.AsyncClient (HTTP/2 + keep-alive)"""
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class HttpClientFactory:
    """HTTP 客户端工厂

    为每个 base_url 维护一个共享的 httpx.AsyncClient 实例：
    - HTTP/2 多路复用（一个 TCP 连接并发多个请求）
    - Keep-alive 避免重复握手
    - 连接池限制防止 fd 泄漏

    对 Pollinations/DeepSeek 等高频 API 可显著降低 p99 延迟。
    """

    def __init__(self) -> None:
        self._clients: dict[str, httpx.AsyncClient] = {}

    def get_client(
        self,
        base_url: str,
        *,
        max_connections: int = 100,
        max_keepalive_connections: int = 20,
        timeout: float = 30.0,
        headers: Optional[dict] = None,
    ) -> httpx.AsyncClient:
        """获取或创建共享 client"""
        if base_url in self._clients:
            return self._clients[base_url]

        client = httpx.AsyncClient(
            base_url=base_url,
            http2=True,
            timeout=httpx.Timeout(timeout, connect=10.0),
            limits=httpx.Limits(
                max_connections=max_connections,
                max_keepalive_connections=max_keepalive_connections,
                keepalive_expiry=30.0,
            ),
            headers=headers or {"User-Agent": "ComicStudio-AI/1.0"},
        )
        self._clients[base_url] = client
        logger.debug(f"Created HTTP/2 client for {base_url}")
        return client

    async def close_all(self) -> None:
        """关闭所有 client (用于应用关闭)"""
        for url, client in self._clients.items():
            try:
                await client.aclose()
            except Exception as exc:
                logger.warning(f"Error closing client {url}: {exc}")
        self._clients.clear()


http_client_factory = HttpClientFactory()
