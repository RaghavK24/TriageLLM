import threading
import logging
import pathlib
import chromadb
from langchain_huggingface import HuggingFaceEmbeddings
from config import settings

logger = logging.getLogger(__name__)

class RagStore:
    def __init__(self, persist_dir, embedding_model, top_k, distance_threshold):
        self._top_k = top_k
        self._distance_threshold = distance_threshold
        self._embeddings = HuggingFaceEmbeddings(model_name=embedding_model)
        self._client = chromadb.PersistentClient(path=persist_dir)
        self._collection = self._client.get_or_create_collection(
            name="rag_documents",
            metadata={"hnsw:space": "cosine"}
        )

    def ingest_texts(self, texts: list[str], metadatas: list[dict]) -> int:
        import uuid
        embeddings = self._embeddings.embed_documents(texts)
        ids = [str(uuid.uuid4()) for _ in texts]
        self._collection.add(
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
            ids=ids
        )
        return len(texts)

    def retrieve(self, query: str) -> str:
        qe = self._embeddings.embed_query(query)
        results = self._collection.query(query_embeddings=[qe], n_results=self._top_k)
        
        if not results or not results.get("documents") or not results["documents"][0]:
            return ""
            
        documents = results["documents"][0]
        distances = results.get("distances", [[0.0] * len(documents)])[0]
        
        filtered_docs = []
        for doc, dist in zip(documents, distances):
            if dist <= self._distance_threshold:
                filtered_docs.append(doc)
            else:
                logger.debug(f"Dropped RAG chunk due to distance threshold ({dist:.3f} > {self._distance_threshold})")
                
        if not filtered_docs:
            return ""
            
        return "\n\n---\n\n".join(filtered_docs)

    def count(self) -> int:
        return self._collection.count()


_store: RagStore | None = None
_store_lock: threading.Lock = threading.Lock()

def get_store() -> RagStore:
    global _store
    if _store is not None:
        return _store
    with _store_lock:
        if _store is not None:
            return _store
        _store = RagStore(
            persist_dir=settings.rag_persist_dir,
            embedding_model=settings.embedding_model,
            top_k=settings.rag_top_k,
            distance_threshold=settings.rag_distance_threshold,
        )
    return _store

