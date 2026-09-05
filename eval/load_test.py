"""
Load simulator.

Fires N concurrent requests at BOTH endpoints (/chat and /chat_baseline)
using the labeled prompt set (recycled if N > len(prompts)), measures
latency and cost, and writes results to results/<endpoint>_<N>.json.

Run:
    python -m eval.load_test --levels 5 15 30 50 --url http://localhost:8000

Then plot with:
    python -m eval.plot_results
"""
from __future__ import annotations
import argparse
import asyncio
import json
import os
import statistics
import time
from pathlib import Path

import httpx
from tqdm.asyncio import tqdm_asyncio


HERE = Path(__file__).resolve().parent
PROMPTS_FILE = HERE / "labeled_prompts.json"
RESULTS_DIR = HERE / "results"
RESULTS_DIR.mkdir(exist_ok=True)


def load_prompts():
    with PROMPTS_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)


async def _one(client: httpx.AsyncClient, url: str, prompt: str):
    t0 = time.perf_counter()
    try:
        r = await client.post(url, json={"prompt": prompt, "use_rag": True}, timeout=120.0)
        r.raise_for_status()
        body = r.json()
        return {
            "ok": True,
            "latency_ms": (time.perf_counter() - t0) * 1000.0,
            "server_latency_ms": body.get("latency_ms"),
            "tier": body.get("tier"),
            "model": body.get("model"),
            "cost_usd": body.get("cost_usd", 0.0),
            "complexity": body.get("complexity"),
            "load_fraction": body.get("load_fraction"),
            "prompt_tokens": body.get("prompt_tokens"),
            "completion_tokens": body.get("completion_tokens"),
        }
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "latency_ms": (time.perf_counter() - t0) * 1000.0,
        }


async def run_level(base_url: str, endpoint: str, n_concurrent: int, prompts):
    url = f"{base_url}{endpoint}"
    # Cycle prompts if we need more than the labeled set.
    tasks_prompts = [prompts[i % len(prompts)]["prompt"] for i in range(n_concurrent)]

    async with httpx.AsyncClient() as client:
        coros = [_one(client, url, p) for p in tasks_prompts]
        results = await tqdm_asyncio.gather(
            *coros, desc=f"{endpoint} N={n_concurrent}"
        )

    ok = [r for r in results if r["ok"]]
    lats = [r["latency_ms"] for r in ok]
    costs = [r["cost_usd"] or 0.0 for r in ok]
    tier_counts = {}
    for r in ok:
        tier_counts[r["tier"]] = tier_counts.get(r["tier"], 0) + 1

    summary = {
        "endpoint": endpoint,
        "n_concurrent": n_concurrent,
        "n_ok": len(ok),
        "n_err": len(results) - len(ok),
        "latency_ms": {
            "avg": statistics.mean(lats) if lats else 0.0,
            "p50": statistics.median(lats) if lats else 0.0,
            "p95": (statistics.quantiles(lats, n=20)[18] if len(lats) >= 20
                    else (max(lats) if lats else 0.0)),
            "max": max(lats) if lats else 0.0,
        },
        "total_cost_usd": sum(costs),
        "avg_cost_usd": (sum(costs) / len(ok)) if ok else 0.0,
        "tier_counts": tier_counts,
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
    ap.add_argument("--endpoints", nargs="+", default=["/chat", "/chat_baseline"])
    ap.add_argument("--smart-cooldown", action="store_true", help="Use rate_limits_measured.json to wait between runs")
    args = ap.parse_args()

    prompts = load_prompts()

    # Calculate safe RPM if smart cooldown is enabled
    safe_rpm = None
    if args.smart_cooldown:
        limits_file = RESULTS_DIR / "rate_limits_measured.json"
        if limits_file.exists():
            with limits_file.open("r", encoding="utf-8") as f:
                limits = json.load(f)
                safe_rpm = min(provider["safe_rpm"] for provider in limits.values())
            print(f"[info] Smart cooldown enabled. Safe RPM: {safe_rpm}")
        else:
            print("[warn] --smart-cooldown requested but eval/results/rate_limits_measured.json not found. Ignoring.")

    # Sanity: does the server respond?
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(f"{args.url}/health", timeout=10.0)
            r.raise_for_status()
        except Exception as e:
            print(f"[fatal] server not reachable at {args.url}: {e}")
            return

    for n in args.levels:
        for ep in args.endpoints:
            await run_level(args.url, ep, n, prompts)
            
            # Smart cooldown calculation
            if safe_rpm:
                # Wait based on requests just sent. Minimum 5 seconds.
                wait_sec = int((n / safe_rpm) * 60) + 15
                print(f"[info] Cooldown for {wait_sec}s to respect rate limits...")
                for i in range(wait_sec, 0, -1):
                    print(f"\rCooling down: {i}s remaining...", end="", flush=True)
                    await asyncio.sleep(1.0)
                print("\rCooling down: DONE                  ")
            else:
                await asyncio.sleep(1.0)


if __name__ == "__main__":
    asyncio.run(main())

