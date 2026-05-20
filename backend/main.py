"""
AuditTrace — FastAPI + LangGraph
---------------------------------
Audit flow:
  POST /audit { repo_url, policy }
    1. Load pre-distilled requirements from policies/<policy>.json
    2. Clone repo, run Checkov once
    3. 3-model consensus matching (3 batched LLM calls)
    4. Save versioned result to SQLite
    5. Return ranked violations with confidence scores
"""

import os
import sys
import json
from typing import List, Dict, Any, Optional

from langgraph.graph import StateGraph, END
from dotenv import load_dotenv
from fastapi import FastAPI, Form, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from agents.planner import ComplianceRequirement
from agents.executor import Finding
from agents.consensus import run_consensus, MODELS as DEFAULT_MODELS
from tools.checkov_runner import clone_repo, run_checkov, extract_resource_block
import db

load_dotenv()
db.init_db()

POLICIES_DIR = os.path.join(os.path.dirname(__file__), "..", "policies")


def load_policy(name: str) -> List[ComplianceRequirement]:
    """Load pre-distilled requirements from policies/<name>.json."""
    path = os.path.join(POLICIES_DIR, f"{name}.json")
    if not os.path.exists(path):
        raise HTTPException(
            status_code=404,
            detail=f"Policy '{name}' not found. Run scripts/distill_policy.py first."
        )
    with open(path) as f:
        data = json.load(f)
    reqs = [ComplianceRequirement(**r) for r in data["requirements"]]
    print(f"[main] loaded {len(reqs)} requirements from policy '{name}'")
    return reqs


# ---------------------------------------------------------------------------
# LangGraph state
# ---------------------------------------------------------------------------

class AuditState(dict):
    pass


# ---------------------------------------------------------------------------
# Node functions
# ---------------------------------------------------------------------------

def scan_node(state: dict) -> dict:
    """Clone repo, run Checkov, attach HCL block per finding, then delete the clone."""
    import time
    import shutil
    token = os.environ.get("GITHUB_TOKEN", "")
    print(f"[scan_node] cloning {state['repo_url']}…")
    t0         = time.time()
    local_path = clone_repo(state["repo_url"], token)
    print(f"[scan_node] cloned in {time.time()-t0:.1f}s → running Checkov…")
    t1       = time.time()
    raw      = run_checkov(local_path)
    print(f"[scan_node] Checkov done in {time.time()-t1:.1f}s — {len(raw)} findings")

    findings = []
    for f in raw:
        fp_rel = (f.get("file_path") or "").lstrip("/\\")
        fp_abs = os.path.join(local_path, fp_rel)
        f["hcl_block"] = extract_resource_block(fp_abs, f.get("file_line_range") or [1, 1])
        findings.append(Finding(f))
    print(f"[scan_node] HCL blocks extracted for {sum(1 for f in findings if f.get('hcl_block'))} findings")

    shutil.rmtree(local_path, ignore_errors=True)
    print(f"[scan_node] cleaned up {local_path}")
    return {**state, "repo_local_path": "", "all_findings": findings}


async def consensus_node(state: dict) -> dict:
    """Run 3-model consensus matching."""
    report = await run_consensus(
        requirements=state["requirements"],
        all_findings=state["all_findings"],
        models=state.get("models") or DEFAULT_MODELS,
    )
    return {**state, "report": report}


# ---------------------------------------------------------------------------
# Graph
# ---------------------------------------------------------------------------

def build_graph() -> StateGraph:
    graph = StateGraph(dict)
    graph.add_node("scan",      scan_node)
    graph.add_node("consensus", consensus_node)
    graph.set_entry_point("scan")
    graph.add_edge("scan",      "consensus")
    graph.add_edge("consensus", END)
    return graph.compile()


# ---------------------------------------------------------------------------
# FastAPI
# ---------------------------------------------------------------------------

