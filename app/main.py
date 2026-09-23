"""
FastAPI entrypoint.

Changes to this file focus on exposing the routing decision explicitly in the
API response, and implementing fail-fast load shedding (returning HTTP 429
before ANY work is done if the system is overloaded).
"""
from __future__ import annotations
import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import Any, Dict

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from app.metrics import (
    REQUESTS_TOTAL, ROUTING_DECISIONS, LLM_LATENCY,
    IN_FLIGHT_REQUESTS, CACHE_HITS, CACHE_MISSES
)

from app.classifier import load_classifier, score_prompt
from app.llm_client import call_model, get_breaker_states, AllProvidersExhausted
from app.load_tracker import LoadTracker
from app.rate_limiter import get_effective_remaining_frac
from app.router import route, LoadSheddingError
from app.coalescer import RequestCoalescer, generate_coalesce_key
from app.semantic_cache import SemanticCache
from app.rag import get_store
from config import settings

STRONG = "strong"
WEAK = "weak"

logger = logging.getLogger("uvicorn.error")

# Global load tracker initialized with capacity from config.
tracker = LoadTracker(capacity=settings.max_concurrent_requests)

coalescer = RequestCoalescer(timeout=settings.coalesce_timeout)
semantic_cache = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global semantic_cache
    # Warm up singletons on startup.
    load_classifier()  # Load DistilBERT model safely (with threading.Lock)
    get_store()  # Warm up RAG singleton
    
    from langchain_huggingface import HuggingFaceEmbeddings
    embeddings = HuggingFaceEmbeddings(model_name=settings.embedding_model)
    semantic_cache = SemanticCache(
        embeddings=embeddings, 
        persist_dir=settings.semantic_cache_dir,
        threshold=settings.semantic_cache_threshold,
        ttl_seconds=settings.semantic_cache_ttl
    )
    yield


app = FastAPI(title="Adaptive LLM Gateway", lifespan=lifespan)


class ChatRequest(BaseModel):
    prompt: str = Field(..., max_length=8000)
    use_rag: bool = True


class ChatResponse(BaseModel):
    answer: str
    metadata: Dict[str, Any]


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    """
    Core entrypoint.

    Workflow:
      1. RAG Retrieval
      2. Complexity Scoring — DistilBERT inference (local, fast).
      3. Router — Decides tier ("strong" or "weak") based on complexity & load.
      4. Semantic Cache LOOKUP.
      5. Request Coalescing (wraps LLM Client).
      6. Semantic Cache STORE.
    """
    # -- 1. Classification & Scoring --
    # Local, zero-cost scoring (runs in asyncio threadpool). We score the RAW prompt FIRST.
    classification = await asyncio.to_thread(score_prompt, req.prompt)

    # -- 2. Conditionally Fetch RAG Context --
    rag_context = ""
    # We only use RAG if the user requested it AND our classifier says it's needed
    if req.use_rag and classification.needs_rag:
        store = await asyncio.to_thread(get_store)
        rag_context = await asyncio.to_thread(store.retrieve, req.prompt)

    full_prompt = req.prompt
    if rag_context:
        full_prompt = f"Context:\n{rag_context}\n\nQuestion:\n{req.prompt}"

    # -- 2. Routing --
    # Track request. The `async with` acquires the semaphore, which will
    # block here if in_flight >= capacity.
    async with tracker.track():
        # Read the load fraction. Since we are inside the `track()` block, 
        # this fraction inherently includes the current request (+1/capacity bias). 
        # This is safe and conservative.
        current_load = tracker.load_fraction
        in_flight = tracker.in_flight
        
        # We need Groq's remaining quota to see if we should spill over.
        # Check either model in the weak pool; they share the org budget anyway.
        groq_remaining = get_effective_remaining_frac(settings.weak_model)
        groq_usage = 1.0 - groq_remaining

        try:
            decision = route(
                complexity=classification.complexity_score,
                load=current_load,
                groq_usage=groq_usage,
                in_flight=in_flight,
            )
        except LoadSheddingError as e:
            # The router determined the system is too congested to serve a strong-tier request.
            logger.warning(f"Load shedding: {e}")
            REQUESTS_TOTAL.labels(tier=STRONG, cache_hit="False", status="load_shed").inc()
            raise HTTPException(status_code=429, detail=str(e))

        # -- 3. Semantic Cache LOOKUP --
        cached_response = None
        if semantic_cache is not None:
            cached_response = await asyncio.to_thread(
                semantic_cache.lookup, req.prompt, decision.tier
            )
        if cached_response is not None:
            REQUESTS_TOTAL.labels(tier=decision.tier, cache_hit="True", status="success").inc()
            ROUTING_DECISIONS.labels(tier=decision.tier, reason=decision.reason).inc()
            IN_FLIGHT_REQUESTS.set(tracker.in_flight)
            CACHE_HITS.inc()
            return ChatResponse(
                answer=cached_response,
                metadata={
                    "routing": {
                        "tier": decision.tier,
                        "model_used": "cache",
                        "reason": decision.reason,
                        "load_fraction": round(current_load, 2),
                        "groq_usage": round(groq_usage, 2),
                    },
                    "classifier": classification.features,
                    "domain": classification.domain,
                    "needs_rag": classification.needs_rag,
                    "cache_hit": True,
                    "coalesced": False,
                    "rag_context_chars": len(rag_context)
                }
            )

        # -- 4. Request Coalescing & LLM Execution --
        t0 = time.monotonic()
        try:
            key = generate_coalesce_key(req.prompt, decision.tier)
            llm_result, was_coalesced = await coalescer.get_or_fetch(
                key,
                call_model,
                tier=decision.tier,
                prompt=full_prompt,
                complexity=classification.complexity_score,
                domain=classification.domain,
                has_rag=bool(rag_context),
            )
            LLM_LATENCY.labels(tier=decision.tier, model=llm_result.model).observe(time.monotonic() - t0)
        except AllProvidersExhausted as e:
            logger.error(f"All providers exhausted for {decision.tier} tier: {e}")
            REQUESTS_TOTAL.labels(tier=decision.tier, cache_hit="False", status="error").inc()
            raise HTTPException(status_code=503, detail="All LLM providers currently unavailable.")
        except Exception as e:
            logger.error(f"Unexpected LLM error: {e}")
            REQUESTS_TOTAL.labels(tier=decision.tier, cache_hit="False", status="error").inc()
            raise HTTPException(status_code=500, detail="Internal server error")

        # -- 5. Semantic Cache STORE --
        if semantic_cache is not None:
            await asyncio.to_thread(
                semantic_cache.store, req.prompt, llm_result.text, 
                decision.tier, llm_result.model
            )

        REQUESTS_TOTAL.labels(tier=decision.tier, cache_hit="False", status="success").inc()
        ROUTING_DECISIONS.labels(tier=decision.tier, reason=decision.reason).inc()
        IN_FLIGHT_REQUESTS.set(tracker.in_flight)
        CACHE_MISSES.inc()

        return ChatResponse(
            answer=llm_result.text,
            metadata={
                "routing": {
                    "tier": decision.tier,
                    "model_used": llm_result.model,
                    "reason": decision.reason,
                    "load_fraction": round(current_load, 2),
                    "groq_usage": round(groq_usage, 2),
                },
                "classifier": classification.features,
                "domain": classification.domain,
                "needs_rag": classification.needs_rag,
                "cache_hit": False,
                "coalesced": was_coalesced,
                "rag_context_chars": len(rag_context),
                "usage": {
                    "prompt_tokens": getattr(llm_result, "prompt_tokens", None),
                    "completion_tokens": getattr(llm_result, "completion_tokens", None),
                    "cost_usd": getattr(llm_result, "cost_usd", None),
                }
            }
        )


