# Adaptive RAG Router — Evaluation Report

## 💰 Financial & Latency Savings

| Concurrency | Avg Latency (Router) | Avg Latency (Baseline) | Latency Drop | Cost (Router) | Cost (Baseline) | Cost Savings |
|---:|---:|---:|---:|---:|---:|---:|
| **10** | 7143 ms | 14685 ms | **-51%** | $0.0326 | $0.0778 | **-58%** |
| **30** | 7669 ms | 19683 ms | **-61%** | $0.1223 | $0.2924 | **-58%** |
| **60** | 13201 ms | 28259 ms | **-53%** | $0.1477 | $0.8669 | **-83%** |
| **80** | 2782 ms | 27375 ms | **-90%** | $0.0325 | $1.0484 | **-97%** |

## ⚡ Cache & Coalescer Hits

| Concurrency | Total Requests | Cache Hits (DB) | Coalesced (RAM) | LLM Calls Saved |
|---:|---:|---:|---:|---:|
| **10** | 10 | 0 | 3 | **3 (30%)** |
| **30** | 30 | 9 | 7 | **16 (53%)** |
| **60** | 60 | 29 | 9 | **38 (63%)** |
| **80** | 80 | 58 | 7 | **65 (81%)** |

## 🎯 DistilBERT Multi-Axis Accuracy

*Evaluated on 73 unique requests from test_250.json*

- **Tier Routing**: 69.9%
- **Domain Detection**: 83.6%
- **RAG Skipping**: 79.5%