app = FastAPI(title="AuditTrace API", version="0.3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

audit_graph = build_graph()


@app.post("/audit")
async def run_audit(
    repo_url: str           = Form(...),
    policy:   str           = Form(...),
    models:   Optional[str] = Form(default=None),
):
    """
    Run a consensus compliance audit.

    - **repo_url**: GitHub repo URL containing infrastructure-as-code
    - **policy**: Name of pre-distilled policy (e.g. 'cis_aws_v7')
    - **models**: Comma-separated OpenRouter model IDs (optional)
    """
    requirements = load_policy(policy)

    model_list = (
        [m.strip() for m in models.split(",") if m.strip()]
        if models else DEFAULT_MODELS
    )

    initial_state = {
        "repo_url":        repo_url,
        "policy":          policy,
        "models":          model_list,
        "requirements":    requirements,
        "all_findings":    [],
        "repo_local_path": "",
        "report":          {},
    }

    final_state = await audit_graph.ainvoke(initial_state)
    report      = final_state["report"]
    report.setdefault("summary", {})["total_requirements"] = len(requirements)
    version_info = db.save_audit(repo_url=repo_url, model=",".join(model_list), report=report)

    return {**report, **version_info}


@app.get("/policies")
def list_policies():
    """List all available distilled policy specs."""
    os.makedirs(POLICIES_DIR, exist_ok=True)
    result = []
    for fname in os.listdir(POLICIES_DIR):
        if not fname.endswith(".json"):
            continue
        with open(os.path.join(POLICIES_DIR, fname)) as f:
            data = json.load(f)
        result.append({
            "name":              data.get("name"),
            "source_pdf":        data.get("source_pdf"),
            "model_used":        data.get("model_used"),
            "requirement_count": data.get("requirement_count"),
        })
    return result


@app.get("/history")
def get_history(repo_url: str = Query(...)):
    """Return all audit versions for a repo."""
    return db.get_history(repo_url)


@app.get("/history/report")
def get_version_report(repo_url: str = Query(...), version: int = Query(...)):
    """Return the full report for a specific audit version."""
    report = db.get_audit_report(repo_url, version)
    if report is None:
        raise HTTPException(status_code=404, detail="Version not found")
    return report


@app.post("/evaluate")
async def evaluate_audit(
    repo_url:   str = Form(...),
    violations: str = Form(...),   # JSON of violations from existing audit
    models:     str = Form(default=None),
):
    """
    Compute metrics for an ALREADY-COMPLETED audit.
    Does NOT redo the audit — uses violations passed from the frontend.
    Only runs Checkov once for ground truth (~30s), then computes metrics.
    """
    import shutil

    try:
        violation_list = json.loads(violations)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid violations JSON")

    model_list = (
        [m.strip() for m in models.split(',') if m.strip()]
        if models else DEFAULT_MODELS
    )

    # Checkov ground truth only — no LLM calls
    print(f'[evaluate] cloning {repo_url} for ground truth…')
    token      = os.environ.get('GITHUB_TOKEN', '')
    local_path = clone_repo(repo_url, token)
    raw_gt     = run_checkov(local_path)
    shutil.rmtree(local_path, ignore_errors=True)
    print(f'[evaluate] ground truth: {len(raw_gt)} Checkov findings')

    violations = violation_list

    def _norm(check_id, file_path):
        return (check_id or '', (file_path or '').replace('\\', '/').lower().lstrip('./'))

    gt_keys = {_norm(f.get('check_id'), f.get('file_path')) for f in raw_gt}

    preds = [
        {
            'key':           _norm(v.get('check_id'), v.get('file')),
            'in_gt':         _norm(v.get('check_id'), v.get('file')) in gt_keys,
            'confidence':    v.get('confidence', 'UNCERTAIN'),
            'models_agreed': v.get('models_agreed', []),
            'severity':      (v.get('severity') or 'low').lower(),
        }
        for v in violations
    ]

    def _prf(tp, fp, fn):
        p = tp / (tp + fp) if tp + fp else 0.0
        r = tp / (tp + fn) if tp + fn else 0.0
        f = 2 * p * r / (p + r) if p + r else 0.0
        return round(p, 3), round(r, 3), round(f, 3)

    tp = sum(1 for p in preds if p['in_gt'])
    fp = sum(1 for p in preds if not p['in_gt'])
    fn = max(0, len(gt_keys) - tp)
    prec, rec, f1 = _prf(tp, fp, fn)

    by_model = {}
    for model in model_list:
        mp = [p for p in preds if model in p['models_agreed']]
        m_tp = sum(1 for p in mp if p['in_gt'])
        m_fp = sum(1 for p in mp if not p['in_gt'])
        m_fn = max(0, len(gt_keys) - m_tp)
        p2, r2, f2 = _prf(m_tp, m_fp, m_fn)
        by_model[model.split('/')[-1]] = {
            'model': model, 'precision': p2, 'recall': r2, 'f1': f2,
            'tp': m_tp, 'fp': m_fp, 'fn': m_fn, 'violations_flagged': len(mp),
        }

    by_confidence = {}
    for tier in ['HIGH', 'LIKELY', 'UNCERTAIN']:
        tp2 = [p for p in preds if p['confidence'] == tier]
        if tp2:
            t_tp = sum(1 for p in tp2 if p['in_gt'])
            t_fp = len(tp2) - t_tp
            by_confidence[tier] = {
                'precision': round(t_tp / len(tp2), 3),
                'count': len(tp2), 'tp': t_tp, 'fp': t_fp,
            }

    by_severity = {}
    for sev in ['critical', 'high', 'medium', 'low']:
        sp = [p for p in preds if p['severity'] == sev]
        s_tp = sum(1 for p in sp if p['in_gt'])
        by_severity[sev] = {
            'flagged': len(sp), 'confirmed': s_tp,
            'false_positives': len(sp) - s_tp,
            'precision': round(s_tp / len(sp), 3) if sp else None,
        }

    return {
        'overall': {
            'precision': prec, 'recall': rec, 'f1': f1,
            'true_positives': tp, 'false_positives': fp, 'false_negatives': fn,
            'total_checkov_findings': len(gt_keys),
            'total_our_violations': len(preds),
            'coverage_pct': round(100 * tp / len(gt_keys), 1) if gt_keys else 0,
        },
        'by_model':      by_model,
        'by_confidence': by_confidence,
        'by_severity':   by_severity,
    }


@app.post("/fix")
async def get_fix(
    clause_text: str           = Form(...),
    check_id:    str           = Form(...),
    resource:    str           = Form(default=""),
    file_path:   str           = Form(default=""),
    model:       Optional[str] = Form(default="openai/gpt-4o-mini"),
):
    """
    Generate a Terraform diff fix for a specific violation on demand.
    Called when the user clicks 'view fix' on an issue card.
    """
    from agents.llm import get_llm
    from pydantic import BaseModel

    class DiffLine(BaseModel):
        k: str   # "ctx" | "del" | "add"
        n: int
        t: str

    class FixResult(BaseModel):
        diff: List[DiffLine]
        explanation: str

    llm = get_llm(model, temperature=0)
    structured = llm.with_structured_output(FixResult)

    prompt = (
        f"Generate a minimal Terraform diff to fix this compliance violation.\n\n"
        f"Policy clause: {clause_text}\n"
        f"Checkov check: {check_id}\n"
        f"Resource: {resource}\n"
        f"File: {file_path}\n\n"
        f"Return a diff with 'ctx' (context), 'del' (removed), 'add' (added) lines "
        f"using realistic Terraform syntax. Include 2 context lines before and after. "
        f"Use sequential line numbers starting around line 10. "
        f"Also return a 1-sentence explanation of what changed and why."
    )

    try:
        result = structured.invoke([
            {"role": "system", "content": "You are an expert infrastructure-as-code engineer. Generate precise Terraform diffs."},
            {"role": "user",   "content": prompt},
        ])
        return result.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


EVAL_DIR = os.path.join(os.path.dirname(__file__), "..", "evaluation")


@app.get("/eval/fp-filter")
def get_fp_filter_results():
    """Return the latest FP-filter eval (eval_e2e_results.json)."""
    path = os.path.join(EVAL_DIR, "eval_e2e_results.json")
    if not os.path.exists(path):
        raise HTTPException(
            status_code=404,
            detail="No FP-filter eval results yet — run `python evaluation/eval_e2e.py` from backend/."
        )
    with open(path) as f:
        return json.load(f)


@app.get("/eval/planner")
def get_planner_results():
    """Return per-model planner eval comparison (comparison_summary.json)."""
    path = os.path.join(EVAL_DIR, "comparison_summary.json")
    if not os.path.exists(path):
        raise HTTPException(
            status_code=404,
            detail="No planner eval results yet — run `python evaluation/run_eval.py` from backend/."
        )
    with open(path) as f:
        return json.load(f)


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
