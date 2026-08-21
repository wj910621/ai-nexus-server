"""Tests for Task 10: WebSocket Streaming."""
import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from fastapi import WebSocket, WebSocketDisconnect

from app.core.ws_manager import WebSocketManager, ws_manager


@pytest.mark.asyncio
async def test_subscribe_adds_connection_to_channel():
    """subscribe() adds a connection to the channel's set."""
    mgr = WebSocketManager()
    ws = MagicMock()
    ws.client_state = MagicMock()
    ws.send_json = AsyncMock()
    await mgr.subscribe(ws, "task:123", user_id=1)
    assert "task:123" in mgr._channels
    assert ws in mgr._channels["task:123"]


@pytest.mark.asyncio
async def test_unsubscribe_removes_connection():
    """unsubscribe() removes the connection from all channels."""
    mgr = WebSocketManager()
    ws = MagicMock()
    ws.send_json = AsyncMock()
    await mgr.subscribe(ws, "task:123", user_id=1)
    await mgr.unsubscribe(ws, "task:123")
    assert "task:123" not in mgr._channels or ws not in mgr._channels.get("task:123", set())


@pytest.mark.asyncio
async def test_publish_sends_message_to_all_subscribers():
    """publish() sends the message to every connection on that channel."""
    mgr = WebSocketManager()
    ws1 = MagicMock()
    ws1.send_json = AsyncMock()
    ws2 = MagicMock()
    ws2.send_json = AsyncMock()
    await mgr.subscribe(ws1, "task:1", user_id=1)
    await mgr.subscribe(ws2, "task:1", user_id=2)
    await mgr.publish("task:1", {"type": "progress", "progress": 50})
    ws1.send_json.assert_awaited_once()
    ws2.send_json.assert_awaited_once()
    msg = ws1.send_json.await_args.args[0]
    assert msg["type"] == "progress"
    assert msg["progress"] == 50


@pytest.mark.asyncio
async def test_publish_skips_failed_connections():
    """publish() removes connections that raise on send."""
    mgr = WebSocketManager()
    ws_bad = MagicMock()
    ws_bad.send_json = AsyncMock(side_effect=Exception("disconnected"))
    ws_good = MagicMock()
    ws_good.send_json = AsyncMock()
    await mgr.subscribe(ws_bad, "task:1", user_id=1)
    await mgr.subscribe(ws_good, "task:1", user_id=2)
    await mgr.publish("task:1", {"type": "ping"})
    # Bad conn should be removed
    assert ws_bad not in mgr._channels.get("task:1", set())
    assert ws_good in mgr._channels["task:1"]


@pytest.mark.asyncio
async def test_publish_to_nonexistent_channel_is_noop():
    """Publishing to a channel with no subscribers is a no-op."""
    mgr = WebSocketManager()
    await mgr.publish("nonexistent", {"type": "ping"})  # No exception


@pytest.mark.asyncio
async def test_publish_to_user_only_sends_to_that_user():
    """publish_to_user() only sends to that user's connections."""
    mgr = WebSocketManager()
    ws1 = MagicMock()
    ws1.send_json = AsyncMock()
    ws2 = MagicMock()
    ws2.send_json = AsyncMock()
    await mgr.subscribe(ws1, "user:1", user_id=1)
    await mgr.subscribe(ws2, "user:2", user_id=2)
    await mgr.publish_to_user(1, {"type": "notification"})
    ws1.send_json.assert_awaited_once()
    ws2.send_json.assert_not_awaited()


@pytest.mark.asyncio
async def test_broadcast_sends_to_all_connections():
    """broadcast() sends to every connected client."""
    mgr = WebSocketManager()
    ws1 = MagicMock(); ws1.send_json = AsyncMock()
    ws2 = MagicMock(); ws2.send_json = AsyncMock()
    await mgr.subscribe(ws1, "global", user_id=1)
    await mgr.subscribe(ws2, "global", user_id=2)
    await mgr.broadcast({"type": "system", "message": "restart"})
    assert ws1.send_json.await_count == 1
    assert ws2.send_json.await_count == 1


@pytest.mark.asyncio
async def test_get_channel_subscriber_count():
    """get_subscriber_count returns channel size."""
    mgr = WebSocketManager()
    ws1 = MagicMock(); ws1.send_json = AsyncMock()
    ws2 = MagicMock(); ws2.send_json = AsyncMock()
    await mgr.subscribe(ws1, "task:1", user_id=1)
    await mgr.subscribe(ws2, "task:1", user_id=2)
    assert mgr.get_subscriber_count("task:1") == 2
    assert mgr.get_subscriber_count("task:999") == 0


@pytest.mark.asyncio
async def test_connection_limit_is_enforced_atomically():
    mgr = WebSocketManager()
    ws1 = MagicMock()
    ws2 = MagicMock()

    assert await mgr.subscribe(
        ws1, "user:u1", user_id="u1", max_connections=1
    )
    assert not await mgr.subscribe(
        ws2, "user:u1", user_id="u1", max_connections=1
    )
    assert mgr.get_user_connection_count("u1") == 1


@pytest.mark.asyncio
async def test_subscription_limit_is_enforced_atomically():
    mgr = WebSocketManager()
    ws = MagicMock()

    assert await mgr.subscribe(ws, "user:u1", user_id="u1", max_subscriptions=2)
    assert await mgr.subscribe(ws, "task:1", user_id="u1", max_subscriptions=2)
    assert not await mgr.subscribe(ws, "task:2", user_id="u1", max_subscriptions=2)


@pytest.mark.asyncio
async def test_unsubscribe_unknown_channel_does_not_allocate_channel():
    mgr = WebSocketManager()
    await mgr.unsubscribe(MagicMock(), "attacker-controlled")
    assert "attacker-controlled" not in mgr._channels


@pytest.mark.asyncio
async def test_auth_invalid_token_rejects_connection():
    """Invalid JWT token is rejected with 4001 close."""
    from app.api.websocket import handle_websocket
    ws = AsyncMock(spec=WebSocket)
    ws.query_params = {"token": "invalid.jwt.token"}
    ws.accept = AsyncMock()
    ws.close = AsyncMock()
    await handle_websocket(ws)
    ws.accept.assert_not_awaited()
    ws.close.assert_awaited_once()
    assert ws.close.await_args.kwargs.get("code") == 4001


@pytest.mark.asyncio
async def test_auth_valid_token_accepts_connection(monkeypatch):
    """Valid JWT token is accepted."""
    from app.api.websocket import handle_websocket
    from app.core.security import create_access_token
    # Existing signature: create_access_token(subject: str, expires_delta=None)
    token = create_access_token("1")
    ws = AsyncMock()
    ws.query_params = {"token": token}
    ws.headers = {}  # A6: origin 校验需要 headers.get("origin", "") 返回字符串
    ws.accept = AsyncMock()
    # handle_websocket calls receive_json; raise WebSocketDisconnect to exit loop
    ws.receive_json = AsyncMock(side_effect=WebSocketDisconnect())
    ws.send_json = AsyncMock()
    ws.close = AsyncMock()
    # A1: 撤销表校验需要 AsyncSessionLocal，mock 为返回 None 的空 session
    class _FakeSession:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            return False
        async def execute(self, *args, **kwargs):
            class _FakeResult:
                def scalar_one_or_none(self):
                    return None
            return _FakeResult()
    monkeypatch.setattr("app.core.database.AsyncSessionLocal", lambda: _FakeSession())
    monkeypatch.setattr("app.api.websocket.ws_manager", WebSocketManager())
    await handle_websocket(ws)
    ws.accept.assert_awaited_once()
