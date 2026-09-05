"""
Central configuration. All tunables live here so the router logic in app/router.py
stays clean and readable — an interviewer should be able to open router.py and
understand it without also having to know what "0.55" means.
"""
from __future__ import annotations
import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    # ---- Model IDs (LiteLLM format: "<provider>/<model>") ----
    # Primary models
    strong_model: str = os.getenv("STRONG_MODEL", "openai/gpt-4o")
    weak_model: str = os.getenv("WEAK_MODEL", "groq/openai/gpt-oss-20b")

    # Fallback models (comma-separated list)
    strong_fallback_models: list[str] = field(
        default_factory=lambda: [
            m.strip() for m in os.getenv("STRONG_FALLBACK_MODELS", "").split(",") if m.strip()
        ]
    )
    weak_fallback_models: list[str] = field(
        default_factory=lambda: [
            m.strip() for m in os.getenv("WEAK_FALLBACK_MODELS", "groq/openai/gpt-oss-120b,gemini/gemini-3.6-flash,mistral/mistral-small-latest").split(",") if m.strip()
        ]
    )

    # ---- Concurrency / load ----
    max_concurrent_requests: int = int(os.getenv("MAX_CONCURRENT_REQUESTS", "50"))

    # ---- Routing thresholds. All are on [0, 1]. See app/router.py for how they're used. ----
    # If complexity >= this, we lean toward the strong model.
    complexity_threshold: float = float(os.getenv("COMPLEXITY_THRESHOLD", "0.55"))
    # If load fraction >= this, we start biasing toward the cheap model to protect latency.
    load_high_threshold: float = float(os.getenv("LOAD_HIGH_THRESHOLD", "0.70"))
    # If load fraction >= this, we force the cheap model regardless of complexity.
    load_critical_threshold: float = float(os.getenv("LOAD_CRITICAL_THRESHOLD", "0.90"))

    # ---- Circuit Breaker ----
    cb_failure_threshold: int = int(os.getenv("CB_FAILURE_THRESHOLD", "3"))
    cb_recovery_timeout: float = float(os.getenv("CB_RECOVERY_TIMEOUT", "30.0"))

    # ---- Embeddings (used by both RAG and the classifier) ----
    embedding_model: str = os.getenv(
        "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
    )

    # ---- RAG ----
    chroma_persist_dir: str = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
    rag_top_k: int = int(os.getenv("RAG_TOP_K", "3"))
    sample_docs_dir: str = os.getenv("SAMPLE_DOCS_DIR", "./data/sample_docs")
    # Chunks with a distance score above this are considered irrelevant and dropped.
    # Lower = stricter (only very relevant docs). Chroma L2 distances typically
    # range from 0.0 (identical) to ~2.0 (unrelated). 1.2 is a reasonable default.
    rag_distance_threshold: float = float(os.getenv("RAG_DISTANCE_THRESHOLD", "1.2"))

    # ---- Generation ----
    weak_max_tokens: int = int(os.getenv("WEAK_MAX_TOKENS", "150"))
    strong_max_tokens: int = int(os.getenv("STRONG_MAX_TOKENS", "512"))
    temperature: float = float(os.getenv("TEMPERATURE", "0.2"))

    # ---- DistilBERT classifier (fine-tuned, optional) ----
    distilbert_model_dir: str = os.getenv(
        "DISTILBERT_MODEL_DIR", "Rk24012003/adaptive-rag-distilbert"
    )


settings = Settings()
