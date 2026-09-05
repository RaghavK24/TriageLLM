"""
Minimal in-process RAG with Chroma.

- On startup, if the persist directory is empty, we ingest every .txt file
  from data/sample_docs/ into a Chroma collection.
- At query time, we do a top-k similarity search and stitch the results
  into a single context string.

This is deliberately tiny — the RAG isn't the interesting part of the
project, the routing is.
"""
from __future__ import annotations
import os
import threading
from pathlib import Path
from typing import List

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from config import settings


_COLLECTION = "adaptive_rag_router"


class RagStore:
    def __init__(self):
        self._lock = threading.Lock()
        self._embeddings = HuggingFaceEmbeddings(model_name=settings.embedding_model)
        self._store = Chroma(
            collection_name=_COLLECTION,
            embedding_function=self._embeddings,
            persist_directory=settings.chroma_persist_dir,
        )

    def is_empty(self) -> bool:
        try:
            return self._store._collection.count() == 0
        except Exception:
            return True

    def ingest_folder(self, folder: str) -> int:
        """Load every .txt file under `folder`, split, embed, store. Returns doc count."""
        p = Path(folder)
        if not p.exists():
            return 0

        raw_docs: List[Document] = []
        for txt in p.rglob("*.txt"):
            content = txt.read_text(encoding="utf-8", errors="ignore")
            raw_docs.append(Document(page_content=content, metadata={"source": str(txt.name)}))

        splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)
        chunks = splitter.split_documents(raw_docs)
        if not chunks:
            return 0

        with self._lock:
            self._store.add_documents(chunks)
        return len(chunks)

    def retrieve(self, query: str, k: int = None) -> str:
        k = k or settings.rag_top_k
        try:
            # Returns list of (Document, distance) tuples.
            # Lower distance = more relevant. We discard anything above the threshold.
            with self._lock:
                results_with_scores = self._store.similarity_search_with_score(query, k=k)
        except Exception:
            return ""
        if not results_with_scores:
            return ""

        # Filter out chunks that are too far away (i.e. irrelevant to the query)
        relevant = [
            (doc, score) for doc, score in results_with_scores
            if score <= settings.rag_distance_threshold
        ]

        if not relevant:
            return ""

        return "\n\n---\n\n".join(
            f"[source: {d.metadata.get('source', 'unknown')}] (dist: {score:.3f})\n{d.page_content}"
            for d, score in relevant
        )


# Module-level singleton — Chroma + embeddings are expensive to construct.
_store: RagStore | None = None


def get_store() -> RagStore:
    global _store
    if _store is None:
        _store = RagStore()
        if _store.is_empty():
            n = _store.ingest_folder(settings.sample_docs_dir)
            print(f"[rag] ingested {n} chunks from {settings.sample_docs_dir}")
    return _store

