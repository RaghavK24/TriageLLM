import pytest
import time
from unittest.mock import MagicMock, patch
from app.semantic_cache import SemanticCache

@pytest.fixture
def mock_embeddings():
    emb = MagicMock()
    emb.embed_query.return_value = [0.1] * 384
    return emb

@pytest.fixture
def semantic_cache(mock_embeddings):
    # Mocking Chroma so we don't actually create a DB on disk
    with patch('app.semantic_cache.Chroma') as mock_chroma:
        cache = SemanticCache(embeddings=mock_embeddings, persist_dir="dummy_dir", threshold=0.15, ttl_seconds=60)
        cache._store = MagicMock()
        return cache

def test_cache_miss_on_empty(semantic_cache):
    semantic_cache._store.similarity_search_with_score.return_value = []
    
    result = semantic_cache.lookup("Hello", "strong")
    assert result is None
    assert semantic_cache.misses == 1
    assert semantic_cache.hits == 0

def test_cache_hit(semantic_cache):
    mock_doc = MagicMock()
    mock_doc.metadata = {
        "response": "Cached answer",
        "cached_at": time.time()
    }
    # Return doc and a distance of 0.05 (< 0.15 threshold)
    semantic_cache._store.similarity_search_with_score.return_value = [(mock_doc, 0.05)]
    
    result = semantic_cache.lookup("Hello", "strong")
    assert result == "Cached answer"
    assert semantic_cache.hits == 1

def test_cache_miss_above_threshold(semantic_cache):
    mock_doc = MagicMock()
    mock_doc.metadata = {
        "response": "Cached answer",
        "cached_at": time.time()
    }
    # Return doc and a distance of 0.20 (> 0.15 threshold)
    semantic_cache._store.similarity_search_with_score.return_value = [(mock_doc, 0.20)]
    
    result = semantic_cache.lookup("Hello", "strong")
    assert result is None
    assert semantic_cache.misses == 1

def test_cache_miss_expired_ttl(semantic_cache):
    mock_doc = MagicMock()
    mock_doc.metadata = {
        "response": "Cached answer",
        "cached_at": time.time() - 100  # 100 seconds ago, TTL is 60
    }
    semantic_cache._store.similarity_search_with_score.return_value = [(mock_doc, 0.05)]
    
    result = semantic_cache.lookup("Hello", "strong")
    assert result is None
    assert semantic_cache.misses == 1

def test_cache_store_ignores_short_responses(semantic_cache):
    semantic_cache.store("Hello", "Short", "strong", "model")
    semantic_cache._store.add_texts.assert_not_called()

def test_cache_store_success(semantic_cache):
    response = "This is a sufficiently long response to be cached."
    semantic_cache.store("Hello", response, "strong", "model")
    assert semantic_cache._store.add_texts.call_count == 1

