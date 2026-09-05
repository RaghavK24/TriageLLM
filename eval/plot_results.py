"""
Reads eval/results/*.json, produces:

  - eval/results/latency_comparison.png
  - eval/results/cost_comparison.png
  - eval/results/tier_distribution.png
  - eval/results/routing_accuracy.png
  - eval/results/summary.md   (markdown table + percentages)

Run:
    python -m eval.plot_results
"""
from __future__ import annotations
import json
import re
from pathlib import Path
from typing import Dict, List

import httpx
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
RESULTS_DIR = HERE / "results"
PROMPTS_FILE = HERE / "labeled_prompts.json"


# ---- Load result JSONs -------------------------------------------------

def load_summaries() -> Dict[str, Dict[int, dict]]:
    """Returns {endpoint: {N: summary}} for both /chat and /chat_baseline."""
    out: Dict[str, Dict[int, dict]] = {"chat": {}, "chat_baseline": {}}
    for p in RESULTS_DIR.glob("*.json"):
        m = re.match(r"(chat|chat_baseline)_N(\d+)\.json", p.name)
        if not m:
            continue
        ep, n = m.group(1), int(m.group(2))
        with p.open("r", encoding="utf-8") as f:
            out[ep][n] = json.load(f)
    return out


def _pct_drop(new: float, base: float) -> float:
    if base <= 0:
        return 0.0
    return (base - new) / base * 100.0


# ---- Charts -----------------------------------------------------------

def plot_latency(summaries):
    levels = sorted(set(summaries["chat"].keys()) & set(summaries["chat_baseline"].keys()))
    fig, ax = plt.subplots(figsize=(9, 5))

    for metric, marker in [("avg", "o"), ("p50", "s"), ("p95", "^")]:
        adaptive = [summaries["chat"][n]["latency_ms"][metric] for n in levels]
        baseline = [summaries["chat_baseline"][n]["latency_ms"][metric] for n in levels]
        ax.plot(levels, adaptive, marker=marker, label=f"adaptive {metric}")
        ax.plot(levels, baseline, marker=marker, linestyle="--", label=f"baseline {metric}")

    ax.set_xlabel("Concurrent users")
    ax.set_ylabel("Latency (ms)")
    ax.set_title("Latency vs concurrency: adaptive router vs always-strong baseline")
    ax.grid(True, alpha=0.3)
    ax.legend()
    out = RESULTS_DIR / "latency_comparison.png"
    fig.tight_layout()
    fig.savefig(out, dpi=140)
    plt.close(fig)
    print(f"[saved] {out}")


def plot_cost(summaries):
    levels = sorted(set(summaries["chat"].keys()) & set(summaries["chat_baseline"].keys()))
    fig, ax = plt.subplots(figsize=(9, 5))

    x = range(len(levels))
    width = 0.35
    adaptive = [summaries["chat"][n]["total_cost_usd"] for n in levels]
    baseline = [summaries["chat_baseline"][n]["total_cost_usd"] for n in levels]
    ax.bar([i - width / 2 for i in x], adaptive, width, label="adaptive")
    ax.bar([i + width / 2 for i in x], baseline, width, label="baseline (always strong)")

    ax.set_xticks(list(x))
    ax.set_xticklabels([str(n) for n in levels])
    ax.set_xlabel("Concurrent users")
    ax.set_ylabel("Total USD cost for the batch")
    ax.set_title("Cost vs concurrency")
    ax.legend()
    ax.grid(True, alpha=0.3, axis="y")

    for i, (a, b) in enumerate(zip(adaptive, baseline)):
        drop = _pct_drop(a, b)
        ax.text(i, max(a, b) * 1.02, f"-{drop:.0f}%", ha="center", fontsize=9)

    out = RESULTS_DIR / "cost_comparison.png"
    fig.tight_layout()
    fig.savefig(out, dpi=140)
    plt.close(fig)
    print(f"[saved] {out}")


def plot_tier_distribution(summaries):
    levels = sorted(summaries["chat"].keys())
    fig, ax = plt.subplots(figsize=(9, 5))

    weak = [summaries["chat"][n]["tier_counts"].get("weak", 0) for n in levels]
    strong = [summaries["chat"][n]["tier_counts"].get("strong", 0) for n in levels]

    x = range(len(levels))
    ax.bar(x, weak, label="weak (cheap)")
    ax.bar(x, strong, bottom=weak, label="strong (expensive)")
    ax.set_xticks(list(x))
    ax.set_xticklabels([str(n) for n in levels])
    ax.set_xlabel("Concurrent users")
    ax.set_ylabel("Requests routed")
    ax.set_title("Adaptive router — tier distribution vs load")
    ax.legend()
    ax.grid(True, alpha=0.3, axis="y")

    out = RESULTS_DIR / "tier_distribution.png"
    fig.tight_layout()
    fig.savefig(out, dpi=140)
    plt.close(fig)
    print(f"[saved] {out}")


