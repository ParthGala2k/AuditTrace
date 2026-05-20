"""
Multi-Model Evaluation Runner
------------------------------
Benchmarks the Planner Agent's requirement extraction across 3 LLMs:
  - openai/gpt-4o
  - anthropic/claude-3.5-sonnet
  - meta-llama/llama-3.1-70b-instruct

Metrics per model:
  - severity_accuracy      : exact match on severity field
  - requirement_type_acc   : exact match on requirement_type
  - check_targets_f1       : token-level F1 on check_targets list
  - avg_latency_s          : mean seconds per call
  - total_cost_usd         : estimated cost (from token counts × price table)

Usage:
    cd backend
    python ../evaluation/run_eval.py
"""

import sys, os, json, time
from dotenv import load_dotenv

# Load .env from the backend directory
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), "backend", ".env"))

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)) + "/backend")

from agents.planner import PlannerAgent

# Approximate cost per 1 000 tokens (input + output) in USD
COST_PER_1K = {
    "openai/gpt-4o-mini":                  0.000375,
    "deepseek/deepseek-chat":              0.00027,
    "meta-llama/llama-3.1-70b-instruct":  0.0009,
}

MODELS = list(COST_PER_1K.keys())

TEST_CASES_PATH = os.path.join(os.path.dirname(__file__), "test_cases.json")
RESULTS_DIR = os.path.dirname(__file__)


def load_test_cases():
    with open(TEST_CASES_PATH) as f:
        return json.load(f)


def targets_f1(predicted: list, expected: list) -> float:
    """Compute token-level F1 between two lists of check_target strings."""
    pred_set = {t.lower() for t in predicted}
    exp_set  = {t.lower() for t in expected}
    if not exp_set and not pred_set:
        return 1.0
    if not pred_set or not exp_set:
        return 0.0
    tp = len(pred_set & exp_set)
    precision = tp / len(pred_set)
    recall    = tp / len(exp_set)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def evaluate_model(model: str, test_cases: list) -> dict:
    print(f"\n{'='*60}")
    print(f"Evaluating: {model}")
    print(f"{'='*60}")

    planner = PlannerAgent(model=model)

    severity_hits = 0
    req_type_hits = 0
    f1_scores = []
    latencies = []
    total_tokens = 0

    per_case_results = []

    for tc in test_cases:
        tc_id = tc["id"]
        text  = tc["input"]
        exp   = tc["expected"]

        t0 = time.time()
        try:
            reqs = planner.decompose(text)
        except Exception as e:
            print(f"  [{tc_id}] ERROR: {e}")
            per_case_results.append({"id": tc_id, "error": str(e)})
            continue
        latency = time.time() - t0
        latencies.append(latency)

        if not reqs:
            print(f"  [{tc_id}] WARNING: no requirements extracted")
            per_case_results.append({"id": tc_id, "predicted": [], "latency": latency})
            f1_scores.append(0.0)
            continue

        # Use the first extracted requirement for comparison
        pred = reqs[0]

        try:
            sev_ok  = (pred.severity or "").lower() == exp["severity"].lower()
            rtyp_ok = (pred.requirement_type or "").lower() == exp["requirement_type"].lower()
            f1      = targets_f1(pred.check_targets or [], exp["check_targets"])
        except Exception as e:
            print(f"  [{tc_id}] ERROR parsing prediction: {e}")
            per_case_results.append({"id": tc_id, "error": str(e)})
            f1_scores.append(0.0)
            continue

        severity_hits += int(sev_ok)
        req_type_hits += int(rtyp_ok)
        f1_scores.append(f1)

        # Rough token estimate (4 chars ≈ 1 token)
        tokens = (len(text) + len(str(pred.model_dump()))) // 4
        total_tokens += tokens

        status = "OK" if sev_ok and rtyp_ok and f1 > 0.5 else "PARTIAL"
        print(f"  [{tc_id}] {status} | sev={sev_ok} type={rtyp_ok} f1={f1:.2f} t={latency:.1f}s")

        per_case_results.append({
            "id": tc_id,
            "predicted": pred.model_dump(),
            "expected": exp,
            "severity_ok": sev_ok,
            "req_type_ok": rtyp_ok,
            "targets_f1": round(f1, 3),
            "latency_s": round(latency, 2),
        })

    n = len(test_cases)
    avg_lat = sum(latencies) / len(latencies) if latencies else 0
    cost = (total_tokens / 1000) * COST_PER_1K.get(model, 0.003)

    summary = {
        "model": model,
        "n_cases": n,
        "severity_accuracy":     round(severity_hits / n, 3),
        "req_type_accuracy":     round(req_type_hits / n, 3),
        "avg_targets_f1":        round(sum(f1_scores) / len(f1_scores), 3) if f1_scores else 0,
        "avg_latency_s":         round(avg_lat, 2),
        "total_tokens_est":      total_tokens,
        "estimated_cost_usd":    round(cost, 4),
    }

    out_path = os.path.join(RESULTS_DIR, f"results_{model.replace('/', '_')}.json")
    with open(out_path, "w") as f:
        json.dump({"summary": summary, "per_case": per_case_results}, f, indent=2)
    print(f"\nResults saved → {out_path}")

    return summary


def print_comparison_table(summaries: list):
    print("\n" + "=" * 80)
    print("MULTI-MODEL COMPARISON SUMMARY")
    print("=" * 80)
    header = f"{'Model':<42} {'SevAcc':>7} {'TypeAcc':>8} {'F1':>6} {'Lat(s)':>7} {'Cost$':>8}"
    print(header)
    print("-" * 80)
    for s in summaries:
        name = s["model"].split("/")[-1][:40]
        print(
            f"{name:<42} "
            f"{s['severity_accuracy']:>7.3f} "
            f"{s['req_type_accuracy']:>8.3f} "
            f"{s['avg_targets_f1']:>6.3f} "
            f"{s['avg_latency_s']:>7.2f} "
            f"{s['estimated_cost_usd']:>8.4f}"
        )
    print("=" * 80)


def main():
    test_cases = load_test_cases()
    print(f"Loaded {len(test_cases)} test cases from {TEST_CASES_PATH}")

    summaries = []
    for model in MODELS:
        try:
            summary = evaluate_model(model, test_cases)
            summaries.append(summary)
        except Exception as e:
            print(f"Failed to evaluate {model}: {e}")

    if summaries:
        print_comparison_table(summaries)
        with open(os.path.join(RESULTS_DIR, "comparison_summary.json"), "w") as f:
            json.dump(summaries, f, indent=2)
        print("\nComparison saved → evaluation/comparison_summary.json")


if __name__ == "__main__":
    main()
