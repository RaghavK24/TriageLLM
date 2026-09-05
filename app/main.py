"""
FastAPI server wiring everything together.

Two endpoints:
  POST /chat            — adaptive router
  POST /chat_baseline   — always uses the strong model (this is what we
                          compare against in the eval)

Plus a small /stats endpoint that exposes the current load fraction, useful
if you want to eyeball the load tracker live during the demo.
"""
from __future__ import annotations
import asyncio
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.classifier import score_prompt
from app.llm_client import call_model, AllProvidersExhausted, get_breaker_states
from app.load_tracker import LoadTracker
from app.rag import get_store
from app.router import route, STRONG, WEAK
from app.schemas import ChatRequest, ChatResponse
from config import settings


tracker = LoadTracker(capacity=settings.max_concurrent_requests)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Warm up — construct the embedder and Chroma store once at startup so
    # the very first request isn't a 3-second cold-start outlier in the eval.
    _ = get_store()
    _ = score_prompt("warmup")
    yield


app = FastAPI(title="Adaptive Load-Aware RAG Router", lifespan=lifespan)

# ── Serve the chatbot frontend ──────────────────────────────────
_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

@app.get("/")
async def index():
    return FileResponse(_STATIC_DIR / "index.html")

app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


@app.get("/health")
async def health():
    return {"ok": True}


@app.get("/stats")
async def stats():
    from app.rate_limiter import get_group_budget
    groq_budget = get_group_budget("groq")
    groq_usage = groq_budget.usage_fraction if groq_budget else 0.0

    return {
        "in_flight": tracker.in_flight,
        "capacity": tracker.capacity,
        "load_fraction": tracker.load_fraction,
        "circuit_breakers": get_breaker_states(),
        "groq_usage": groq_usage,
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """Adaptive router: classifier + load-aware decision."""
    start = time.perf_counter()

    async with tracker.track():
        # 1. Retrieve RAG context (best-effort; empty string if the store is empty).
        #    Chroma.similarity_search + MiniLM embedding are synchronous CPU/IO — run in
        #    a worker thread so we don't freeze the event loop while other requests wait.
        rag_ctx = ""
        if req.use_rag:
            rag_ctx = await asyncio.to_thread(get_store().retrieve, req.prompt)

        # 2. Score complexity (fast, local, no LLM call). Also blocking because of the
        #    embedding call or distilbert inside — offload for the same reason as (1).
        complexity_result = await asyncio.to_thread(score_prompt, req.prompt)
        complexity = complexity_result.score

        # 3. Read current load and rate limits.
        load = tracker.load_fraction
        from app.rate_limiter import get_group_budget
        groq_budget = get_group_budget("groq")
        groq_usage = groq_budget.usage_fraction if groq_budget else 0.0

        # 4. Make the routing decision.
        decision = route(
            complexity=complexity, 
            load=load,
            groq_usage=groq_usage,
            in_flight=tracker.in_flight
        )
        
        if decision.tier == "429_TOO_MANY_REQUESTS":
            raise HTTPException(status_code=429, detail=decision.reason)

        # 5. Call the chosen model tier.
        try:
            result = await call_model(decision.tier, req.prompt, rag_context=rag_ctx or None)
        except AllProvidersExhausted as e:
            raise HTTPException(status_code=503, detail=str(e))

    latency_ms = (time.perf_counter() - start) * 1000.0

    return ChatResponse(
        answer=result.text,
        tier=decision.tier,
        model=result.model,
        complexity=complexity,
        load_fraction=load,
        routing_reason=decision.reason,
        latency_ms=latency_ms,
        cost_usd=result.cost_usd,
        rag_context_used=bool(rag_ctx),
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
    )


@app.post("/chat_baseline", response_model=ChatResponse)
async def chat_baseline(req: ChatRequest):
    """
    Naive baseline: always use the strong model.
    Same load tracker, same RAG, same everything — the ONLY difference is
    that routing is disabled and we go straight to the expensive tier.
    This is what the eval compares against.
    """
    start = time.perf_counter()

    async with tracker.track():
        rag_ctx = ""
        if req.use_rag:
            rag_ctx = await asyncio.to_thread(get_store().retrieve, req.prompt)

        # Still scored for reporting; offload for the same reason as /chat.
        complexity_result = await asyncio.to_thread(score_prompt, req.prompt)
        complexity = complexity_result.score
        load = tracker.load_fraction
        
        try:
            result = await call_model("strong", req.prompt, rag_context=rag_ctx or None)
        except AllProvidersExhausted as e:
            raise HTTPException(status_code=503, detail=str(e))

    latency_ms = (time.perf_counter() - start) * 1000.0
    return ChatResponse(
        answer=result.text,
        tier="baseline_strong",
        model=result.model,
        complexity=complexity,
        load_fraction=load,
        routing_reason="baseline: always strong",
        latency_ms=latency_ms,
        cost_usd=result.cost_usd,
        rag_context_used=bool(rag_ctx),
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
    )

