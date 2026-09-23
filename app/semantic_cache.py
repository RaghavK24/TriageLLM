import time
import uuid
import logging
import threading
from typing import Optional
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

logger = logging.getLogger(__name__)

class SemanticCache:
    """
    Application-layer KV cache equivalent for LLM responses.
    Uses ChromaDB with cosine distance for semantic similarity matching.
    """
    COLLECTION_NAME = "semantic_cache"
    
    def __init__(self, embeddings: HuggingFaceEmbeddings, persist_dir: str, threshold: float = 0.15, ttl_seconds: int = 3600):
        self._store = Chroma(
            collection_name=self.COLLECTION_NAME,
            embedding_function=embeddings,
            persist_directory=persist_dir,
            collection_metadata={"hnsw:space": "cosine"},  # CRITICAL for intuitive thresholds
        )
        self._threshold = threshold
        self._ttl_seconds = ttl_seconds
        # Metrics
        self.hits = 0
        self.misses = 0
        self._lock = threading.Lock()
    
    def lookup(self, prompt: str, tier: str) -> Optional[str]:
        """Search for a semantically similar cached response. Returns None on miss."""
        # Strong questions ONLY accept strong answers.
        # Weak questions accept BOTH weak and strong answers (tier fallback).
        if tier == "strong":
            tier_filter = {"tier": {"$eq": "strong"}}
        else:
            tier_filter = {"tier": {"$in": ["weak", "strong"]}}

        try:
            results = self._store.similarity_search_with_score(
                prompt, k=1,
                filter=tier_filter
            )
        except Exception as e:
            logger.warning(f"Semantic cache lookup failed (probably empty): {e}")
            self.misses += 1
            return None

        if not results:
            self.misses += 1
            return None
        
        doc, distance = results[0]
        
        # Distance check (cosine: 0 = identical, lower = better)
        if distance > self._threshold:
            self.misses += 1
            return None
        
        # TTL check
        cached_at = doc.metadata.get("cached_at", 0)
        if time.time() - cached_at > self._ttl_seconds:
            doc_id = doc.metadata.get("doc_id")
            if doc_id:
                try:
                    with self._lock:
                        self._store.delete(ids=[doc_id])
                except Exception as e:
                    logger.error(f"Failed to delete expired cache doc: {e}")
            self.misses += 1
            return None
        
        self.hits += 1
        return doc.metadata.get("response")  # The actual cached LLM response
    
    def store(self, prompt: str, response: str, tier: str, model: str) -> None:
        """Cache a new LLM response."""
        if len(response.strip()) < 20:
            return  # Don't cache garbage/error responses
        
        doc_id = str(uuid.uuid4())
        
        try:
            # We add the PROMPT as the document (so Chroma embeds it for future lookups)
            # and store the RESPONSE in metadata
            with self._lock:
                self._store.add_texts(
                    texts=[prompt],  # Chroma embeds THIS for similarity search
                    metadatas=[{
                        "doc_id": doc_id,
                        "response": response,  # The actual cached answer
                        "tier": tier,
                        "model": model,
                        "cached_at": time.time(),
                        "original_prompt": prompt[:500],
                    }],
                    ids=[doc_id],
                )
        except Exception as e:
            logger.error(f"Failed to store in semantic cache: {e}")

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        if total == 0:
            return 0.0
        return self.hits / total

