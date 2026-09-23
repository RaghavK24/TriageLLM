"""
Load simulator for Adaptive RAG Router.

Fires N concurrent requests at BOTH endpoints (/chat and /chat_baseline)
using the test_250.json dataset. Uses a fixed random seed to deterministically
generate duplicate requests according to --duplicate-ratio.

Measures latency, cost, cache hits, and classifier accuracy, dumping rich
JSON files to results/<endpoint>_<N>.json.
"""
import argparse
import asyncio
import json
import random
import statistics
import time
from pathlib import Path

import httpx
import numpy as np
from tqdm.asyncio import tqdm_asyncio

HERE = Path(__file__).resolve().parent
PROMPTS_FILE = HERE.parent / "training" / "data" / "test_250.json"
RESULTS_DIR = HERE / "results"
RESULTS_DIR.mkdir(exist_ok=True)

# Fixed seed guarantees deterministic duplicates across runs for scientific benchmarking.
RANDOM_SEED = 42

def load_prompts():
    with PROMPTS_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)

def generate_traffic(prompts_data: list, n_concurrent: int, duplicate_ratio: float):
    """
    Generates deterministic traffic.
    Selects unique base prompts, then pads with exact duplicates.
    """
    random.seed(RANDOM_SEED)
    
    n_duplicates = int(n_concurrent * duplicate_ratio)
    n_unique = n_concurrent - n_duplicates
    
    # Pick the unique subset randomly across the whole 250 dataset
    # This guarantees some cache hits (random overlap) but allows massive uncached spikes at high N
    base_pool = random.sample(prompts_data, min(n_unique, len(prompts_data)))
    
    traffic = []
    # Add uniques
    traffic.extend(base_pool)
    
    # Add duplicates (randomly sampled from the base_pool)
    for _ in range(n_concurrent - len(traffic)):
        traffic.append(random.choice(base_pool))
        
    # Shuffle to interleave uniques and duplicates (simulate real traffic)
    random.shuffle(traffic)
    return traffic

async def _one(client: httpx.AsyncClient, url: str, item: dict):
    prompt_str = item["prompt"]
    t0 = time.perf_counter()
    try:
        r = await client.post(url, json={"prompt": prompt_str, "use_rag": True}, timeout=120.0)
        r.raise_for_status()
        body = r.json()
        meta = body.get("metadata", {})
        routing = meta.get("routing", {})
        usage = meta.get("usage", {})
        
        # We need a fallback cost estimator since LiteLLM doesn't always return cost
        cost = usage.get("cost_usd")
        if not cost:
            p_tokens = usage.get("prompt_tokens") or 0
            c_tokens = usage.get("completion_tokens") or 0
            model = routing.get("model_used", "").lower()
            if "gpt-4o" in model:
                cost = (p_tokens * 5.0 / 1e6) + (c_tokens * 15.0 / 1e6)
            elif "qwen" in model or "llama" in model or "gpt-oss" in model:
                cost = (p_tokens * 0.15 / 1e6) + (c_tokens * 0.60 / 1e6)
            else:
                cost = 0.0

        return {
            "ok": True,
            "latency_ms": (time.perf_counter() - t0) * 1000.0,
            
            # Request Tracking
            "prompt": prompt_str,
            "answer": body.get("answer"),
            
            # Ground Truth from JSON
            "expected_tier": item.get("label"),
            "expected_domain": item.get("domain"),
            "expected_rag": item.get("needs_rag"),
            
            # System Metrics
            "tier": routing.get("tier"),
            "model": routing.get("model_used"),
            "domain": meta.get("domain"),
            "needs_rag": meta.get("needs_rag"),
            "cache_hit": meta.get("cache_hit"),
            "coalesced": meta.get("coalesced"),
            
            "cost_usd": cost,
        }
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "latency_ms": (time.perf_counter() - t0) * 1000.0,
        }

async def run_level(base_url: str, endpoint: str, traffic: list, n_concurrent: int):
    url = f"{base_url}{endpoint}"
    
    async with httpx.AsyncClient() as client:
        coros = [_one(client, url, p) for p in traffic]
        results = await tqdm_asyncio.gather(
            *coros, desc=f"{endpoint} N={n_concurrent}"
        )

    ok = [r for r in results if r["ok"]]
    lats = [r["latency_ms"] for r in ok]
    costs = [r["cost_usd"] or 0.0 for r in ok]
    
    tier_counts = {}
    cache_hits = 0
    coalesced_hits = 0
    
    for r in ok:
        tier_counts[r["tier"]] = tier_counts.get(r["tier"], 0) + 1
        if r.get("cache_hit"): cache_hits += 1
        if r.get("coalesced"): coalesced_hits += 1

    summary = {
        "endpoint": endpoint,
        "n_concurrent": n_concurrent,
        "n_ok": len(ok),
        "n_err": len(results) - len(ok),
        "latency_ms": {
            "avg": statistics.mean(lats) if lats else 0.0,
            "p50": statistics.median(lats) if lats else 0.0,
            "p95": float(np.percentile(lats, 95)) if lats else 0.0,
            "max": max(lats) if lats else 0.0,
        },
        "total_cost_usd": sum(costs),
        "avg_cost_usd": (sum(costs) / len(ok)) if ok else 0.0,
        "tier_counts": tier_counts,
        "cache_hits": cache_hits,
        "coalesced_hits": coalesced_hits,
        "raw": results,
    }

    tag = endpoint.strip("/").replace("/", "_") or "root"
    out = RESULTS_DIR / f"{tag}_N{n_concurrent}.json"
    with out.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"[saved] {out}")
    return summary


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8000")
    ap.add_argument("--levels", type=int, nargs="+", default=[5, 15, 30, 50])
    ap.add_argument("--duplicate-ratio", type=float, default=0.2, help="Fraction of requests that are exact duplicates")
    ap.add_argument(
        "--endpoint",
        choices=["both", "chat", "baseline"],
        default="both",
        help="Target endpoint to test: 'chat' (/chat only), 'baseline' (/chat_baseline only), or 'both' (default)"
    )
    args = ap.parse_args()

    prompts_data = load_prompts()

    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(f"{args.url}/health", timeout=10.0)
            r.raise_for_status()
        except Exception as e:
            print(f"[fatal] server not reachable at {args.url}: {e}")
            return

    for n in args.levels:
        traffic = generate_traffic(prompts_data, n, args.duplicate_ratio)
        
        if args.endpoint in ("both", "chat"):
            await run_level(args.url, "/chat", traffic, n)
            await asyncio.sleep(1.0)
        
        if args.endpoint in ("both", "baseline"):
            await run_level(args.url, "/chat_baseline", traffic, n)
            await asyncio.sleep(1.0)

if __name__ == "__main__":
    asyncio.run(main())
