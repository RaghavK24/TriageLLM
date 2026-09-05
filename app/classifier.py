"""
Prompt complexity classifier — DistilBERT-v3-base (fine-tuned) with heuristic fallback.

Two modes:
  1. If a fine-tuned DistilBERT model exists at config.distilbert_model_dir, we load
     it and run inference: tokenize → forward pass → softmax → P(strong).
     Inference is ~3-5ms on CPU — well within our latency budget.

  2. If the model is NOT found (e.g., you haven't trained it yet), we fall back
     to the original hand-crafted heuristic so the server still starts.

The public API is unchanged: score_prompt(prompt) → ComplexityResult
Everything downstream (router, main, schemas) works with either mode.
"""
from __future__ import annotations
import logging
import math
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np

from config import settings

logger = logging.getLogger(__name__)

# ---- Public API (same for both modes) -----------------------------------

@dataclass
class ComplexityResult:
    score: float                     # in [0, 1]
    features: dict                   # for logging / debugging


# ---- Mode 1: Fine-tuned DistilBERT ----------------------------------------

_distilbert_model = None
_distilbert_tokenizer = None
_distilbert_available = False


def _try_load_distilbert() -> bool:
    """
    Attempt to load the fine-tuned DistilBERT model. Called once at startup.
    Returns True if the model was loaded successfully, False otherwise.
    """
    global _distilbert_model, _distilbert_tokenizer, _distilbert_available

    model_dir = Path(settings.distilbert_model_dir)
    if not model_dir.exists() or not (model_dir / "config.json").exists():
        logger.warning(
            f"DistilBERT model not found at {model_dir}. "
            f"Falling back to heuristic classifier. "
            f"To use DistilBERT, run: python training/train_distilbert.py"
        )
        return False

    try:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        logger.info(f"Loading DistilBERT classifier from {model_dir}...")
        _distilbert_tokenizer = AutoTokenizer.from_pretrained(str(model_dir))
        _distilbert_model = AutoModelForSequenceClassification.from_pretrained(str(model_dir))
        _distilbert_model.eval()  # inference mode — no dropout

        # Verify it's a 2-class model
        if _distilbert_model.config.num_labels != 2:
            logger.error(f"Expected 2-class model, got {_distilbert_model.config.num_labels}")
            return False

        _distilbert_available = True
        logger.info("DistilBERT classifier loaded successfully.")
        return True

    except Exception as e:
        logger.error(f"Failed to load DistilBERT model: {e}")
        return False


def _score_distilbert(prompt: str) -> ComplexityResult:
    """Score a prompt using the fine-tuned DistilBERT model."""
    import torch

    inputs = _distilbert_tokenizer(
        prompt,
        return_tensors="pt",
        truncation=True,
        max_length=512,
        padding=True,
    )
    inputs.pop("token_type_ids", None)

    with torch.no_grad():
        outputs = _distilbert_model(**inputs)
        logits = outputs.logits[0]  # shape: (2,)
        probs = torch.softmax(logits, dim=0)

    # label 0 = weak, label 1 = strong
    score_strong = float(probs[1])

    return ComplexityResult(
        score=score_strong,
        features={
            "classifier_type": "distilbert",
            "prob_weak": float(probs[0]),
            "prob_strong": float(probs[1]),
            "logit_weak": float(logits[0]),
            "logit_strong": float(logits[1]),
        },
    )


# ---- Mode 2: Heuristic fallback (original classifier) ------------------

_QUESTION_WORDS = {"what", "why", "how", "when", "where", "which", "who", "whom"}
_COMPLEX_VERBS = {
    "explain", "compare", "contrast", "derive", "prove", "analyze",
    "design", "architect", "optimize", "debug", "refactor", "critique",
    "summarize", "synthesize", "evaluate", "trade-off", "tradeoff",
}
_MATH_TOKENS = re.compile(r"[=+\-*/^<>]|\\frac|\\sum|\\int|integral|derivative")
_CODE_FENCE = re.compile(r"```")


