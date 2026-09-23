import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, AsyncMock, MagicMock
from app.main import app
from app.classifier import ClassificationResult

def make_mock_llm_response(text="Mock response", model="test/model"):
    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(content=text))]
    response.usage = MagicMock(prompt_tokens=10, completion_tokens=5)
    response.text = text
    response.model = model
    response.cost_usd = 0.001
    return response

@pytest.fixture
def mock_classification_normal():
    return ClassificationResult(
        complexity_score=0.5,
        needs_rag=True,
        domain="general",
        features={}
    )

@pytest.fixture
def mock_classification_strong():
    return ClassificationResult(
        complexity_score=1.0,
        needs_rag=True,
        domain="coding",
        features={}
    )

@pytest.fixture
def mock_classification_no_rag():
    return ClassificationResult(
        complexity_score=0.3,
        needs_rag=False,
        domain="business",
        features={}
    )

@pytest.mark.asyncio
async def test_chat_endpoint_returns_200(mock_classification_normal):
    mock_llm_result = MagicMock()
    mock_llm_result.text = "This is a mocked answer."
    mock_llm_result.model = "test-model"
    mock_llm_result.prompt_tokens = 10
    mock_llm_result.completion_tokens = 20
    mock_llm_result.cost_usd = 0.001

    with patch("app.main.call_model", new_callable=AsyncMock, return_value=mock_llm_result), \
         patch("app.main.score_prompt", return_value=mock_classification_normal):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post("/chat", json={"prompt": "Hello"})
    
    assert resp.status_code == 200
    data = resp.json()
    assert data["answer"] == "This is a mocked answer."
    assert "routing" in data["metadata"]
    assert "cache_hit" in data["metadata"]
    assert data["metadata"]["cache_hit"] is False

@pytest.mark.asyncio
async def test_chat_endpoint_load_shedding(mock_settings, mock_classification_strong):
    from app.main import tracker
    tracker._in_flight = 45 

    with patch("app.main.score_prompt", return_value=mock_classification_strong), \
         patch("app.main.get_store", return_value=MagicMock()):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post("/chat", json={"prompt": "Explain quantum physics"})
    
    assert resp.status_code == 429
    tracker._in_flight = 0

@pytest.mark.asyncio
async def test_chat_skips_rag_if_needs_rag_false(mock_classification_no_rag):
    mock_llm_result = MagicMock()
    mock_llm_result.text = "Mocked answer without RAG."

    with patch("app.main.call_model", new_callable=AsyncMock, return_value=mock_llm_result), \
         patch("app.main.score_prompt", return_value=mock_classification_no_rag), \
         patch("app.main.get_store") as mock_get_store:
        
        # We need the retrieve method to be accessible
        mock_store = MagicMock()
        mock_get_store.return_value = mock_store

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post("/chat", json={"prompt": "Short question"})
            
    assert resp.status_code == 200
    # Assert that retrieve was never called because needs_rag is False
    mock_store.retrieve.assert_not_called()
    data = resp.json()
    assert data["metadata"]["needs_rag"] is False
    assert data["metadata"]["rag_context_chars"] == 0
