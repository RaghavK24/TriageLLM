"""
Prompt complexity classifier — DistilBERT-v3-base (fine-tuned).
"""
from __future__ import annotations
import logging
import threading
from dataclasses import dataclass

from config import settings

logger = logging.getLogger(__name__)

# ---- Public API --------------------------------------------------------

@dataclass
class ClassificationResult:
    complexity_score: float
    needs_rag: bool
    domain: str
    features: dict

import torch
import torch.nn as nn
from transformers import DistilBertModel, AutoTokenizer

DOMAINS = [
    "business", "coding", "creative_writing", "data_analysis", "education",
    "general", "mathematics", "reasoning", "science", "system_design"
]

class MultiHeadRouter(nn.Module):
    def __init__(self, model_name, num_domains, dropout_rate=0.1):
        super().__init__()
        self.distilbert = DistilBertModel.from_pretrained(model_name)
        self.dropout = nn.Dropout(dropout_rate)
        hidden_size = self.distilbert.config.hidden_size
        self.complexity_head = nn.Linear(hidden_size, 1)
        self.rag_head = nn.Linear(hidden_size, 1)
        self.domain_head = nn.Linear(hidden_size, num_domains)

    def forward(self, input_ids, attention_mask):
        outputs = self.distilbert(input_ids=input_ids, attention_mask=attention_mask)
        pooled_output = outputs.last_hidden_state[:, 0]  # CLS token
        pooled_output = self.dropout(pooled_output)
        
        complexity_logits = self.complexity_head(pooled_output)
        rag_logits = self.rag_head(pooled_output)
        domain_logits = self.domain_head(pooled_output)
        
        return complexity_logits, rag_logits, domain_logits

# ---- Model Loading -----------------------------------------------------

_distilbert_model = None
_distilbert_tokenizer = None
_distilbert_available = False
_init_lock = threading.Lock()


def load_classifier() -> None:
    """
    Attempt to load the fine-tuned MultiHeadRouter model. Called safely from the
    FastAPI lifespan hook. Protected by a threading.Lock to prevent TOCTOU
    races if multiple async workers try to warm it up concurrently.
    """
    global _distilbert_model, _distilbert_tokenizer, _distilbert_available
    
    if _distilbert_available:
        return

    with _init_lock:
        if _distilbert_available:
            return

        model_id_or_path = settings.distilbert_model_dir
        
        try:
            import torch
            import os
            from huggingface_hub import hf_hub_download
            
            logger.info(f"Loading MultiHeadRouter classifier from {model_id_or_path}...")
            _distilbert_tokenizer = AutoTokenizer.from_pretrained(model_id_or_path)
            
            # Find the pytorch_model.bin file
            if os.path.exists(f"{model_id_or_path}/pytorch_model.bin"):
                weights_path = f"{model_id_or_path}/pytorch_model.bin"
                logger.info(f"Found local weights at {weights_path}")
            else:
                logger.info("Downloading/locating weights from Hugging Face hub...")
                weights_path = hf_hub_download(repo_id=model_id_or_path, filename="pytorch_model.bin")
            
            # device mapping for the torch.load
            device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
            
            _distilbert_model = MultiHeadRouter(model_id_or_path, num_domains=10)
            _distilbert_model.load_state_dict(torch.load(weights_path, map_location=device, weights_only=True))
            _distilbert_model.to(device)
            _distilbert_model.eval()

            _distilbert_available = True
            logger.info("MultiHeadRouter classifier loaded successfully.")

        except Exception as e:
            logger.error(f"Failed to load MultiHeadRouter model: {e}")
            raise RuntimeError(f"Could not load required MultiHeadRouter model from {model_id_or_path}: {e}")


def score_prompt(prompt: str) -> ClassificationResult:
    """
    Return a classification result containing complexity, rag need, and domain.
    """
    load_classifier()
    
    import torch
    device = next(_distilbert_model.parameters()).device

    inputs = _distilbert_tokenizer(
        prompt,
        return_tensors="pt",
        truncation=True,
        max_length=512,
        padding=True,
    )
    inputs.pop("token_type_ids", None)
    inputs = {k: v.to(device) for k, v in inputs.items()}

    with torch.no_grad():
        complexity_logits, rag_logits, domain_logits = _distilbert_model(**inputs)
        
        complexity_logit = complexity_logits[0, 0].item()
        rag_logit = rag_logits[0, 0].item()
        
        complexity_score = torch.sigmoid(torch.tensor(complexity_logit)).item()
        needs_rag = torch.sigmoid(torch.tensor(rag_logit)).item() > 0.5
        
        domain_idx = torch.argmax(domain_logits, dim=1).item()
        domain = DOMAINS[domain_idx]

    return ClassificationResult(
        complexity_score=complexity_score,
        needs_rag=needs_rag,
        domain=domain,
        features={
            "classifier_type": "multi_head_router",
            "complexity_logit": complexity_logit,
            "rag_logit": rag_logit,
            "domain_logits": domain_logits[0].tolist(),
        },
    )
