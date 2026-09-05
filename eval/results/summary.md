# Adaptive Router — Eval Summary

## Latency and cost vs concurrency

| N | avg (adapt) | avg (base) | p95 (adapt) | p95 (base) | cost (adapt) | cost (base) | latency Δ | cost Δ |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 5 | 964 ms | 2879 ms | 1170 ms | 3222 ms | $0.0006 | $0.0041 | **-67%** | **-86%** |
| 15 | 1985 ms | 2557 ms | 5627 ms | 5663 ms | $0.0256 | $0.0255 | **-22%** | **--1%** |
| 30 | 2523 ms | 3664 ms | 7655 ms | 9482 ms | $0.0379 | $0.0509 | **-31%** | **-26%** |
| 50 | 2993 ms | 3552 ms | 7342 ms | 7208 ms | $0.0636 | $0.0941 | **-16%** | **-32%** |

## Tier distribution (adaptive)

| N | weak (cheap) | strong (expensive) |
|---:|---:|---:|
| 5 | 5 | 0 |
| 15 | 8 | 7 |
| 30 | 18 | 12 |
| 50 | 37 | 13 |

## Routing accuracy on hand-labeled prompts

**17 / 18 = 94.4%**

| Expected | Got | Prompt |
|---|---|---|
| weak | weak ✅ | Hi, who are you? |
| weak | weak ✅ | What are our support hours? |
| weak | weak ✅ | What is p95 latency? |
| weak | strong ❌ | Summarize the release notes for v3.2.0. |
| weak | weak ✅ | Who do I contact for time off requests? |
| weak | weak ✅ | What is the max meal expense? |
| weak | weak ✅ | Define cold start. |
| weak | weak ✅ | Is 09:00 UTC within support hours? |
| weak | weak ✅ | List the known issues for the Quantum Widget. |
| strong | strong ✅ | Compare the trade-offs between exponential backoff and token-bucket rate limitin… |
| strong | strong ✅ | Design an in-memory concurrency-aware router that decides between two LLM tiers … |
| strong | strong ✅ | Given a Chroma vector store with 1M embeddings and top-k=10 retrieval, analyze h… |
| strong | strong ✅ | Prove that a weighted-round-robin scheduler with weights (w1, w2) is equivalent,… |
| strong | strong ✅ | Refactor the following Python function for readability and to reduce its cycloma… |
| strong | strong ✅ | Explain the difference between BM25 and dense retrieval, when a hybrid approach … |
| strong | strong ✅ | Derive the expected cost savings per 1000 requests for a two-tier router that se… |
| strong | strong ✅ | Explain step by step how to reset my password. |
| weak | weak ✅ | What? |