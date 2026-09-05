"""
Merge batch label results from Gemini Pro into a single training dataset.

Usage:
    python training/merge_labels.py

Reads:   training/batches/batch_*_results.json
Writes:  training/data/labeled_dataset.json

Also incorporates the hand-labeled prompts from eval/labeled_prompts.json
as additional training data.
"""
from __future__ import annotations
import json
import re
from pathlib import Path


HERE = Path(__file__).resolve().parent
BATCHES_DIR = HERE / "batches"
EVAL_PROMPTS = HERE.parent / "eval" / "labeled_prompts.json"
OUTPUT_DIR = HERE / "data"
OUTPUT_FILE = OUTPUT_DIR / "labeled_dataset.json"


def clean_json_text(text: str) -> str:
    """
    Strip markdown code fences and leading/trailing whitespace from
    Gemini Pro's output. Sometimes it wraps JSON in ```json ... ```.
    """
    text = text.strip()
    # Remove ```json ... ``` wrapper if present
    text = re.sub(r"^```(?:json)?\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


def load_batch_files() -> list[dict]:
    """Load all batch_*_results.json files and merge into one list."""
    all_items = []
    if not BATCHES_DIR.exists():
        print(f"[warn] batches directory not found: {BATCHES_DIR}")
        return all_items

    batch_files = sorted(BATCHES_DIR.glob("batch_*_results.json"))
    if not batch_files:
        print(f"[warn] no batch result files found in {BATCHES_DIR}")
        print("       Expected files like: batch_01_results.json, batch_02_results.json, ...")
        return all_items

    for bf in batch_files:
        print(f"[load] {bf.name}")
        try:
            raw = bf.read_text(encoding="utf-8")
            raw = clean_json_text(raw)
            items = json.loads(raw)
            if not isinstance(items, list):
                print(f"  [warn] expected a JSON array, got {type(items).__name__} — skipping")
                continue
            for item in items:
                # Normalize: ensure we have "prompt" and "label" keys
                prompt = item.get("prompt", "").strip()
                label = item.get("label", "").strip().lower()
                if not prompt or label not in ("weak", "strong"):
                    print(f"  [skip] invalid item: {item}")
                    continue
                all_items.append({
                    "prompt": prompt,
                    "label": label,
                    "reasoning": item.get("reasoning", ""),
                    "source": bf.name,
                })
            print(f"  → {len(items)} items loaded")
        except json.JSONDecodeError as e:
            print(f"  [error] invalid JSON in {bf.name}: {e}")
        except Exception as e:
            print(f"  [error] reading {bf.name}: {e}")

    return all_items


def load_eval_prompts() -> list[dict]:
    """Load the hand-labeled prompts from eval/labeled_prompts.json."""
    if not EVAL_PROMPTS.exists():
        print(f"[info] eval prompts not found: {EVAL_PROMPTS}")
        return []

    with EVAL_PROMPTS.open("r", encoding="utf-8") as f:
        items = json.load(f)

    result = []
    for item in items:
        prompt = item.get("prompt", "").strip()
        label = item.get("expected_tier", "").strip().lower()
        if prompt and label in ("weak", "strong"):
            result.append({
                "prompt": prompt,
                "label": label,
                "reasoning": "hand-labeled in eval set",
                "source": "eval/labeled_prompts.json",
            })
    print(f"[load] {len(result)} items from eval/labeled_prompts.json")
    return result


def deduplicate(items: list[dict]) -> list[dict]:
    """Remove duplicate prompts, keeping the first occurrence."""
    seen = set()
    deduped = []
    for item in items:
        key = item["prompt"].strip().lower()
        if key not in seen:
            seen.add(key)
            deduped.append(item)
    return deduped


def main():
    batch_items = load_batch_files()
    eval_items = load_eval_prompts()

    all_items = batch_items + eval_items
    all_items = deduplicate(all_items)

    # Stats
    weak_count = sum(1 for i in all_items if i["label"] == "weak")
    strong_count = sum(1 for i in all_items if i["label"] == "strong")

    print(f"\n[summary]")
    print(f"  Total unique prompts: {len(all_items)}")
    print(f"  Weak:   {weak_count}")
    print(f"  Strong: {strong_count}")
    print(f"  Balance: {weak_count/(len(all_items) or 1)*100:.1f}% weak / "
          f"{strong_count/(len(all_items) or 1)*100:.1f}% strong")

    if len(all_items) < 50:
        print("\n[warn] Less than 50 examples. DeBERTa will likely underfit.")
        print("       Consider labeling more batches for better results.")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        json.dump(all_items, f, indent=2, ensure_ascii=False)
    print(f"\n[saved] {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
