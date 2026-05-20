"""
End-to-End Multi-Model Evaluation — False-Positive Filter
---------------------------------------------------------
Loads the hand-labeled `fp_annotations.json` dataset, runs each model
through the FP-filter consensus engine, and computes:

  - Per-model precision, recall, F1 on the GENUINE class
  - Per-model precision, recall, F1 on the FALSE_POSITIVE class
  - Cohen's kappa between every model pair (consensus reliability)
  - FP reduction rate (how many true FPs the consensus correctly suppresses)
  - Confusion matrix per model

This replaces the previous Checkov-as-ground-truth eval, whose precision
was forced to 100% by construction.  Annotations live at
`evaluation/fp_annotations.json` and contain a check_id + HCL block +
GENUINE / FALSE_POSITIVE label for each entry.

Usage:
    cd backend
    python ../evaluation/eval_e2e.py
"""

import sys, os, json, asyncio, time, argparse
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), "backend", ".env"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "backend"))

from agents.planner import ComplianceRequirement
from agents.executor import Finding
from agents.consensus import (
    MODELS as DEFAULT_MODELS,
    _judge,            # per-model verdict function
)

POLICIES_DIR     = os.path.join(os.path.dirname(os.path.dirname(__file__)), "policies")
ANNOTATIONS_PATH = os.path.join(os.path.dirname(__file__), "fp_annotations.json")
RESULTS_PATH     = os.path.join(os.path.dirname(__file__), "eval_e2e_results.json")


def load_policy(name: str):
    path = os.path.join(POLICIES_DIR, f"{name}.json")
    with open(path) as f:
        data = json.load(f)
    return [ComplianceRequirement(**r) for r in data["requirements"]]


def load_annotations():
    with open(ANNOTATIONS_PATH) as f:
        data = json.load(f)
    return data["annotations"]


def annotations_to_findings(annotations):
    findings = []
    for a in annotations:
        findings.append(Finding({
            "check_id":        a["check_id"],
            "resource":        a["resource"],
            "file_path":       a["file_path"],
            "file_line_range": a.get("file_line_range", [1, 1]),
            "hcl_block":       a["hcl_block"],
        }))
    return findings


def prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return round(p, 3), round(r, 3), round(f, 3)


def cohen_kappa(labels_a, labels_b):
    """Standard Cohen's kappa for two raters over the same set of items."""
    assert len(labels_a) == len(labels_b)
    n = len(labels_a)
    if n == 0:
        return 0.0
    categories = sorted(set(labels_a) | set(labels_b))
    if len(categories) < 2:
        return 1.0
    agree = sum(1 for x, y in zip(labels_a, labels_b) if x == y) / n
    pe = 0.0
    for c in categories:
        pa = labels_a.count(c) / n
        pb = labels_b.count(c) / n
        pe += pa * pb
    if pe >= 1.0:
        return 1.0
    return round((agree - pe) / (1 - pe), 3)


def confusion(predictions, truths, positive="GENUINE"):
    tp = fp = tn = fn = 0
    for p, t in zip(predictions, truths):
        if p == positive and t == positive:
            tp += 1
        elif p == positive and t != positive:
            fp += 1
        elif p != positive and t == positive:
            fn += 1
        else:
            tn += 1
    return tp, fp, tn, fn


def collapse_verdict(v):
    """Map the model's raw verdict to one of {GENUINE, FALSE_POSITIVE, UNCERTAIN}."""
    if not v:
        return "UNCERTAIN"
    return (v.get("v") or "UNCERTAIN").upper()


def collapse_to_binary(verdict_label):
    """Collapse 3-way verdict to binary GENUINE vs NOT_GENUINE for P/R/F1."""
    return "GENUINE" if verdict_label == "GENUINE" else "FALSE_POSITIVE"


