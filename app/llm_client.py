"""
Thin wrapper over LiteLLM with load-balanced model pools.

Strong-tier routing  (Strict Primary Fallback)
──────────────────────────────────────────────
Azure GPT-4 is *always* tried first for strong queries.  Groq 120B is used
ONLY if Azure returns an error or its circuit breaker is OPEN.  This keeps
Groq's shared 30 RPM org budget entirely reserved for the weak-tier pool.

Weak-tier routing  (Org-Aware Weighted Pool)
─────────────────────────────────────────────
All weak-tier models compete in a weighted shuffle that uses the effective
remaining capacity — the MINIMUM of the per-model budget and the provider's
org-level group budget.  Previously the shuffle saw 4 Groq models × 28 RPM
= 112 phantom RPM; now it correctly sees the ~30 RPM Groq org ceiling and
spills overflow to non-Groq providers (Gemini, Mistral, etc.).

The pool still acts as a *fallback* when a model fails mid-request — the
request retries on another model from the shuffled order — but the critical
difference is that the *initial* distribution is balanced, not funneled.
"""
from __future__ import annotations
import asyncio
import logging
import random
import time
from dataclasses import dataclass
from typing import Optional

import litellm
from litellm import acompletion, completion_cost

from app.circuit_breaker import CircuitBreaker, CircuitOpenError
from app.rate_limiter import (
    get_budget,
    record_model_request,
    get_effective_remaining_frac,
)
from app.metrics import CIRCUIT_BREAKER_STATE
from app.prompts import get_system_prompt
from config import settings

# Silence LiteLLM's verbose logging in the demo.
litellm.suppress_debug_info = True

logger = logging.getLogger(__name__)

# Use a cryptographically secure RNG for the load balancer shuffle
# so it isn't deterministic based on the OS import-time clock.
_sys_rng = random.SystemRandom()

@dataclass
class LLMResult:
    text: str
    model: str
    cost_usd: float
    prompt_tokens: Optional[int]
    completion_tokens: Optional[int]


class AllProvidersExhausted(Exception):
    """Raised when all models in a fallback chain are unavailable."""
    pass


def _extract_cost(response) -> float:
    """
    Try the fast path (hidden param), fall back to computing it explicitly.
    Never raises — returns 0.0 if we truly can't figure it out.
    """
    try:
        hp = getattr(response, "_hidden_params", None) or {}
        c = hp.get("response_cost")
        if c is not None:
            return float(c)
    except Exception:
        pass
    try:
        return float(completion_cost(completion_response=response))
    except Exception:
        return 0.0


# ── Circuit breakers (one per model) ─────────────────────────────────────

_circuit_breakers: dict[str, CircuitBreaker] = {}


def get_breaker(model: str) -> CircuitBreaker:
    if model not in _circuit_breakers:
        _circuit_breakers[model] = CircuitBreaker(
            failure_threshold=settings.cb_failure_threshold,
            recovery_timeout=settings.cb_recovery_timeout,
        )
    return _circuit_breakers[model]


def get_breaker_states() -> dict[str, str]:
    """Return the current state of all active circuit breakers."""
    return {model: cb.state for model, cb in _circuit_breakers.items()}


def _update_cb_metric(model: str) -> None:
    breaker = get_breaker(model)
    if breaker.state == "CLOSED":
        val = 1.0
    elif breaker.state == "HALF_OPEN":
        val = 0.5
    else:
        val = 0.0
    CIRCUIT_BREAKER_STATE.labels(model=model).set(val)


# ── Org-Aware Weighted-shuffle model selection (weak tier) ────────────────

def _weighted_shuffle(models: list[str]) -> list[str]:
    """
    Return *models* in a weighted-random order for the weak-tier pool.

    Weight for each model = effective remaining capacity × breaker multiplier.
      - effective remaining capacity = min(per-model budget, org-group budget)
        so the shared Groq 30 RPM ceiling is respected across all Groq models.
      - CLOSED breaker  → full weight
      - HALF_OPEN       → 20% weight (graduated re-entry)
      - OPEN            → excluded entirely

    This means models with more *real* remaining budget are tried first, and
    traffic naturally spreads across providers instead of funneling through
    whichever Groq model happens to be listed first.
    """
    candidates: list[tuple[str, float]] = []

    for model in models:
        breaker = get_breaker(model)

        if breaker.state == "OPEN":
            continue

        # Base weight: effective remaining capacity as a fraction (0–1),
        # floored at 0.05 so even a nearly-full provider gets some chance.
        # get_effective_remaining_frac already applies min(model, group) and floor.
        weight = get_effective_remaining_frac(model)

        # Breaker multiplier
        if breaker.state == "HALF_OPEN":
            weight *= 0.2  # graduated re-entry

        candidates.append((model, weight))

    if not candidates:
        return []

    # Weighted shuffle: repeatedly pick from the remaining candidates
    # with probability proportional to weight.
    shuffled: list[str] = []
    remaining = list(candidates)
    while remaining:
        total = sum(w for _, w in remaining)
        if total <= 0:
            shuffled.extend(m for m, _ in remaining)
            break
        r = _sys_rng.random() * total
        cumulative = 0.0
        for i, (model, w) in enumerate(remaining):
            cumulative += w
            if r <= cumulative:
                shuffled.append(model)
                remaining.pop(i)
                break
    return shuffled


# ── Internal helpers ──────────────────────────────────────────────────────

