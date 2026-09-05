"""
Single-process, in-memory load tracker.

- A semaphore bounds true concurrency at `capacity`.
- An atomic counter reports the current in-flight count so the router can
  read the load *before* deciding which tier to use.
- Everything is asyncio-native; no threads, no locks needed because
  Python's asyncio is single-threaded per event loop and increments here
  happen between awaits.
"""
from __future__ import annotations
import asyncio
from contextlib import asynccontextmanager


class LoadTracker:
    def __init__(self, capacity: int):
        assert capacity > 0
        self.capacity = capacity
        self._sem = asyncio.Semaphore(capacity)
        self._in_flight = 0

    @property
    def in_flight(self) -> int:
        return self._in_flight

    @property
    def load_fraction(self) -> float:
        """Fraction of capacity currently in use, on [0, 1]."""
        return self._in_flight / self.capacity

    @asynccontextmanager
    async def track(self):
        """
        Use as `async with tracker.track(): ...` around request handling.
        Blocks (awaits) if we're already at capacity, which is intentional —
        it's how we simulate a real overloaded system.
        """
        await self._sem.acquire()
        self._in_flight += 1
        try:
            yield
        finally:
            self._in_flight -= 1
            self._sem.release()

