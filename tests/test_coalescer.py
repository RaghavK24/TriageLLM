import pytest
import asyncio
from app.coalescer import RequestCoalescer, generate_coalesce_key

def test_generate_coalesce_key():
    key1 = generate_coalesce_key("Hello\nworld ", "strong")
    key2 = generate_coalesce_key("Hello\nworld", "strong")
    assert key1 == key2

    key3 = generate_coalesce_key("Hello world", "weak")
    assert key1 != key3

@pytest.mark.asyncio
async def test_coalescer_deduplication():
    coalescer = RequestCoalescer(timeout=1.0)
    calls = 0

    async def fetch_coro():
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.1)
        return "result"

    # Fire 10 concurrent requests for the same key
    tasks = [
        coalescer.get_or_fetch("key1", fetch_coro)
        for _ in range(10)
    ]
    results = await asyncio.gather(*tasks)

    # All should return the exact same result
    assert all(r == "result" for r in results)
    
    # The underlying function should only be called once
    assert calls == 1
    assert coalescer.total_requests == 10
    assert coalescer.coalesced_requests == 9
    assert "key1" not in coalescer._in_flight  # Cleanup worked

@pytest.mark.asyncio
async def test_coalescer_exception_propagation():
    coalescer = RequestCoalescer(timeout=1.0)

    async def fetch_coro():
        await asyncio.sleep(0.01)
        raise ValueError("fetch failed")

    tasks = [
        coalescer.get_or_fetch("key2", fetch_coro)
        for _ in range(3)
    ]
    
    # All tasks should raise the same exception
    results = await asyncio.gather(*tasks, return_exceptions=True)
    assert all(isinstance(r, ValueError) for r in results)
    assert "key2" not in coalescer._in_flight  # Cleanup worked on exception

