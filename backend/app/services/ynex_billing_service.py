"""Fail-closed client for the Y·NEX shared credit ledger."""
import uuid
from dataclasses import dataclass

import httpx
from fastapi import HTTPException

from app.core.config import settings


@dataclass(frozen=True)
class YnexCharge:
    event_id: int
    operation: str


class YnexBillingService:
    """Charge and refund only through the main site's reviewed price manifest."""

    def _headers(self) -> dict[str, str]:
        return {
            "X-Story-Service-Token": settings.ynex_billing_service_token,
            "Content-Type": "application/json",
            "User-Agent": "YNEX-Story-Studio/1.0",
        }

    async def charge(self, subject: str, operation: str) -> YnexCharge:
        if (
            not settings.ynex_billing_base_url
            or len(settings.ynex_billing_service_token) < 32
        ):
            raise HTTPException(503, "Y·NEX shared billing is not configured")

        payload = {
            "username": subject,
            "operation": operation,
            "idempotencyKey": f"story_{uuid.uuid4().hex}",
        }
        response = None
        last_error: httpx.HTTPError | None = None
        # A lost response may occur after the main ledger committed. Retry once
        # with the exact same idempotency key so it cannot charge twice.
        for _attempt in range(2):
            try:
                async with httpx.AsyncClient(
                    base_url=settings.ynex_billing_base_url.rstrip("/"),
                    timeout=httpx.Timeout(15.0, connect=5.0),
                    follow_redirects=False,
                ) as client:
                    response = await client.post(
                        "/api/internal/story/credits/charge",
                        headers=self._headers(),
                        json=payload,
                    )
                break
            except httpx.HTTPError as exc:
                last_error = exc
        if response is None:
            raise HTTPException(503, "Y·NEX shared billing is unavailable") from last_error

        try:
            body = (
                response.json()
                if response.headers.get("content-type", "").startswith("application/json")
                else {}
            )
        except ValueError as exc:
            raise HTTPException(503, "Y·NEX billing returned an invalid response") from exc
        if response.status_code == 402:
            raise HTTPException(402, "积分不足")
        if response.status_code < 200 or response.status_code >= 300:
            raise HTTPException(503, f"Y·NEX billing rejected operation: {body.get('error', 'unknown')}")

        event_id = body.get("event", {}).get("id")
        if not isinstance(event_id, int) or event_id <= 0:
            raise HTTPException(503, "Y·NEX billing returned an invalid receipt")
        return YnexCharge(event_id=event_id, operation=operation)

    async def refund(self, charge: YnexCharge, reason: str) -> None:
        safe_reason = reason[:120]
        try:
            async with httpx.AsyncClient(
                base_url=settings.ynex_billing_base_url.rstrip("/"),
                timeout=httpx.Timeout(15.0, connect=5.0),
                follow_redirects=False,
            ) as client:
                response = await client.post(
                    "/api/internal/story/credits/refund",
                    headers=self._headers(),
                    json={"eventId": charge.event_id, "reason": safe_reason},
                )
        except httpx.HTTPError as exc:
            raise HTTPException(503, "Y·NEX refund is temporarily unavailable") from exc
        if response.status_code < 200 or response.status_code >= 300:
            raise HTTPException(503, "Y·NEX refund failed; manual reconciliation required")


ynex_billing_service = YnexBillingService()
