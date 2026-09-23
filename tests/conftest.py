import pytest
from unittest.mock import patch
from app.circuit_breaker import CircuitBreaker
from app.rate_limiter import ProviderBudget

@pytest.fixture
def circuit_breaker():
    """Fresh circuit breaker with low thresholds for fast testing."""
    return CircuitBreaker(
        failure_threshold=3, 
        recovery_timeout=1.0,  # 1 second for fast tests
        window_seconds=5.0,
    )

@pytest.fixture
def provider_budget():
    """Fresh provider budget with known RPM limit."""
    return ProviderBudget(rpm_limit=10)

@pytest.fixture
def mock_settings():
    """Override settings for deterministic testing."""
    with patch("config.settings") as mock:
        mock.complexity_threshold = 0.55
        mock.load_high_threshold = 0.70
        mock.load_critical_threshold = 0.90
        mock.load_shed_strong_fraction = 0.70
        mock.max_concurrent_requests = 50
        mock.load_shed_strong_threshold = 35
        mock.strong_model = "test/strong-model"
        mock.weak_model = "test/weak-model"
        mock.coalesce_timeout = 1.0
        mock.semantic_cache_ttl = 3600
        mock.semantic_cache_threshold = 0.15
        mock.embedding_model = "all-MiniLM-L6-v2"
        mock.semantic_cache_dir = "dummy_cache_dir"
        mock.rag_persist_dir = "dummy_rag_dir"
        mock.rag_top_k = 2
        mock.rag_distance_threshold = 0.6
        mock.distilbert_model_dir = "dummy_model_dir"
        yield mock