async def _try_model(model: str, messages: list[dict], max_tokens: int) -> LLMResult:
    """
    Attempt one completion against *model*.

    Raises:
        CircuitOpenError  — breaker is OPEN, skip this model.
        Exception         — any API error; caller decides whether to retry.
    """
    breaker = get_breaker(model)

    # May raise CircuitOpenError.
    await breaker.check()
    _update_cb_metric(model)

    # Record the request *before* sending so the budget tracker
    # is up-to-date for concurrent requests.
    record_model_request(model)

    response = await acompletion(
        model=model,
        messages=messages,
        temperature=settings.temperature,
    )

    # Success — reset breaker.
    await breaker.on_success()
    _update_cb_metric(model)

    text = response.choices[0].message.content or ""
    usage = getattr(response, "usage", None)
    prompt_tokens = getattr(usage, "prompt_tokens", None) if usage else None
    completion_tokens = getattr(usage, "completion_tokens", None) if usage else None

    return LLMResult(
        text=text,
        model=model,
        cost_usd=_extract_cost(response),
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )


async def _execute_with_retries(model: str, messages: list[dict], max_tokens: int) -> LLMResult:
    """
    Execute model with Full Jitter exponential backoff for transient 503s.
    429s (Rate Limits) or 400s fail instantly to allow fallback to the next model.
    """
    BASE_MS = 0.5
    CAP_MS = 4.0
    ATTEMPTS = 3
    
    for attempt in range(ATTEMPTS):
        try:
            return await _try_model(model, messages, max_tokens)
        except CircuitOpenError:
            raise  # Break out immediately, model is dead
        except Exception as e:
            error_str = str(e).lower()
            # If rate limited, don't sleep - fail instantly to trigger fallback pool
            if any(kw in error_str for kw in ("rate", "429", "capacity")):
                logger.warning(f"[{model}] Rate limit hit — failing over instantly.")
                breaker = get_breaker(model)
                await breaker.on_failure()
                _update_cb_metric(model)
                raise
                
            # Transient server overload (502, 503) - worth a quick jittered retry
            if any(kw in error_str for kw in ("503", "502", "timeout", "unavailable")):
                if attempt < ATTEMPTS - 1:
                    # Full Jitter (AWS pattern)
                    sleep_time = random.uniform(0, min(CAP_MS, BASE_MS * (2 ** attempt)))
                    logger.warning(f"[{model}] Transient error, retrying in {sleep_time:.2f}s... Error: {e}")
                    await asyncio.sleep(sleep_time)
                    continue
            
            # Any other error or out of retries - record failure and re-raise
            logger.error(f"[{model}] Request failed: {e}")
            breaker = get_breaker(model)
            await breaker.on_failure()
            _update_cb_metric(model)
            raise


async def _call_sequential(models: list[str], messages: list[dict], max_tokens: int) -> LLMResult:
    """
    Strong-tier routing: Strict Primary Fallback.

    Try models in *fixed* order — primary first, then fallbacks.  Each model
    is only tried if the previous one fails or its breaker is OPEN.  No
    weighted shuffle; the primary model absorbs 100% of traffic under normal
    conditions.

    This keeps Groq's shared 30 RPM org budget fully reserved for the
    weak-tier pool, since Groq 120B is only reached on Azure failure.
    """
    for model in models:
        try:
            return await _execute_with_retries(model, messages, max_tokens)
        except CircuitOpenError:
            logger.debug(f"[strong] Circuit OPEN for {model}, trying next.")
            continue
        except Exception:
            # Failure already recorded in _execute_with_retries
            continue

    raise AllProvidersExhausted(
        f"All strong-tier models exhausted: {models}"
    )


async def _call_pool(models: list[str], messages: list[dict], max_tokens: int) -> LLMResult:
    """
    Weak-tier routing: Org-Aware Weighted Pool.

    Models are tried in weighted-random order (proportional to their
    *effective* remaining RPM — the min of per-model and org-group budget).
    On failure the request retries on the next model in the shuffled order.
    """
    model_order = _weighted_shuffle(models)

    if not model_order:
        raise AllProvidersExhausted(
            f"All weak-tier models are currently unavailable."
        )

    for model in model_order:
        try:
            return await _execute_with_retries(model, messages, max_tokens)
        except CircuitOpenError:
            logger.debug(f"[weak] Circuit OPEN for {model}, trying next.")
            continue
        except Exception:
            # Failure already recorded in _execute_with_retries
            continue

    raise AllProvidersExhausted(
        f"All weak-tier models exhausted."
    )


# ── Public API ───────────────────────────────────────────────────────────

async def call_model(
    tier: str,
    prompt: str,
    complexity: float = 0.5,
    domain: str = "",
    has_rag: bool = False,
) -> LLMResult:
    """
    Fire one completion call based on the requested tier ("strong" or "weak").
    """
    if tier not in ("strong", "weak"):
        raise ValueError(f"Unknown tier: {tier!r}")

    # Build messages payload.
    messages = []
    
    # Use soft guardrails: allow models to generate up to the ceiling
    max_tokens = settings.max_tokens_ceiling
    
    sys_prompt = get_system_prompt(domain, tier, has_rag)
    
    messages.append({
        "role": "system",
        "content": sys_prompt,
    })
    messages.append({"role": "user", "content": prompt})

    if tier == "strong":
        # Strict Primary Fallback — Azure first, Groq 120B only on failure.
        all_models = [settings.strong_model] + settings.strong_fallback_models
        return await _call_sequential(all_models, messages, max_tokens=max_tokens)
    else:
        # Org-Aware Weighted Pool — distribute across weak models.
        all_models = [settings.weak_model] + settings.weak_fallback_models
        return await _call_pool(all_models, messages, max_tokens=max_tokens)
