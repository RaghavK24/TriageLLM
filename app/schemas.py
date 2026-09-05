"""Request / response schemas for the FastAPI endpoints."""
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=8000)
    use_rag: bool = True


class ChatResponse(BaseModel):
    answer: str
    tier: str                    # "strong" | "weak" | "baseline_strong"
    model: str                   # actual LiteLLM model id used
    complexity: float            # classifier score ∈ [0, 1]
    load_fraction: float         # in-flight / capacity ∈ [0, 1]
    routing_reason: str          # short human-readable justification
    latency_ms: float
    cost_usd: float
    rag_context_used: bool
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None

