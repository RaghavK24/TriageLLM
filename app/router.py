"""
THE routing decision.

This is the file you will walk an interviewer through. Keep it small, keep it
readable, keep the logic explicit. No magic — every threshold comes from
config.py and every branch has a comment explaining WHY.

Inputs (both normalized to [0, 1]):
    complexity  — how "hard" the prompt looks (from app/classifier.py)
    load        — fraction of concurrent capacity currently in use

Output:
    RoutingDecision(tier, model, reason)

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


@dataclass
class RoutingDecision:
    tier: str          # "strong" | "weak"
    model: str         # actual model id, ready to pass to LiteLLM
    reason: str        # short human-readable explanation


import math
import random

def _sigmoid_route(complexity: float, load: float) -> RoutingDecision:
    """
    Probabilistic routing using a sigmoid curve.
    Instead of a hard threshold, we calculate a probability that the request
    needs the strong model, and route based on that.
    """
    # Base threshold shifts based on load (same logic as step function)
    base_threshold = settings.complexity_threshold
    if load >= settings.load_critical_threshold:
        # Load critical: heavy bias against strong, but don't block entirely.
        # A genuinely complex query (score ~0.9) can still reach strong.
        base_threshold += 0.30
    elif load >= settings.load_high_threshold:
        # Load high: raise the bar
        base_threshold += 0.15

    # Calculate probability using sigmoid
    # steepness parameter controls how "hard" the threshold is.
    # High steepness approaches a step function.
    x = complexity - base_threshold
    p_strong = 1.0 / (1.0 + math.exp(-settings.sigmoid_steepness * x))

    # Route based on random draw against probability
    if random.random() < p_strong:
        return RoutingDecision(
            tier=STRONG,
            model=settings.strong_model,
            reason=f"sigmoid (P={p_strong:.2f}) -> strong"
        )
    else:
        return RoutingDecision(
            tier=WEAK,
            model=settings.weak_model,
            reason=f"sigmoid (P={p_strong:.2f}) -> weak"
        )

def route(complexity: float, load: float) -> RoutingDecision:
    """
    Decide which tier to send this request to.

    Args:
        complexity: classifier score, in [0, 1]
        load: current in-flight / capacity, in [0, 1]

    Returns:
        RoutingDecision — pass `.model` straight to the LLM client.
    """
    # Guard rails — never trust callers.
    complexity = max(0.0, min(1.0, complexity))
    load = max(0.0, min(1.0, load))

    if settings.routing_mode == "smooth":
        return _sigmoid_route(complexity, load)

    # --- Standard Step Function Routing ---
    # --- Rule 1: system is nearly saturated. Raise the bar significantly ---
    # --- but don't unconditionally force cheap — genuinely hard prompts ---
    # --- still deserve the strong model. ---
    # (The old design forced ALL traffic to weak here, which created a
    # thundering herd on the weak-tier providers.)
    effective_bar = settings.complexity_threshold
    if load >= settings.load_critical_threshold:
        effective_bar = settings.complexity_threshold + 0.30
    elif load >= settings.load_high_threshold:
        effective_bar = settings.complexity_threshold + 0.15

    if complexity >= effective_bar:
        return RoutingDecision(
            tier=STRONG,
            model=settings.strong_model,
            reason=(
                f"complexity {complexity:.2f} >= bar {effective_bar:.2f} "
                f"(load {load:.2f}): strong model justified"
            ),
        )

    # --- Rule 3: default is the cheap tier. Most prompts land here. ---
    return RoutingDecision(
        tier=WEAK,
        model=settings.weak_model,
        reason=(
            f"complexity {complexity:.2f} < bar {effective_bar:.2f} "
            f"(load {load:.2f}): cheap tier is sufficient"
        ),
    )