@app.post("/chat_baseline", response_model=ChatResponse)
async def chat_baseline_endpoint(req: ChatRequest):
    """
    Control group endpoint for scientific benchmarking.
    Simulates a standard, non-adaptive AI application:
      1. Always retrieves RAG (wasting time).
      2. Always uses the STRONG model (wasting money).
      3. Never uses Semantic Cache or Coalescer.
      4. Always uses the generic system prompt (bypassing the domain classifier).
    """
    # 1. ALWAYS retrieve RAG
    store = await asyncio.to_thread(get_store)
    rag_context = await asyncio.to_thread(store.retrieve, req.prompt)
    
    full_prompt = req.prompt
    if rag_context:
        full_prompt = f"Context:\n{rag_context}\n\nQuestion:\n{req.prompt}"

    # 2. ALWAYS call STRONG directly (bypassing router, cache, and coalescer)
    # We pass 'general' domain so it uses the generic system prompt, just like a standard app.
    try:
        llm_result = await call_model(
            tier=STRONG,
            prompt=full_prompt,
            complexity=1.0,
            domain="general",
            has_rag=True
        )
    except Exception as e:
        logger.error(f"Baseline error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
        
    return ChatResponse(
        answer=llm_result.text,
        metadata={
            "routing": {
                "tier": STRONG,
                "model_used": llm_result.model,
                "reason": "baseline_override",
                "load_fraction": 1.0,
                "groq_usage": 0.0,
            },
            "classifier": {},
            "domain": "general",
            "needs_rag": True,
            "cache_hit": False,
            "coalesced": False,
            "rag_context_chars": len(rag_context),
            "usage": {
                "prompt_tokens": getattr(llm_result, "prompt_tokens", None),
                "completion_tokens": getattr(llm_result, "completion_tokens", None),
                "cost_usd": getattr(llm_result, "cost_usd", None),
            }
        }
    )


@app.get("/health")
async def health_endpoint():
    """
    Diagnostic endpoint to inspect the router's internal state.
    Note: In-memory counters (like cache hits/misses) reset on server restart. 
    Use the /metrics Prometheus endpoint for persistent, authoritative metrics.
    """
    return {
        "status": "ok",
        "load": {
            "in_flight": tracker.in_flight,
            "capacity": tracker.capacity,
            "fraction": round(tracker.load_fraction, 2)
        },
        "coalescing": {
            "total_requests": coalescer.total_requests,
            "coalesced_requests": coalescer.coalesced_requests,
            "hit_rate": round(coalescer.hit_rate, 3),
            "in_flight_keys": len(coalescer._in_flight),
        },
        "semantic_cache": {
            "hits": semantic_cache.hits if semantic_cache else 0,
            "misses": semantic_cache.misses if semantic_cache else 0,
            "hit_rate": round(semantic_cache.hit_rate, 3) if semantic_cache else 0.0,
        },
        "circuit_breakers": get_breaker_states()
    }

@app.get("/metrics")
async def metrics_endpoint():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