def _handcrafted(prompt: str) -> np.ndarray:
    """
    Six normalized features on [0, 1]. Each maps to a real signal a human
    would use when asked "is this a hard prompt?".
    """
    words = prompt.split()
    n_words = len(words)

    # 1. Length. Long prompts are usually structured requests, not chit-chat.
    f_length = min(n_words / 200.0, 1.0)

    # 2. Question-word count. More question words → deeper ask.
    q_count = sum(1 for w in words if w.lower().strip("?,.") in _QUESTION_WORDS)
    f_questions = min(q_count / 4.0, 1.0)

    # 3. Complex-verb hits. "compare", "derive", "design", etc.
    lower = prompt.lower()
    verb_hits = sum(1 for v in _COMPLEX_VERBS if v in lower)
    f_verbs = min(verb_hits / 3.0, 1.0)

    # 4. Math / formula tokens.
    math_hits = len(_MATH_TOKENS.findall(prompt))
    f_math = min(math_hits / 5.0, 1.0)

    # 5. Code fences (```). Code = usually strong-model territory.
    code_hits = len(_CODE_FENCE.findall(prompt))
    f_code = 1.0 if code_hits >= 2 else 0.0

    # 6. Multi-part signals: "and also", "step by step", enumerated lists.
    multipart = int(
        "step by step" in lower
        or "and also" in lower
        or bool(re.search(r"\n\s*(\d+\.|-|\*)\s+", prompt))
    )
    f_multipart = float(multipart)

    return np.array([f_length, f_questions, f_verbs, f_math, f_code, f_multipart],
                    dtype=np.float32)


# Weights chosen by inspection: length and verbs matter most, then math/code.
_HANDCRAFTED_WEIGHTS = np.array([1.6, 1.2, 1.8, 1.5, 2.0, 1.0], dtype=np.float32)
_HANDCRAFTED_BIAS = -2.2  # sigmoid(-2.2) ≈ 0.10 for an all-zeros prompt like "hi"


@lru_cache(maxsize=1)
def _embedder():
    from langchain_huggingface import HuggingFaceEmbeddings
    return HuggingFaceEmbeddings(model_name=settings.embedding_model)


_rng = np.random.default_rng(seed=42)
_EMB_PROJ = _rng.normal(0.0, 1.0 / math.sqrt(384), size=(384,)).astype(np.float32)
_EMB_WEIGHT = 0.8


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def _score_heuristic(prompt: str) -> ComplexityResult:
    """Original hand-crafted heuristic classifier (fallback)."""
    handcrafted = _handcrafted(prompt)
    logit_hand = float(np.dot(handcrafted, _HANDCRAFTED_WEIGHTS)) + _HANDCRAFTED_BIAS

    emb = np.array(_embedder().embed_query(prompt), dtype=np.float32)
    emb = emb - emb.mean()
    logit_emb = float(np.dot(emb, _EMB_PROJ))

    total_logit = logit_hand + _EMB_WEIGHT * logit_emb
    score = _sigmoid(total_logit)

    return ComplexityResult(
        score=score,
        features={
            "classifier_type": "heuristic_fallback",
            "length": float(handcrafted[0]),
            "questions": float(handcrafted[1]),
            "verbs": float(handcrafted[2]),
            "math": float(handcrafted[3]),
            "code": float(handcrafted[4]),
            "multipart": float(handcrafted[5]),
            "logit_hand": logit_hand,
            "logit_emb": logit_emb,
        },
    )


# ---- Initialization (runs once on first import) -------------------------

# Try to load DistilBERT on module import. If it fails, _distilbert_available stays False
# and we silently use the heuristic. This means the server always starts.
_try_load_distilbert()


# ---- Public API --------------------------------------------------------

def score_prompt(prompt: str) -> ComplexityResult:
    """
    Return a complexity score in [0, 1]. Higher = more likely to need the
    strong model.

    Uses the fine-tuned DistilBERT model if available, otherwise falls back
    to the hand-crafted heuristic. Both produce the same ComplexityResult
    type, so downstream code (router, main) doesn't need to know which
    mode is active. Check result.features["classifier_type"] to see.
    """
    if _distilbert_available:
        return _score_distilbert(prompt)
    return _score_heuristic(prompt)
