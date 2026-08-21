"""Tests for ProviderFailover circuit breaker."""
import pytest
import asyncio
from unittest.mock import AsyncMock

from app.engines.provider_failover import ProviderFailover, CircuitState


@pytest.mark.asyncio
async def test_circuit_starts_closed():
    """Circuit breaker starts in CLOSED state (requests pass through)."""
    fb = ProviderFailover(threshold=5, reset_seconds=60)
    assert fb.state == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_circuit_opens_after_threshold_failures():
    """After threshold consecutive failures, circuit opens."""
    fb = ProviderFailover(threshold=3, reset_seconds=60)
    await fb.record_failure()
    await fb.record_failure()
    assert fb.state == CircuitState.CLOSED
    await fb.record_failure()
    assert fb.state == CircuitState.OPEN


@pytest.mark.asyncio
async def test_circuit_closes_after_success():
    """A success resets the failure count and closes the circuit."""
    fb = ProviderFailover(threshold=3, reset_seconds=60)
    await fb.record_failure()
    await fb.record_failure()
    await fb.record_success()
    assert fb.state == CircuitState.CLOSED
    assert fb.failure_count == 0


@pytest.mark.asyncio
async def test_open_circuit_rejects_calls():
    """When OPEN, can_call() returns False (reject)."""
    fb = ProviderFailover(threshold=1, reset_seconds=60)
    await fb.record_failure()
    assert fb.state == CircuitState.OPEN
    assert fb.can_call() is False


@pytest.mark.asyncio
async def test_circuit_transitions_to_half_open_after_timeout():
    """After reset_seconds, OPEN transitions to HALF_OPEN on next can_call()."""
    fb = ProviderFailover(threshold=1, reset_seconds=0)  # 0s for test
    await fb.record_failure()
    assert fb.state == CircuitState.OPEN
    import time
    time.sleep(0.05)
    # Next can_call should transition to HALF_OPEN and allow the call
    assert fb.can_call() is True
    assert fb.state == CircuitState.HALF_OPEN


@pytest.mark.asyncio
async def test_half_open_success_closes_circuit():
    """In HALF_OPEN, a success closes the circuit."""
    fb = ProviderFailover(threshold=1, reset_seconds=0)
    await fb.record_failure()
    import time
    time.sleep(0.05)
    fb.can_call()  # Transitions to HALF_OPEN
    await fb.record_success()
    assert fb.state == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_half_open_failure_reopens_circuit():
    """In HALF_OPEN, a failure re-opens the circuit."""
    fb = ProviderFailover(threshold=1, reset_seconds=0)
    await fb.record_failure()
    import time
    time.sleep(0.05)
    fb.can_call()
    await fb.record_failure()
    assert fb.state == CircuitState.OPEN


@pytest.mark.asyncio
async def test_call_with_failover_uses_secondary_on_open():
    """call_with_failover falls back to secondary when primary circuit is open."""
    primary = AsyncMock(side_effect=Exception("primary down"))
    secondary = AsyncMock(return_value="from-secondary")

    fb = ProviderFailover(threshold=1, reset_seconds=60)
    await fb.record_failure()  # Open the circuit

    result = await fb.call_with_failover(primary, secondary, arg1=1)
    assert result == "from-secondary"
    secondary.assert_awaited_once()


@pytest.mark.asyncio
async def test_call_with_failover_raises_when_both_fail():
    """Both primary and secondary fail → raise last exception."""
    primary = AsyncMock(side_effect=ValueError("primary"))
    secondary = AsyncMock(side_effect=KeyError("secondary"))

    fb = ProviderFailover(threshold=1, reset_seconds=60)
    await fb.record_failure()

    with pytest.raises(KeyError):
        await fb.call_with_failover(primary, secondary)
