import pytest
import time
from unittest.mock import patch
from app.circuit_breaker import CircuitOpenError

@pytest.mark.asyncio
async def test_starts_closed(circuit_breaker):
    assert circuit_breaker.state == "CLOSED"
    await circuit_breaker.check()  # Should not raise

@pytest.mark.asyncio
async def test_failures_trip_to_open(circuit_breaker):
    for _ in range(3):
        await circuit_breaker.on_failure()
    assert circuit_breaker.state == "OPEN"

@pytest.mark.asyncio
async def test_open_blocks_requests(circuit_breaker):
    for _ in range(3):
        await circuit_breaker.on_failure()
    with pytest.raises(CircuitOpenError):
        await circuit_breaker.check()

@pytest.mark.asyncio
async def test_half_open_after_timeout(circuit_breaker):
    for _ in range(3):
        await circuit_breaker.on_failure()
    
    # We monkey-patch the time to simulate timeout
    # A bit of a hack without freezegun, but it works and is deterministic.
    circuit_breaker.last_failure_time = time.monotonic() - 5.0 
    
    await circuit_breaker.check()  # Should not raise
    assert circuit_breaker.state == "HALF_OPEN"
    assert circuit_breaker._half_open_calls == 1

@pytest.mark.asyncio
async def test_half_open_success_closes(circuit_breaker):
    circuit_breaker.state = "HALF_OPEN"
    await circuit_breaker.on_success()
    assert circuit_breaker.state == "CLOSED"

@pytest.mark.asyncio
async def test_half_open_failure_reopens(circuit_breaker):
    circuit_breaker.state = "HALF_OPEN"
    await circuit_breaker.on_failure()
    assert circuit_breaker.state == "OPEN"

@pytest.mark.asyncio
async def test_half_open_probe_limit(circuit_breaker):
    circuit_breaker.state = "HALF_OPEN"
    circuit_breaker._half_open_calls = 1  # max is 1
    with pytest.raises(CircuitOpenError):
        await circuit_breaker.check()

