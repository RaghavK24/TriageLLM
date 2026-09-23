"""
Circuit breaker for LLM API providers.

Improvements over the original:
  1. **Windowed failure rate** instead of a simple counter. 3 failures out
     of 3000 requests (0.1%) shouldn't trip the breaker.
  2. **Higher default threshold** (5 instead of 3) — LLM APIs are bursty.
  3. **Jittered recovery** — when multiple breakers are OPEN, they don't all
     try to recover at the exact same moment (which would re-create the
     thundering herd on the half-open probe).
"""
import asyncio
import random
import time
from typing import Literal

State = Literal["CLOSED", "OPEN", "HALF_OPEN"]


class CircuitOpenError(Exception):
    """Raised when trying to call an API while its circuit is OPEN."""
    pass


class CircuitBreaker:
    """
    State machine for tracking API availability.
    CLOSED: Normal operation, requests flow through.
    OPEN: API is failing, requests are blocked instantly.
    HALF_OPEN: Testing if API has recovered.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        window_seconds: float = 15.0,
    ):
        self.state: State = "CLOSED"
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.window_seconds = window_seconds

        # Limit the number of test requests that can pass through when HALF_OPEN.
        self.half_open_max_calls = 1
        self._half_open_calls = 0

        # Windowed failure tracking — list of monotonic timestamps.
        self._failure_times: list[float] = []
        self.last_failure_time: float = 0.0
        self._lock = asyncio.Lock()

    def _prune_old(self) -> None:
        """Remove failure records outside the observation window."""
        cutoff = time.monotonic() - self.window_seconds
        self._failure_times = [t for t in self._failure_times if t > cutoff]

    @property
    def failures_in_window(self) -> int:
        self._prune_old()
        return len(self._failure_times)

    async def check(self) -> None:
        """
        Check if a request is allowed to proceed.
        Raises CircuitOpenError if the circuit is OPEN and recovery timeout
        (with jitter) hasn't elapsed, or if it is HALF_OPEN and the probe limit
        has already been reached.
        """
        async with self._lock:
            if self.state == "HALF_OPEN":
                if self._half_open_calls >= self.half_open_max_calls:
                    raise CircuitOpenError()
                self._half_open_calls += 1
            elif self.state == "OPEN":
                now = time.monotonic()
                # Jitter: ±20% of recovery_timeout so breakers don't all
                # probe at the same instant.
                jittered = self.recovery_timeout * random.uniform(0.8, 1.2)
                if now - self.last_failure_time >= jittered:
                    self.state = "HALF_OPEN"
                    self._half_open_calls = 1
                else:
                    raise CircuitOpenError()

    async def on_success(self) -> None:
        """Record a successful request to reset the breaker."""
        async with self._lock:
            if self.state != "CLOSED":
                self.state = "CLOSED"
            self._failure_times.clear()

    async def on_failure(self) -> None:
        """Record a failure (e.g., rate limit) to potentially open the breaker."""
        async with self._lock:
            now = time.monotonic()
            self.last_failure_time = now
            self._failure_times.append(now)

            if self.state == "HALF_OPEN":
                # A failure during the probe — go straight back to OPEN.
                self.state = "OPEN"
                return

            # Check windowed failure count.
            self._prune_old()
            if len(self._failure_times) >= self.failure_threshold:
                self.state = "OPEN"
