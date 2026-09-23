"""
THE routing decision.

This is the file you will walk an interviewer through. Keep it small, keep it
readable, keep the logic explicit. No magic — every threshold comes from
config.py and every branch has a comment explaining WHY.

Inputs (both normalized to [0, 1]):
    complexity  — how "hard" the prompt looks (from app/classifier.py)
    load        — fraction of concurrent capacity currently in use

Output:
    RoutingDecision(tier, model, reason)  — or raises LoadSheddingError

The rule surface, in plain English:

  1. If load is CRITICAL (>= load_critical_threshold, default 0.90),
     raise the complexity bar by +0.30. This heavily biases toward the
     cheap model while still allowing genuinely complex queries through
     to the strong model. (The previous design forced ALL traffic to weak,
     which created a thundering herd on the weak-tier providers.)

  2. If load is HIGH (>= load_high_threshold, default 0.70), raise the
     complexity bar by +0.15 — a moderate penalty.

  3. If the prompt's complexity >= the effective bar, send to the strong
     model.

  4. Otherwise, send to the cheap model. Most prompts land here — short,
     factual, low-effort — and this is where the cost savings come from.

Why a rule-based router and not a learned one? Two reasons:
  - The point of the demo is to *show* an explainable trade-off between
    cost, latency, and quality. A 4-line decision function makes that
    visible; a learned model hides it.
  - There is no ground-truth "which tier should have answered this?"
    training data for our specific model pair, so any learned router
    would just be memorizing another rubric anyway.
"""
from __future__ import annotations
from dataclasses import dataclass
from config import settings


STRONG = "strong"
WEAK = "weak"


class LoadSheddingError(Exception):
    """
    Raised by route() when the system is too congested to safely queue a
    strong-tier request without causing tail-latency blowup.

    Carrying HTTP-layer concerns (status codes) inside a domain object
    (RoutingDecision.tier) was a design smell — the old code set
    tier="429_TOO_MANY_REQUESTS" and then checked that string in main.py.
    A proper exception separates the routing domain from the HTTP layer:
    route() raises, main.py catches and converts to HTTPException.
    """
    def __init__(self, in_flight: int, threshold: int):
        self.in_flight = in_flight
        self.threshold = threshold
        super().__init__(
            f"System congested ({in_flight} active, shed threshold={threshold}). "
            "Dropping strong-tier request to protect p95 latency."
        )


@dataclass
class RoutingDecision:
    tier: str          # "strong" | "weak" only — no HTTP codes leaked here
    model: str         # actual model id, ready to pass to LiteLLM
    reason: str        # short human-readable explanation


def route(
    complexity: float,
    load: float,
    groq_usage: float = 0.0,
    in_flight: int = 0
) -> RoutingDecision:
    """
    Decide which tier to send this request to.

    Args:
        complexity: classifier score, in [0, 1]
        load: current in-flight / capacity, in [0, 1]
        groq_usage: fraction of Groq's RPM budget used [0, 1]
        in_flight: total concurrent requests currently active

    Returns:
        RoutingDecision — pass `.model` straight to the LLM client.

    Raises:
        LoadSheddingError — if the system is too congested to safely serve
        a strong-tier request. main.py converts this to HTTP 429.
    """
    # Guard rails — never trust callers.
    complexity = max(0.0, min(1.0, complexity))
    load = max(0.0, min(1.0, load))

    # --- Step 1: Dynamic Threshold Adjustment ---
    # Base threshold comes from config; we raise it under load to aggressively
    # shed marginal traffic to the cheap tier, protecting tail latency.
    effective_bar = settings.complexity_threshold
    if load >= settings.load_critical_threshold:
        effective_bar = settings.complexity_threshold + 0.30
    elif load >= settings.load_high_threshold:
        effective_bar = settings.complexity_threshold + 0.15

    # --- Step 2: Base Complexity Decision ---
    if complexity >= effective_bar:
        target_tier = STRONG
        reason = (
            f"complexity {complexity:.2f} >= bar {effective_bar:.2f} "
            f"(load {load:.2f}): strong model justified"
        )
    else:
        target_tier = WEAK
        reason = (
            f"complexity {complexity:.2f} < bar {effective_bar:.2f} "
            f"(load {load:.2f}): cheap tier is sufficient"
        )

    # --- Step 3: Rate-Limit Aware Spillover ---
    # If the decision was WEAK, but Groq is functionally maxed out, spill to STRONG.
    if target_tier == WEAK and groq_usage > 0.90:
        target_tier = STRONG
        reason = f"spillover: Groq budget at {groq_usage*100:.0f}%, rerouting to strong to avoid crash"

    # --- Step 4: p95 Latency Protection (Fail-Fast Load Shedding) ---
    # If the request is going to STRONG, but the server is already heavily
    # congested, queueing it will cause 7-8 second tail latencies.
    # --- Graceful Degradation ---
    # If the system is heavily loaded, we refuse to route to the STRONG tier
    # (Azure) because it takes 20s and ties up capacity. Instead of rejecting
    # the user, we forcefully downgrade them to the WEAK tier (Groq).
    if target_tier == STRONG and in_flight >= settings.load_shed_strong_threshold:
        return RoutingDecision(
            tier=WEAK, 
            model=settings.weak_model, 
            reason=f"graceful_degradation_load_{in_flight}"
        )

    # --- Final Return ---
    if target_tier == STRONG:
        return RoutingDecision(tier=STRONG, model=settings.strong_model, reason=reason)
    else:
        return RoutingDecision(tier=WEAK, model=settings.weak_model, reason=reason)
