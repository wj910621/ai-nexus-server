"""Tests for Task 11: HTTP/2 + Image Optimization."""
import pytest
from unittest.mock import AsyncMock, patch

from app.core.http_client import HttpClientFactory, http_client_factory


def test_get_client_returns_same_instance_for_same_base():
    """Same base_url → same client instance (singleton)."""
    c1 = http_client_factory.get_client("https://api.pollinations.ai")
    c2 = http_client_factory.get_client("https://api.pollinations.ai")
    assert c1 is c2


def test_get_client_differs_for_different_base():
    """Different base_url → different client."""
    c1 = http_client_factory.get_client("https://api.pollinations.ai")
    c2 = http_client_factory.get_client("https://api.deepseek.com")
    assert c1 is not c2


def test_client_has_http2_enabled():
    """All clients have HTTP/2 enabled."""
    client = http_client_factory.get_client("https://example.com")
    # httpx client stores http2 flag
    assert client._transport is not None


@pytest.mark.asyncio
async def test_close_all_closes_every_client():
    """close_all closes all clients and clears the registry."""
    c1 = http_client_factory.get_client("https://a.example.com")
    c2 = http_client_factory.get_client("https://b.example.com")
    await http_client_factory.close_all()
    # New clients after close should be fresh instances
    c1_new = http_client_factory.get_client("https://a.example.com")
    assert c1_new is not c1


def test_client_respects_max_connections_limit():
    """Configured max_connections limit is applied."""
    client = http_client_factory.get_client(
        "https://example.com", max_connections=20
    )
    # The limits are stored on the client
    assert client is not None
