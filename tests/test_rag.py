import pytest
from unittest.mock import MagicMock, patch
from app.rag import RagStore

@pytest.fixture
def rag_store():
    with patch('app.rag.chromadb.PersistentClient') as mock_chroma, \
         patch('app.rag.HuggingFaceEmbeddings') as mock_hf_emb:
        
        mock_emb_instance = MagicMock()
        mock_emb_instance.embed_query.return_value = [0.1] * 384
        mock_hf_emb.return_value = mock_emb_instance

        store = RagStore(
            persist_dir="dummy",
            embedding_model="dummy",
            top_k=2,
            distance_threshold=0.6
        )
        return store

def test_retrieve_filters_by_distance(rag_store):
    # chromadb returns a dict with lists of lists
    rag_store._collection.query.return_value = {
        "documents": [["Good relevant context.", "Bad irrelevant context."]],
        "distances": [[0.3, 0.8]]
    }
    
    context = rag_store.retrieve("Test query")
    
    assert "Good relevant context." in context
    assert "Bad irrelevant context." not in context

def test_retrieve_empty_when_all_above_threshold(rag_store):
    rag_store._collection.query.return_value = {
        "documents": [["Bad context 1", "Bad context 2"]],
        "distances": [[0.7, 0.9]]
    }
    
    context = rag_store.retrieve("Test query")
    assert context == ""
