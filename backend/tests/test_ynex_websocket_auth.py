from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_ynex_websocket_maps_external_subject_to_local_user(monkeypatch):
    from app.api.websocket import _authenticate_with_db

    monkeypatch.setattr("app.api.websocket.settings.billing_mode", "jarvis")
    user = SimpleNamespace(id="local-user-uuid", status="active")
    scalar_result = SimpleNamespace(scalar_one_or_none=lambda: user)
    db = SimpleNamespace(execute=AsyncMock(return_value=scalar_result))

    with patch(
        "app.api.websocket.decode_ynex_story_token",
        return_value={"sub": "main-site-user", "aud": "story-studio"},
    ):
        payload = await _authenticate_with_db("story-token", db)

    assert payload is not None
    assert payload["sub"] == "local-user-uuid"
    assert payload["ynex_sub"] == "main-site-user"


@pytest.mark.asyncio
async def test_ynex_websocket_rejects_unknown_subject(monkeypatch):
    from app.api.websocket import _authenticate_with_db

    monkeypatch.setattr("app.api.websocket.settings.billing_mode", "jarvis")
    scalar_result = SimpleNamespace(scalar_one_or_none=lambda: None)
    db = SimpleNamespace(execute=AsyncMock(return_value=scalar_result))

    with patch(
        "app.api.websocket.decode_ynex_story_token",
        return_value={"sub": "missing-user", "aud": "story-studio"},
    ):
        payload = await _authenticate_with_db("story-token", db)

    assert payload is None