async def main(models):
    annotations  = load_annotations()
    requirements = load_policy("cis_aws_v7")
    findings     = annotations_to_findings(annotations)
    truths       = [a["label"] for a in annotations]

    n_genuine    = sum(1 for t in truths if t == "GENUINE")
    n_truly_fp   = sum(1 for t in truths if t == "FALSE_POSITIVE")

    print(f"\n{'='*70}")
    print("  AUDITTRACE — FP-FILTER EVALUATION")
    print(f"{'='*70}")
    print(f"  Dataset : {len(annotations)} annotated findings "
          f"({n_genuine} GENUINE, {n_fp} FALSE_POSITIVE)")
    print(f"  Policy  : cis_aws_v7 ({len(requirements)} requirements)")
    print(f"  Models  : {', '.join(m.split('/')[-1] for m in models)}")
    print(f"{'='*70}\n")

    # ── Per-model verdicts ───────────────────────────────────────────
    loop  = asyncio.get_event_loop()
    t0    = time.time()
    per_model_raw = await asyncio.gather(*[
        loop.run_in_executor(None, _judge, model, findings, requirements)
        for model in models
    ])
    elapsed = time.time() - t0
    print(f"\n[verdicts gathered in {elapsed:.1f}s — cache hits are instant]\n")

    # Per-model label arrays (3-way) and binary
    per_model_labels: dict = {}
    for model, raw in zip(models, per_model_raw):
        # raw is {idx: {v, c, r}} — index aligns with annotations order
        labels_3way  = [collapse_verdict(raw.get(i)) for i in range(len(findings))]
        labels_bin   = [collapse_to_binary(l) for l in labels_3way]
        per_model_labels[model] = {"3way": labels_3way, "binary": labels_bin, "raw": raw}

    # ── Per-model P/R/F1 (GENUINE class) ─────────────────────────────
    print(f"{'='*70}")
    print("  PER-MODEL CLASSIFICATION  (positive class = GENUINE)")
    print(f"{'='*70}")
    print(f"  {'Model':<36}  {'P':>6}  {'R':>6}  {'F1':>6}  {'TP':>4}  {'FP':>4}  {'FN':>4}  {'TN':>4}")
    print(f"  {'-'*70}")
    by_model = {}
    for model in models:
        preds = per_model_labels[model]["binary"]
        tp, fp, tn, fn = confusion(preds, truths, positive="GENUINE")
        p, r, f1 = prf(tp, fp, fn)
        by_model[model] = {
            "precision": p, "recall": r, "f1": f1,
            "tp": tp, "fp": fp, "tn": tn, "fn": fn,
            "accuracy": round((tp + tn) / len(annotations), 3),
        }
        name = model.split("/")[-1][:35]
        print(f"  {name:<36}  {p:>6.1%}  {r:>6.1%}  {f1:>6.1%}  {tp:>4}  {fp:>4}  {fn:>4}  {tn:>4}")

    # ── FP-class P/R/F1 (positive class = FALSE_POSITIVE) ────────────
    print(f"\n{'='*70}")
    print("  PER-MODEL FP-DETECTION  (positive class = FALSE_POSITIVE)")
    print(f"  i.e. how well does the model catch true false positives?")
    print(f"{'='*70}")
    print(f"  {'Model':<36}  {'P':>6}  {'R':>6}  {'F1':>6}")
    print(f"  {'-'*70}")
    by_model_fp = {}
    for model in models:
        preds = per_model_labels[model]["binary"]
        tp, fp, tn, fn = confusion(preds, truths, positive="FALSE_POSITIVE")
        p, r, f1 = prf(tp, fp, fn)
        by_model_fp[model] = {"precision": p, "recall": r, "f1": f1}
        name = model.split("/")[-1][:35]
        print(f"  {name:<36}  {p:>6.1%}  {r:>6.1%}  {f1:>6.1%}")

    # ── Cohen's kappa between model pairs ────────────────────────────
    print(f"\n{'='*70}")
    print("  INTER-MODEL AGREEMENT  (Cohen's kappa on 3-way verdicts)")
    print(f"  1.0 = perfect agreement, 0.0 = chance, <0 = worse than chance")
    print(f"{'='*70}")
    kappas = {}
    for i, m1 in enumerate(models):
        for m2 in models[i + 1:]:
            k = cohen_kappa(per_model_labels[m1]["3way"], per_model_labels[m2]["3way"])
            kappas[f"{m1.split('/')[-1]} vs {m2.split('/')[-1]}"] = k
            print(f"  {m1.split('/')[-1]:<28} vs {m2.split('/')[-1]:<28}  kappa = {k:>5}")

    # ── Consensus tier evaluation ────────────────────────────────────
    # Build the consensus label per annotation: count GENUINE votes
    consensus_scores = []
    consensus_labels = []
    for i in range(len(findings)):
        votes = [per_model_labels[m]["3way"][i] for m in models]
        n_gen = sum(1 for v in votes if v == "GENUINE")
        n_fp  = sum(1 for v in votes if v == "FALSE_POSITIVE")
        n_unc = sum(1 for v in votes if v == "UNCERTAIN")
        consensus_scores.append(n_gen)

        if n_gen == len(models):
            consensus_labels.append("HIGH")            # 3/3 GENUINE
        elif n_gen >= 1 and n_gen >= n_fp:
            consensus_labels.append("LIKELY")          # majority GENUINE
        elif n_fp == len(models):
            consensus_labels.append("SUPPRESSED")      # 3/3 FP
        elif n_fp >= 1 and n_fp > n_gen:
            consensus_labels.append("LIKELY_FP")       # majority FP
        else:
            consensus_labels.append("UNCERTAIN")

    print(f"\n{'='*70}")
    print("  CONSENSUS TIER BREAKDOWN")
    print(f"{'='*70}")
    tier_counts = {}
    for tier in consensus_labels:
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
    for tier in ["HIGH", "LIKELY", "UNCERTAIN", "LIKELY_FP", "SUPPRESSED"]:
        c = tier_counts.get(tier, 0)
        if c:
            print(f"  {tier:<14}  {c:>4}")

    # Per-tier precision (what fraction of items in this tier are truly GENUINE)
    print(f"\n{'='*70}")
    print("  PER-TIER PRECISION  (does HIGH tier actually = GENUINE?)")
    print(f"{'='*70}")
    by_tier = {}
    for tier in ["HIGH", "LIKELY", "UNCERTAIN", "LIKELY_FP", "SUPPRESSED"]:
        items = [(consensus_labels[i], truths[i]) for i in range(len(truths)) if consensus_labels[i] == tier]
        if not items:
            continue
        n_truly_gen = sum(1 for _, t in items if t == "GENUINE")
        n_truly_fp  = sum(1 for _, t in items if t == "FALSE_POSITIVE")
        by_tier[tier] = {
            "count": len(items),
            "truly_genuine": n_truly_gen,
            "truly_fp":      n_truly_fp,
            "genuine_pct":   round(n_truly_gen / len(items), 3),
        }
        print(f"  {tier:<14}  count={len(items):>3}  truly_genuine={n_truly_gen:>3}  truly_fp={n_truly_fp:>3}  "
              f"%genuine={n_truly_gen/len(items):.1%}")

    # ── FP reduction rate ────────────────────────────────────────────
    true_fp_indices       = [i for i, t in enumerate(truths) if t == "FALSE_POSITIVE"]
    suppressed_correctly  = sum(
        1 for i in true_fp_indices
        if consensus_labels[i] in ("SUPPRESSED", "LIKELY_FP")
    )
    fp_reduction_rate = round(suppressed_correctly / len(true_fp_indices), 3) if true_fp_indices else 0.0

    true_gen_indices      = [i for i, t in enumerate(truths) if t == "GENUINE"]
    kept_correctly        = sum(
        1 for i in true_gen_indices
        if consensus_labels[i] in ("HIGH", "LIKELY", "UNCERTAIN")
    )
    tp_retention_rate = round(kept_correctly / len(true_gen_indices), 3) if true_gen_indices else 0.0

    print(f"\n{'='*70}")
    print("  HEADLINE NUMBERS")
    print(f"{'='*70}")
    print(f"  FP reduction rate     : {fp_reduction_rate:.1%}  "
          f"({suppressed_correctly}/{len(true_fp_indices)} true FPs correctly suppressed)")
    print(f"  TP retention rate     : {tp_retention_rate:.1%}  "
          f"({kept_correctly}/{len(true_gen_indices)} true violations retained)")
    print(f"  Overall accuracy      : ", end="")
    correct = sum(1 for i in range(len(truths))
                  if (truths[i] == "GENUINE" and consensus_labels[i] in ("HIGH", "LIKELY", "UNCERTAIN"))
                  or (truths[i] == "FALSE_POSITIVE" and consensus_labels[i] in ("SUPPRESSED", "LIKELY_FP")))
    accuracy = round(correct / len(truths), 3)
    print(f"{accuracy:.1%}  ({correct}/{len(truths)} correct)")

    # ── Per-finding inspection (errors only) ─────────────────────────
    errors = []
    for i, (truth, cons) in enumerate(zip(truths, consensus_labels)):
        agreed_with_truth = (
            (truth == "GENUINE" and cons in ("HIGH", "LIKELY"))
            or (truth == "FALSE_POSITIVE" and cons in ("SUPPRESSED", "LIKELY_FP"))
        )
        if not agreed_with_truth:
            errors.append({
                "id":             annotations[i]["id"],
                "truth":          truth,
                "consensus":      cons,
                "check_id":       annotations[i]["check_id"],
                "rationale":      annotations[i]["rationale"][:80],
                "per_model":      {m: per_model_labels[m]["3way"][i] for m in models},
            })

    print(f"\n{'='*70}")
    print(f"  CONSENSUS ERRORS  ({len(errors)} / {len(truths)})")
    print(f"{'='*70}")
    for e in errors[:15]:
        models_str = "  ".join(f"{m.split('/')[-1][:6]}={e['per_model'][m][:3]}" for m in models)
        print(f"  {e['id']}  truth={e['truth']:<14}  cons={e['consensus']:<10}  {models_str}")
        print(f"           {e['check_id']}  -  {e['rationale']}")
    if len(errors) > 15:
        print(f"  ... and {len(errors) - 15} more")

    # ── Save results ──────────────────────────────────────────────────
    results = {
        "dataset_size":         len(annotations),
        "n_genuine":            n_genuine,
        "n_false_positive":     n_fp,
        "models":               models,
        "by_model_genuine_cls": by_model,
        "by_model_fp_cls":      by_model_fp,
        "kappa":                kappas,
        "consensus_tiers":      tier_counts,
        "by_tier":              by_tier,
        "fp_reduction_rate":    fp_reduction_rate,
        "tp_retention_rate":    tp_retention_rate,
        "overall_accuracy":     accuracy,
        "errors":               errors,
    }

    with open(RESULTS_PATH, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n  Saved -> {RESULTS_PATH}")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AuditTrace FP-filter evaluation")
    parser.add_argument("--models", default=None,
                        help="Comma-separated model IDs (default: all 3 consensus models)")
    args = parser.parse_args()

    active_models = (
        [m.strip() for m in args.models.split(",") if m.strip()]
        if args.models else DEFAULT_MODELS
    )

    asyncio.run(main(active_models))
