"""Tests for Task 12: SSE Streaming."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import ASGITransport, AsyncClient

from app.engines.base import GenerationResult


# === Fixtures ===
@pytest.fixture(autouse=True)
def _mock_cache_and_dedup():
    """Patch result_cache_service + request_deduplicator (same as test_ai_api)."""
    async def _passthrough(func, *args, **kwargs):
        return await func(*args, **kwargs)

    mock_cache = MagicMock()
    mock_cache.get = AsyncMock(return_value=None)
    mock_cache.set = AsyncMock(return_value=None)
    mock_cache.LLM_TTL_SECONDS = 1800

    mock_dedup = MagicMock()
    mock_dedup.deduplicate = _passthrough  # type: ignore[assignment]

    with patch("app.api.ai.result_cache_service", mock_cache), \
         patch("app.api.ai.request_deduplicator", mock_dedup):
        yield


@pytest.fixture
def mock_user():
    """Admin user — bypasses credit deduction so no DB is required."""
    user = MagicMock()
    user.id = "test-user-id"
    user.username = "testuser"
    user.status = "active"
    user.role = "admin"
    user.credits = 0
    return user


@pytest.fixture
def auth_bypass(mock_user):
    """Override get_current_user dep (same pattern as test_ai_api)."""
    from app.main import app
    from app.core.deps import get_current_user

    async def _override():
        return mock_user

    app.dependency_overrides[get_current_user] = _override
    yield
    app.dependency_overrides.pop(get_current_user, None)


# === Tests ===
@pytest.mark.asyncio
async def test_chat_stream_returns_event_stream(auth_bypass):
    """/chat?stream=true returns text/event-stream content-type."""
    from app.main import app

    mock_engine = MagicMock()
    async def _stream(*args, **kwargs):
        yield "Hello"
        yield " world"
    mock_engine.chat_stream = _stream

    mock_mgr = MagicMock()
    mock_mgr.get_llm_engine.return_value = mock_engine
    # 路由组件就绪（_resolve_engine 会走 get_engine_routed 分支）
    mock_mgr._router = MagicMock()
    mock_mgr._quota_guard = MagicMock()
    mock_mgr.get_engine_routed = AsyncMock(return_value=mock_engine)

    with patch("app.api.ai.engine_manager", mock_mgr):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/ai/chat?stream=true",
                json={
                    "messages": [{"role": "user", "content": "hi"}],
                },
            )
    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")
    # Body should contain SSE-formatted events
    body = response.text
    assert "event: token" in body
    assert "data: [DONE]" in body
    assert "Hello" in body
    assert " world" in body


@pytest.mark.asyncio
async def test_chat_non_stream_returns_json(auth_bypass):
    """/chat without stream=true returns JSON (backward compat)."""
    from app.main import app

    mock_engine = AsyncMock()
    mock_engine.chat = AsyncMock(
        return_value=GenerationResult(
            success=True,
            data="你好",
            content_type="text/plain",
            metadata={},
        )
    )
    mock_mgr = MagicMock()
    mock_mgr.get_llm_engine.return_value = mock_engine
    # 路由组件就绪（_resolve_engine 会走 get_engine_routed 分支）
    mock_mgr._router = MagicMock()
    mock_mgr._quota_guard = MagicMock()
    mock_mgr.get_engine_routed = AsyncMock(return_value=mock_engine)

    with patch("app.api.ai.engine_manager", mock_mgr):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/ai/chat",
                json={
                    "messages": [{"role": "user", "content": "hi"}],
                },
            )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert data["data"]["success"] is True
    assert data["data"]["data"] == "你好"


@pytest.mark.asyncio
async def test_sse_format_yields_data_lines():
    """sse_format() yields 'event: ...\\ndata: ...\\n\\n' formatted strings."""
    from app.api.sse import sse_format
    result = sse_format({"text": "Hello"}, event="token")
    assert result.startswith("event: token\n")
    assert "data:" in result
    assert result.endswith("\n\n")
    assert "Hello" in result


@pytest.mark.asyncio
async def test_sse_done_event_sent_at_end():
    """sse_done() returns the [DONE] sentinel."""
    from app.api.sse import sse_done
    result = sse_done()
    assert "[DONE]" in result
    assert result.endswith("\n\n")


@pytest.mark.asyncio
async def test_calculate_refund_returns_unused_proportion():
    """calculate_refund() refunds the unused-token proportion of the cost."""
    from app.api.sse import calculate_refund
    # User paid for 1000 tokens but only used 200 → refund 80% → 8 credits
    refund = calculate_refund(used_tokens=200, total_tokens=1000, cost=10)
    assert refund == 8  # int(10 * 0.8)
    # Edge case: zero total → no refund
    assert calculate_refund(used_tokens=100, total_tokens=0, cost=10) == 0
    # Edge case: used >= total → no refund
    assert calculate_refund(used_tokens=1000, total_tokens=1000, cost=10) == 0
