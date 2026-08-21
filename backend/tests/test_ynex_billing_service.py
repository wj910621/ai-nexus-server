from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from httpx import Headers, Response

from app.services.ynex_billing_service import YnexBillingService


class FakeClient:
    def __init__(self, response: Response, **_kwargs):
        self.response = response
        self.post = AsyncMock(return_value=response)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None


@pytest.mark.asyncio
async def test_charge_returns_verified_receipt(monkeypatch):
    monkeypatch.setattr("app.services.ynex_billing_service.settings.ynex_billing_base_url", "https://ynexai.cn")
    monkeypatch.setattr("app.services.ynex_billing_service.settings.ynex_billing_service_token", "s" * 32)
    response = Response(
        201,
        headers=Headers({"content-type": "application/json"}),
        json={"ok": True, "event": {"id": 42}},
    )
    fake = FakeClient(response)
    with patch("app.services.ynex_billing_service.httpx.AsyncClient", return_value=fake):
        receipt = await YnexBillingService().charge("ynex-user", "text2img")
    assert receipt.event_id == 42
    payload = fake.post.await_args.kwargs["json"]
    assert payload["username"] == "ynex-user"
    assert payload["operation"] == "text2img"
    assert payload["idempotencyKey"].startswith("story_")


@pytest.mark.asyncio
async def test_charge_maps_insufficient_balance_to_402(monkeypatch):
    monkeypatch.setattr("app.services.ynex_billing_service.settings.ynex_billing_base_url", "https://ynexai.cn")
    monkeypatch.setattr("app.services.ynex_billing_service.settings.ynex_billing_service_token", "s" * 32)
    response = Response(
        402,
        headers=Headers({"content-type": "application/json"}),
        json={"ok": False, "error": "insufficient_credits"},
    )
    with patch(
        "app.services.ynex_billing_service.httpx.AsyncClient",
        return_value=FakeClient(response),
    ):
        with pytest.raises(HTTPException) as exc:
            await YnexBillingService().charge("ynex-user", "tts")
    assert exc.value.status_code == 402


@pytest.mark.asyncio
async def test_charge_fails_closed_on_invalid_receipt(monkeypatch):
    monkeypatch.setattr("app.services.ynex_billing_service.settings.ynex_billing_base_url", "https://ynexai.cn")
    monkeypatch.setattr("app.services.ynex_billing_service.settings.ynex_billing_service_token", "s" * 32)
    response = Response(
        201,
        headers=Headers({"content-type": "application/json"}),
        json={"ok": True, "event": {}},
    )
    with patch(
        "app.services.ynex_billing_service.httpx.AsyncClient",
        return_value=FakeClient(response),
    ):
        with pytest.raises(HTTPException) as exc:
            await YnexBillingService().charge("ynex-user", "video_compose")
    assert exc.value.status_code == 503
