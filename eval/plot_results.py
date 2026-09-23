"""
Generates beautiful charts and a Markdown summary from the JSON results
produced by `eval/load_test.py`.
"""
import json
import re
from pathlib import Path
from typing import Dict, List

import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
RESULTS_DIR = HERE / "results"

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
    if not levels: return
    fig, ax = plt.subplots(figsize=(9, 5))

    for metric, marker in [("avg", "o"), ("p95", "^")]:
        adaptive = [summaries["chat"][n]["latency_ms"][metric] for n in levels]
        baseline = [summaries["chat_baseline"][n]["latency_ms"][metric] for n in levels]
        ax.plot(levels, adaptive, marker=marker, label=f"Adaptive {metric}")
        ax.plot(levels, baseline, marker=marker, linestyle="--", label=f"Baseline {metric}")

    ax.set_xlabel("Concurrent users")
    ax.set_ylabel("Latency (ms)")
    ax.set_title("Latency vs Concurrency: Adaptive Router vs Baseline")
    ax.grid(True, alpha=0.3)
    ax.legend()
    out = RESULTS_DIR / "latency_comparison.png"
    fig.tight_layout()
    fig.savefig(out, dpi=140)
    plt.close(fig)
    print(f"[saved] {out}")


def plot_cost(summaries):
    levels = sorted(set(summaries["chat"].keys()) & set(summaries["chat_baseline"].keys()))
    if not levels: return
    fig, ax = plt.subplots(figsize=(9, 5))

    x = range(len(levels))
    width = 0.35
    adaptive = [summaries["chat"][n]["total_cost_usd"] for n in levels]
    baseline = [summaries["chat_baseline"][n]["total_cost_usd"] for n in levels]
    
    ax.bar([i - width / 2 for i in x], adaptive, width, label="Adaptive Router")
    ax.bar([i + width / 2 for i in x], baseline, width, label="Baseline (Always Azure)")

    ax.set_xticks(list(x))
    ax.set_xticklabels([str(n) for n in levels])
    ax.set_xlabel("Concurrent users")
    ax.set_ylabel("Total USD Cost for the Batch")
    ax.set_title("Cost vs Concurrency")
    ax.legend()
    ax.grid(True, alpha=0.3, axis="y")

    for i, (a, b) in enumerate(zip(adaptive, baseline)):
        drop = _pct_drop(a, b)
        if drop > 0:
            ax.text(i - width / 2, a + (max(a, b)*0.02), f"-{drop:.0f}%", ha="center", fontsize=9, fontweight='bold', color='green')

    out = RESULTS_DIR / "cost_comparison.png"
    fig.tight_layout()
    fig.savefig(out, dpi=140)
    plt.close(fig)
    print(f"[saved] {out}")


def plot_feature_accuracy(summaries):
    """Calculates and plots the accuracy of the DistilBERT classifier across the 3 dimensions."""
    levels = sorted(summaries["chat"].keys())
    if not levels: return
    
    # We just need to analyze the raw requests from the largest run
    max_n = levels[-1]
    raw_results = summaries["chat"][max_n]["raw"]
    
    tier_correct = 0
    domain_correct = 0
    rag_correct = 0
    total = 0
    
    for r in raw_results:
        if not r.get("ok"): continue
        # Only evaluate non-coalesced requests (coalesced requests don't hit the classifier directly in the same way, but it's fine)
        if r.get("coalesced"): continue
        
        if r.get("tier") == r.get("expected_tier"): tier_correct += 1
        if r.get("domain") == r.get("expected_domain"): domain_correct += 1
        if r.get("needs_rag") == r.get("expected_rag"): rag_correct += 1
        total += 1
        
    if total == 0: return

    acc = {
        "Tier Routing": tier_correct / total * 100,
        "Domain Detection": domain_correct / total * 100,
        "RAG Skipping": rag_correct / total * 100,
    }
    
    fig, ax = plt.subplots(figsize=(7, 4))
    bars = ax.bar(acc.keys(), acc.values(), color=['#4C72B0', '#55A868', '#C44E52'])
    ax.set_ylim(0, 110)
    ax.set_ylabel("Accuracy (%)")
    ax.set_title("DistilBERT Classifier Multi-Axis Accuracy")
    
    for bar in bars:
        yval = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2, yval + 2, f"{yval:.1f}%", ha='center', va='bottom', fontweight='bold')
        
    ax.grid(True, alpha=0.3, axis="y")
    out = RESULTS_DIR / "feature_accuracy.png"
    fig.tight_layout()
    fig.savefig(out, dpi=140)
    plt.close(fig)
    print(f"[saved] {out}")
    
    return acc, total


# ---- Markdown summary ------------------------------------------------

def write_markdown_summary(summaries, accuracy_data):
    levels = sorted(set(summaries["chat"].keys()) & set(summaries["chat_baseline"].keys()))
    if not levels: return
    
    lines: List[str] = []
    lines.append("# Adaptive RAG Router — Evaluation Report\n")
    lines.append("## 💰 Financial & Latency Savings\n")
    lines.append("| Concurrency | Avg Latency (Router) | Avg Latency (Baseline) | Latency Drop | Cost (Router) | Cost (Baseline) | Cost Savings |")
    lines.append("|---:|---:|---:|---:|---:|---:|---:|")
    for n in levels:
        a = summaries["chat"][n]
        b = summaries["chat_baseline"][n]
        lat_delta = _pct_drop(a["latency_ms"]["avg"], b["latency_ms"]["avg"])
        cost_delta = _pct_drop(a["total_cost_usd"], b["total_cost_usd"])
        lines.append(
            f"| **{n}** "
            f"| {a['latency_ms']['avg']:.0f} ms | {b['latency_ms']['avg']:.0f} ms "
            f"| **-{lat_delta:.0f}%** "
            f"| ${a['total_cost_usd']:.4f} | ${b['total_cost_usd']:.4f} "
            f"| **-{cost_delta:.0f}%** |"
        )

    lines.append("\n## ⚡ Cache & Coalescer Hits\n")
    lines.append("| Concurrency | Total Requests | Cache Hits (DB) | Coalesced (RAM) | LLM Calls Saved |")
    lines.append("|---:|---:|---:|---:|---:|")
    for n in levels:
        a = summaries["chat"][n]
        hits = a.get('cache_hits', 0)
        coals = a.get('coalesced_hits', 0)
        saved = hits + coals
        pct = (saved / a['n_ok'] * 100) if a['n_ok'] > 0 else 0
        lines.append(f"| **{n}** | {a['n_ok']} | {hits} | {coals} | **{saved} ({pct:.0f}%)** |")

    lines.append("\n## 🎯 DistilBERT Multi-Axis Accuracy\n")
    if accuracy_data:
        acc, total = accuracy_data
        lines.append(f"*Evaluated on {total} unique requests from test_250.json*\n")
        for k, v in acc.items():
            lines.append(f"- **{k}**: {v:.1f}%")

    out = RESULTS_DIR / "summary.md"
    with out.open("w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"[saved] {out}")


# ---- Entrypoint -------------------------------------------------------

def main():
    summaries = load_summaries()
    if not summaries.get("chat") or not summaries.get("chat_baseline"):
        print("[warn] No complete result files found — run `python eval/load_test.py` first.")
        return
        
    plot_latency(summaries)
    plot_cost(summaries)
    
    acc_data = plot_feature_accuracy(summaries)
    write_markdown_summary(summaries, acc_data)
    
    print("\n✅ Done! Open eval/results/summary.md and the .png files.")


if __name__ == "__main__":
    main()
