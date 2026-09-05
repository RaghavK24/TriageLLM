import asyncio
import json
import time
from pathlib import Path

from litellm import acompletion
from config import settings

RESULTS_DIR = Path(__file__).resolve().parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)

PROBE_MODELS = [
    settings.strong_model,
    *settings.strong_fallback_models,
    settings.weak_model,
    *settings.weak_fallback_models
]

async def probe_model(model: str) -> dict:
    """Find the max requests per minute before HTTP 429 using an exponential backoff probe."""
    print(f"Probing {model}...")
    safe_rpm = 60 # Assume 60 RPM if no limits hit easily
    
    # Fire requests at increasing concurrency
    for concurrency in [5, 10, 15, 30]:
        print(f"  Testing {concurrency} requests...")
        try:
            tasks = [acompletion(model=model, messages=[{"role": "user", "content": "Hi"}], max_tokens=10) for _ in range(concurrency)]
            await asyncio.gather(*tasks)
            safe_rpm = concurrency * 2 # If we handled X concurrent, X*2 is a safe rough RPM baseline
            await asyncio.sleep(5) # breather
        except Exception as e:
            error_str = str(e).lower()
            if "rate" in error_str or "429" in error_str or "capacity" in error_str:
                print(f"  -> Hit rate limit at concurrency {concurrency}.")
                limit_rpm = concurrency
                # safe_rpm shouldn't go below 5 just to be practical for tests
                return {"safe_rpm": max(5, limit_rpm - 2), "limit_hit_at_rpm": limit_rpm}
            print(f"  -> Unexpected error: {e}")
            break
            
    return {"safe_rpm": safe_rpm, "limit_hit_at_rpm": None}

async def main():
    print(f"Probing {len(PROBE_MODELS)} models for rate limits...")
    results = {}
    for model in PROBE_MODELS:
        results[model] = await probe_model(model)
        
    out = RESULTS_DIR / "rate_limits_measured.json"
    with out.open("w") as f:
        json.dump(results, f, indent=2)
    print(f"Saved limits to {out}")
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    asyncio.run(main())