# ---- Routing accuracy on hand-labeled prompts ------------------------

def measure_routing_accuracy(base_url: str = "http://localhost:8000") -> dict:
    """
    Evaluates each labeled prompt locally without needing the server running.
    """
    import sys
    sys.path.insert(0, str(HERE.parent))
    from app.classifier import score_prompt
    from config import settings

    with PROMPTS_FILE.open("r", encoding="utf-8") as f:
        prompts = json.load(f)

    correct = 0
    rows = []
    for item in prompts:
        try:
            res = score_prompt(item["prompt"])
            got = "strong" if res.score >= settings.complexity_threshold else "weak"
        except Exception as e:
            got = f"ERROR: {e}"
        ok = got == item["expected_tier"]
        correct += int(ok)
        rows.append({
            "prompt": item["prompt"][:80] + ("…" if len(item["prompt"]) > 80 else ""),
            "expected": item["expected_tier"],
            "got": got,
            "ok": ok,
        })

    acc = correct / len(prompts) if prompts else 0.0
    return {"accuracy": acc, "correct": correct, "total": len(prompts), "rows": rows}


def plot_routing_accuracy(acc: dict):
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(["correct", "incorrect"], [acc["correct"], acc["total"] - acc["correct"]])
    ax.set_title(
        f"Routing accuracy on hand-labeled set: "
        f"{acc['correct']}/{acc['total']} = {acc['accuracy']*100:.1f}%"
    )
    ax.grid(True, alpha=0.3, axis="y")
    out = RESULTS_DIR / "routing_accuracy.png"
    fig.tight_layout()
    fig.savefig(out, dpi=140)
    plt.close(fig)
    print(f"[saved] {out}")


# ---- Markdown summary ------------------------------------------------

def write_markdown_summary(summaries, acc):
    levels = sorted(set(summaries["chat"].keys()) & set(summaries["chat_baseline"].keys()))
    lines: List[str] = []
    lines.append("# Adaptive Router — Eval Summary\n")
    lines.append("## Latency and cost vs concurrency\n")
    lines.append("| N | avg (adapt) | avg (base) | p95 (adapt) | p95 (base) | "
                 "cost (adapt) | cost (base) | latency Δ | cost Δ |")
    lines.append("|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for n in levels:
        a = summaries["chat"][n]
        b = summaries["chat_baseline"][n]
        lat_delta = _pct_drop(a["latency_ms"]["avg"], b["latency_ms"]["avg"])
        cost_delta = _pct_drop(a["total_cost_usd"], b["total_cost_usd"])
        lines.append(
            f"| {n} "
            f"| {a['latency_ms']['avg']:.0f} ms | {b['latency_ms']['avg']:.0f} ms "
            f"| {a['latency_ms']['p95']:.0f} ms | {b['latency_ms']['p95']:.0f} ms "
            f"| ${a['total_cost_usd']:.4f} | ${b['total_cost_usd']:.4f} "
            f"| **-{lat_delta:.0f}%** | **-{cost_delta:.0f}%** |"
        )

    lines.append("\n## Tier distribution (adaptive)\n")
    lines.append("| N | weak (cheap) | strong (expensive) |")
    lines.append("|---:|---:|---:|")
    for n in levels:
        tc = summaries["chat"][n]["tier_counts"]
        lines.append(f"| {n} | {tc.get('weak', 0)} | {tc.get('strong', 0)} |")

    lines.append("\n## Routing accuracy on hand-labeled prompts\n")
    lines.append(
        f"**{acc['correct']} / {acc['total']} = {acc['accuracy']*100:.1f}%**\n"
    )
    lines.append("| Expected | Got | Prompt |")
    lines.append("|---|---|---|")
    for r in acc["rows"]:
        mark = "✅" if r["ok"] else "❌"
        lines.append(f"| {r['expected']} | {r['got']} {mark} | {r['prompt']} |")

    out = RESULTS_DIR / "summary.md"
    with out.open("w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"[saved] {out}")


# ---- Entrypoint -------------------------------------------------------

def main():
    summaries = load_summaries()
    if not summaries["chat"] or not summaries["chat_baseline"]:
        print("[warn] no result files yet — run `python -m eval.load_test` first.")
        return
    plot_latency(summaries)
    plot_cost(summaries)
    plot_tier_distribution(summaries)

    print("[info] measuring routing accuracy on labeled prompts (one at a time)…")
    acc = measure_routing_accuracy()
    plot_routing_accuracy(acc)

    write_markdown_summary(summaries, acc)
    print("\nDone. Open eval/results/summary.md and the .png files.")


if __name__ == "__main__":
    main()

