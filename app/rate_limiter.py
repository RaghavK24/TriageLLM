"""
Proactive rate-limit tracker.

Instead of waiting for a 429 to discover we've exceeded a provider's limit
(reactive), we track our own request timestamps per model and expose a
`remaining_rpm` property the router can use to distribute load *before*
any provider rejects us.

Rate-limit budgets are seeded from eval/results/rate_limits_measured.json
(produced by the rate-limit probing script). If the file doesn't exist,
we fall back to generous defaults so the server still starts.

Org-aware quota groups
─────────────────────
Some providers (notably Groq) enforce a single *org-wide* RPM limit that is
shared across every model on that API key.  The per-model tracker alone
would see N models × 28 RPM = phantom capacity that doesn't actually exist.

The group budget layer fixes this:
  • Every Groq model is mapped to the "groq" quota group (30 RPM).
  • When recording a request or computing remaining weight, the *minimum*
    of the model budget and the group budget is used.
  • This means the weighted shuffle in llm_client.py will naturally
    deprioritize all Groq models once the org ceiling is near, and spill
    overflow to non-Groq providers (Gemini, Mistral, etc.).
"""
from __future__ import annotations
import json
import logging
import time
from collections import deque
from pathlib import Path
from threading import Lock

logger = logging.getLogger(__name__)

# Default RPM limits when measured data is unavailable.
_DEFAULT_RPM = 30

# ── Provider-level org quota groups ──────────────────────────────────────────
#
# Maps a provider prefix (the first segment of the LiteLLM model string, e.g.
# "groq" in "groq/openai/gpt-oss-20b") to its shared org-wide RPM limit.
#
# Adjust if you get a higher Groq tier or add other shared-limit providers.
_QUOTA_GROUPS: dict[str, int] = {
    "groq": 30,   # Groq org-wide limit (~30 RPM on the free/starter tier)
}


def _provider_of(model: str) -> str:
    """Return the provider prefix of a LiteLLM model string."""
    return model.split("/")[0].lower()


class ProviderBudget:
    """Track remaining RPM budget for a single model or provider group."""

    def __init__(self, rpm_limit: int):
        self.rpm_limit = max(1, rpm_limit)
        # deque of timestamps (monotonic) for requests sent in the current window
        self._timestamps: deque[float] = deque()
        self._lock = Lock()

    def _prune(self) -> None:
        """Remove entries older than 60 seconds."""
        cutoff = time.monotonic() - 60.0
        while self._timestamps and self._timestamps[0] < cutoff:
            self._timestamps.popleft()

    @property
    def remaining_rpm(self) -> int:
        with self._lock:
            self._prune()
            return max(0, self.rpm_limit - len(self._timestamps))

    @property
    def usage_fraction(self) -> float:
        """Fraction of the RPM budget already consumed, in [0, 1]."""
        with self._lock:
            self._prune()
            return min(1.0, len(self._timestamps) / self.rpm_limit)

    def can_accept(self) -> bool:
        return self.remaining_rpm > 0

    def record_request(self) -> None:
        with self._lock:
            self._timestamps.append(time.monotonic())


# ── Module-level singleton registries ────────────────────────────────────────

_budgets: dict[str, ProviderBudget] = {}
_group_budgets: dict[str, ProviderBudget] = {}
_loaded = False


def _load_measured_limits() -> dict[str, int]:
    """Read safe_rpm values from the measured rate-limits file."""
    path = Path(__file__).resolve().parent.parent / "eval" / "results" / "rate_limits_measured.json"
    if not path.exists():
        logger.warning(f"Rate-limit data not found at {path}; using defaults.")
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return {model: info["safe_rpm"] for model, info in data.items() if "safe_rpm" in info}
    except Exception as e:
        logger.error(f"Failed to load rate-limit data: {e}")
        return {}


def _ensure_loaded() -> None:
    global _loaded
    if _loaded:
        return
    measured = _load_measured_limits()
    for m, rpm in measured.items():
        _budgets[m] = ProviderBudget(rpm)

    # Initialise group budgets for every known quota group.
    for group, rpm in _QUOTA_GROUPS.items():
        _group_budgets[group] = ProviderBudget(rpm)

    _loaded = True
    logger.info(
        f"Rate-limit budgets loaded for {len(_budgets)} models: "
        + ", ".join(f"{m}={b.rpm_limit}rpm" for m, b in _budgets.items())
    )
    logger.info(
        f"Quota groups: "
        + ", ".join(f"{g}={b.rpm_limit}rpm" for g, b in _group_budgets.items())
    )


def get_budget(model: str) -> ProviderBudget:
    """Return (or lazily create) the per-model budget tracker for *model*."""
    _ensure_loaded()
    if model not in _budgets:
        _budgets[model] = ProviderBudget(_DEFAULT_RPM)
    return _budgets[model]


def get_group_budget(group: str) -> ProviderBudget | None:
    """Return the shared org-level budget for a provider group, or None."""
    _ensure_loaded()
    return _group_budgets.get(group)


def record_model_request(model: str) -> None:
    """
    Record one outgoing request for *model*.

    Records against BOTH the per-model budget AND the provider's org-level
    group budget (if the model belongs to a quota group).  Always call this
    instead of budget.record_request() directly so the group counter stays
    accurate.
    """
    get_budget(model).record_request()
    group = _provider_of(model)
    grp_budget = get_group_budget(group)
    if grp_budget is not None:
        grp_budget.record_request()


def get_effective_remaining_frac(model: str) -> float:
    """
    Return the effective remaining-capacity fraction for *model*, accounting
    for the provider's org-level quota group.

    This is the value the weighted shuffle should use as a weight:
      • floored at 0.05 so a nearly-full provider still gets some chance
      • capped at 1.0
    """
    model_frac = 1.0 - get_budget(model).usage_fraction

    group = _provider_of(model)
    grp_budget = get_group_budget(group)
    if grp_budget is not None:
        group_frac = 1.0 - grp_budget.usage_fraction
        # Use the more restrictive of the two limits.
        effective = min(model_frac, group_frac)
    else:
        effective = model_frac

    return max(0.05, effective)
