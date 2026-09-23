import pytest
from unittest.mock import patch, MagicMock
from app.classifier import score_prompt, ClassificationResult

@patch("app.classifier.load_classifier")
@patch("app.classifier._distilbert_tokenizer")
@patch("app.classifier._distilbert_model")
def test_score_prompt_mocked(mock_model, mock_tokenizer, mock_load):
    import torch

    # Mock tokenizer output
    mock_tokenizer.return_value = {"input_ids": torch.tensor([[1, 2, 3]])}
    
    # Mock model output (MultiHeadRouter returns 3 items)
    # complexity_logits: [0.0] -> sigmoid(0) = 0.5
    # rag_logits: [2.0] -> sigmoid(2.0) = ~0.88 (> 0.5 so True)
    # domain_logits: [10 values, argmax at index 1 -> "coding"]
    
    complexity_logits = torch.tensor([[-0.5]]) # ~0.37
    rag_logits = torch.tensor([[2.0]])         # True
    domain_logits = torch.tensor([[0.0, 5.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]])
    
    mock_model.return_value = (complexity_logits, rag_logits, domain_logits)

    # Need a fake parameters iterator so score_prompt can find the device
    mock_model.parameters.return_value = iter([MagicMock(device=torch.device('cpu'))])

    result = score_prompt("Test prompt")
    
    assert isinstance(result, ClassificationResult)
    assert result.features["classifier_type"] == "multi_head_router"
    assert result.complexity_score < 0.5  # Sigmoid of -0.5 is ~0.377
    assert result.needs_rag is True       # Sigmoid of 2.0 is ~0.88 > 0.5
    assert result.domain == "coding"      # Index 1
