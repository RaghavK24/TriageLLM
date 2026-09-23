import pytest
from app.prompts import get_system_prompt, DOMAIN_PROMPTS, RAG_PROMPT_ADDENDUM

def test_get_system_prompt_coding_strong():
    prompt = get_system_prompt("coding", "strong", has_rag=False)
    assert prompt == DOMAIN_PROMPTS["coding"]["strong"]

def test_get_system_prompt_general_weak():
    prompt = get_system_prompt("general", "weak", has_rag=False)
    assert prompt == DOMAIN_PROMPTS["general"]["weak"]

def test_get_system_prompt_fallback():
    # A domain that doesn't exist should fall back to general
    prompt = get_system_prompt("unknown_domain", "strong", has_rag=False)
    assert prompt == DOMAIN_PROMPTS["general"]["strong"]

def test_get_system_prompt_with_rag():
    base = DOMAIN_PROMPTS["business"]["weak"]
    prompt = get_system_prompt("business", "weak", has_rag=True)
    assert prompt == base + RAG_PROMPT_ADDENDUM
    assert RAG_PROMPT_ADDENDUM in prompt

