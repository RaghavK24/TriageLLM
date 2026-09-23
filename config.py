"""
Central configuration. All tunables live here so the router logic in app/router.py
stays clean and readable — an interviewer should be able to open router.py and
understand it without also having to know what "0.55" means.

Uses pydantic-settings (BaseSettings) instead of a raw frozen dataclass so that:
  - Invalid env vars are caught at startup with a clear error message.
  - Type coercion is automatic (e.g. "0.55" → 0.55).
  - .env file is loaded automatically without an explicit load_dotenv() call.
"""
from __future__ import annotations
from typing import List
from pydantic import field_validator, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        # Extra env vars (e.g. API keys read directly by LiteLLM) are ignored.
        extra="ignore",
    )

    # ---- Model IDs (LiteLLM format: "<provider>/<model>") ----
    strong_model: str = "azure/gpt-4o"
    weak_model: str = "groq/openai/gpt-oss-20b"

    # Fallback models as comma-separated strings (pydantic will coerce them).
    # We store as str and parse in a validator so that the .env format
    # ("model1,model2") keeps working exactly as before.
    strong_fallback_models_raw: str = Field(
        default="",
        alias="STRONG_FALLBACK_MODELS",
    )
    weak_fallback_models_raw: str = Field(
        default="groq/openai/gpt-oss-120b,gemini/gemini-3.6-flash,mistral/mistral-small-latest",
        alias="WEAK_FALLBACK_MODELS",
    )

    # ---- Concurrency / load ----
    max_concurrent_requests: int = Field(default=60, gt=0)

    # ---- Routing thresholds. All are on [0, 1]. See app/router.py ----
    complexity_threshold: float = Field(default=0.55, ge=0.0, le=1.0)
    load_high_threshold: float = Field(default=0.70, ge=0.0, le=1.0)
    load_critical_threshold: float = Field(default=0.90, ge=0.0, le=1.0)

    # Fraction of capacity at which strong-tier requests are shed (fail-fast).
    # Default 0.70 → 35 active requests at capacity=50 (matches the old magic
    # number in router.py that the code review flagged as undocumented).
    load_shed_strong_fraction: float = Field(default=0.70, ge=0.0, le=1.0)

    # ---- Circuit Breaker ----
    cb_failure_threshold: int = Field(default=3, gt=0)
    cb_recovery_timeout: float = Field(default=30.0, gt=0.0)

    # ---- Embeddings (used for semantic cache and heuristic fallback) ----
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    semantic_cache_dir: str = "./semantic_cache_db"

    # ---- RAG ----
    rag_persist_dir: str = "./chroma_db"
    rag_top_k: int = Field(default=3, gt=0)
    rag_distance_threshold: float = Field(default=0.6, ge=0.0, le=1.0)

    # ---- Generation ----
    max_tokens_ceiling: int = Field(default=2048, gt=0)
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)

    # ---- Semantic Cache ----
    semantic_cache_threshold: float = Field(default=0.15, ge=0.0, le=1.0)
    semantic_cache_ttl: int = Field(default=3600, gt=0)  # 1 hour

    # ---- Request Coalescing ----
    coalesce_timeout: float = Field(default=60.0, gt=0.0)

    # ---- DistilBERT classifier (fine-tuned, optional) ----
    distilbert_model_dir: str = "Rk24012003/adaptive-rag-distilbert"

    # ---- Derived properties (not env vars) ----

    @property
    def strong_fallback_models(self) -> List[str]:
        """Parse the comma-separated fallback list into a Python list."""
        return [m.strip() for m in self.strong_fallback_models_raw.split(",") if m.strip()]

    @property
    def weak_fallback_models(self) -> List[str]:
        return [m.strip() for m in self.weak_fallback_models_raw.split(",") if m.strip()]

    @property
    def load_shed_strong_threshold(self) -> int:
        """
        Absolute in-flight count above which strong-tier requests are shed.

        Computed from load_shed_strong_fraction × max_concurrent_requests so
        the threshold automatically scales if capacity is changed via env var.
        Replaces the old hardcoded magic number `in_flight >= 35` in router.py.
        """
        return int(self.load_shed_strong_fraction * self.max_concurrent_requests)

    # ---- Cross-field validation ----

    @field_validator("load_critical_threshold")
    @classmethod
    def critical_above_high(cls, v: float, info) -> float:
        high = info.data.get("load_high_threshold", 0.70)
        if v <= high:
            raise ValueError(
                f"load_critical_threshold ({v}) must be greater than "
                f"load_high_threshold ({high})"
            )
        return v


settings = Settings()
