import asyncio
import hashlib
import json
import logging
from typing import Any, Callable
from app.metrics import COALESCED_REQUESTS

logger = logging.getLogger(__name__)

def generate_coalesce_key(prompt: str, tier: str) -> str:
    """
    Generate a deterministic hash key for request coalescing.
    
    Includes: prompt (normalized) and tier.
    Does NOT include: RAG context (two requests with the same prompt will
    deterministically pull the same RAG context, so the raw prompt is safe to hash).
    """
    normalized_prompt = "\n".join(
        line.rstrip() for line in prompt.strip().splitlines()
    )
    
    payload = json.dumps({
        "p": normalized_prompt,
        "t": tier,
    }, sort_keys=True).encode("utf-8")
    
    return hashlib.sha256(payload).hexdigest()

class RequestCoalescer:
    """
    Golang singleflight equivalent for asyncio.
    
    Uses asyncio.Task (not Future) so the fetch is decoupled from any 
    individual caller's lifecycle. If the first caller disconnects, 
    the fetch continues for the remaining waiters.
    """
    def __init__(self, timeout: float = 60.0):
        self._in_flight: dict[str, asyncio.Task] = {}
        self._timeout = timeout
        # Metrics
        self.total_requests = 0
        self.coalesced_requests = 0

    async def get_or_fetch(self, key: str, fetch_coro_fn: Callable, *args: Any, **kwargs: Any) -> tuple[Any, bool]:
        self.total_requests += 1
        
        was_coalesced = False
        if key in self._in_flight:
            self.coalesced_requests += 1
            COALESCED_REQUESTS.inc()
            logger.debug(f"Coalescing request for key: {key[:16]}...")
            was_coalesced = True
            task = self._in_flight[key]
        else:
            logger.debug(f"First request for key: {key[:16]}..., launching task")
            task = asyncio.create_task(
                self._do_fetch(key, fetch_coro_fn, *args, **kwargs)
            )
            self._in_flight[key] = task

        try:
            # asyncio.shield prevents the underlying task from being cancelled
            # if THIS specific caller times out or disconnects.
            result = await asyncio.shield(task)
            return result, was_coalesced
        except asyncio.CancelledError:
            logger.warning(f"Caller cancelled waiting for key {key[:16]}")
            raise

    async def _do_fetch(self, key: str, fetch_coro_fn: Callable, *args: Any, **kwargs: Any) -> Any:
        try:
            result = await asyncio.wait_for(
                fetch_coro_fn(*args, **kwargs), 
                timeout=self._timeout
            )
            return result
        except asyncio.TimeoutError:
            logger.error(f"Fetch timed out for coalesced key {key[:16]}")
            raise
        except Exception as e:
            logger.error(f"Fetch failed for coalesced key {key[:16]}: {e}")
            raise
        finally:
            # CRITICAL: Memory leak prevention
            self._in_flight.pop(key, None)

    @property
    def hit_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.coalesced_requests / self.total_requests

