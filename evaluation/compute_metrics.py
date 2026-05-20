"""
Metrics computation for AuditTrace.

Ground truth = raw Checkov output (every failed check in the repo).
Predictions  = violations our system surfaced (matched + LLM-confirmed).

This works on ANY repo with IaC — no human annotation needed.
"""

import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))


def _key(check_id: str, file_path: str) -> tuple:
    """Stable match key: (check_id, normalised_file_path)."""
    norm = (file_path or '').replace('\\', '/').lower().lstrip('./')
    return (check_id or '', norm)


def get_ground_truth(repo_local_path: str) -> list:
    """Run Checkov directly and return every failed check as ground truth."""
    from tools.checkov_runner import run_checkov
    return run_checkov(repo_local_path)


def compute_metrics(
    ground_truth: list,   # raw Checkov finding dicts
    violations:   list,   # violation dicts from our report
    models:       list,   # model names used in the audit
) -> dict:
    """
    Compare our violations against raw Checkov ground truth.

    Returns nested dict:
      overall       → precision / recall / F1 / TP / FP / FN
      by_model      → same per model
      by_confidence → precision per HIGH / LIKELY / UNCERTAIN tier
      by_severity   → flagged + confirmed per severity level
    """
    gt_keys = {_key(f.get('check_id'), f.get('file_path')) for f in ground_truth}

    preds = []
    for v in violations:
        k = _key(v.get('check_id'), v.get('file'))
        preds.append({
            'key':             k,
            'in_gt':           k in gt_keys,
            'confidence':      v.get('confidence', 'UNCERTAIN'),
            'consensus_score': v.get('consensus_score', 1),
            'models_agreed':   v.get('models_agreed', []),
            'severity':        (v.get('severity') or 'low').lower(),
        })

    # ── overall ─────────────────────────────────────────────────────
    tp = sum(1 for p in preds if p['in_gt'])
    fp = sum(1 for p in preds if not p['in_gt'])
    fn = max(0, len(gt_keys) - tp)

    def _prf(tp, fp, fn):
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec  = tp / (tp + fn) if tp + fn else 0.0
        f1   = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        return round(prec, 3), round(rec, 3), round(f1, 3)

    prec, rec, f1 = _prf(tp, fp, fn)

    overall = {
        'precision': prec, 'recall': rec, 'f1': f1,
        'true_positives':          tp,
        'false_positives':         fp,
        'false_negatives':         fn,
        'total_checkov_findings':  len(gt_keys),
        'total_our_violations':    len(preds),
        'coverage_pct':            round(100 * tp / len(gt_keys), 1) if gt_keys else 0,
    }

    # ── per model ────────────────────────────────────────────────────
    by_model = {}
    for model in models:
        mp   = [p for p in preds if model in p['models_agreed']]
        m_tp = sum(1 for p in mp if p['in_gt'])
        m_fp = sum(1 for p in mp if not p['in_gt'])
        m_fn = max(0, len(gt_keys) - m_tp)
        p2, r2, f2 = _prf(m_tp, m_fp, m_fn)
        short = model.split('/')[-1]
        by_model[short] = {
            'model':     model,
            'precision': p2, 'recall': r2, 'f1': f2,
            'tp': m_tp, 'fp': m_fp, 'fn': m_fn,
            'violations_flagged': len(mp),
        }

    # ── per confidence tier ──────────────────────────────────────────
    by_confidence = {}
    for tier in ['HIGH', 'LIKELY', 'UNCERTAIN']:
        tp2 = [p for p in preds if p['confidence'] == tier]
        if not tp2:
            continue
        t_tp   = sum(1 for p in tp2 if p['in_gt'])
        t_fp   = sum(1 for p in tp2 if not p['in_gt'])
        t_prec = round(t_tp / (t_tp + t_fp), 3) if t_tp + t_fp else 0.0
        by_confidence[tier] = {
            'precision': t_prec,
            'count': len(tp2),
            'tp': t_tp, 'fp': t_fp,
        }

    # ── per severity ─────────────────────────────────────────────────
    by_severity = {}
    for sev in ['critical', 'high', 'medium', 'low']:
        sp     = [p for p in preds if p['severity'] == sev]
        s_tp   = sum(1 for p in sp if p['in_gt'])
        s_fp   = sum(1 for p in sp if not p['in_gt'])
        s_prec = round(s_tp / len(sp), 3) if sp else None
        by_severity[sev] = {
            'flagged':   len(sp),
            'confirmed': s_tp,
            'false_positives': s_fp,
            'precision': s_prec,
        }

    return {
        'overall':       overall,
        'by_model':      by_model,
        'by_confidence': by_confidence,
        'by_severity':   by_severity,
    }


# ── CLI mode ─────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import argparse
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), '..', 'backend', '.env'))

    parser = argparse.ArgumentParser(description='Compute AuditTrace metrics against Checkov ground truth.')
    parser.add_argument('report',     help='Path to report.json produced by demo.py')
    parser.add_argument('repo_local', help='Local path to the cloned repo (or re-clone with --repo)')
    parser.add_argument('--repo',     help='GitHub repo URL to clone fresh', default=None)
    args = parser.parse_args()

    from tools.checkov_runner import clone_repo

    repo_path = args.repo_local
    if args.repo:
        import tempfile
        repo_path = clone_repo(args.repo, os.environ.get('GITHUB_TOKEN', ''))
        print(f'Cloned → {repo_path}')

    print('Running Checkov ground truth scan…')
    gt = get_ground_truth(repo_path)
    print(f'Ground truth: {len(gt)} failed checks')

    with open(args.report) as f:
        report = json.load(f)

    violations = report.get('violations', [])
    models     = report.get('models_used', [])
    print(f'Our report : {len(violations)} violations\n')

    m = compute_metrics(gt, violations, models)

    print('═' * 60)
    print('OVERALL')
    print('═' * 60)
    o = m['overall']
    print(f"  Precision  {o['precision']:.1%}   ({o['true_positives']} TP / {o['false_positives']} FP)")
    print(f"  Recall     {o['recall']:.1%}   ({o['true_positives']} TP / {o['false_negatives']} FN)")
    print(f"  F1         {o['f1']:.1%}")
    print(f"  Coverage   {o['coverage_pct']}% of {o['total_checkov_findings']} Checkov findings surfaced")

    print('\nPER MODEL')
    print('─' * 60)
    for name, stats in m['by_model'].items():
        print(f"  {name:<36}  P={stats['precision']:.1%}  R={stats['recall']:.1%}  F1={stats['f1']:.1%}")

    print('\nPER CONFIDENCE TIER')
    print('─' * 60)
    for tier, stats in m['by_confidence'].items():
        print(f"  {tier:<12}  Precision={stats['precision']:.1%}  n={stats['count']}  (FP={stats['fp']})")

    print('\nPER SEVERITY')
    print('─' * 60)
    for sev, stats in m['by_severity'].items():
        p = f"{stats['precision']:.1%}" if stats['precision'] is not None else 'N/A'
        print(f"  {sev:<10}  flagged={stats['flagged']}  confirmed={stats['confirmed']}  P={p}")

    out = os.path.join(os.path.dirname(__file__), 'metrics.json')
    with open(out, 'w') as f:
        json.dump(m, f, indent=2)
    print(f'\nSaved → {out}')
