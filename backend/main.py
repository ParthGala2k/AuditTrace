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
import json
from typing import List, Dict, Any, Optional

from langgraph.graph import StateGraph, END
from dotenv import load_dotenv
from fastapi import FastAPI, Form, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from agents.planner import ComplianceRequirement
from agents.executor import Finding
from agents.consensus import run_consensus, MODELS as DEFAULT_MODELS
from tools.checkov_runner import clone_repo, run_checkov
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
    """Clone repo and run Checkov."""
    token      = os.environ.get("GITHUB_TOKEN", "")
    local_path = clone_repo(state["repo_url"], token)
    findings   = [Finding(f) for f in run_checkov(local_path)]
    print(f"[scan_node] {len(findings)} Checkov findings")
    return {**state, "repo_local_path": local_path, "all_findings": findings}


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

    final_state  = await audit_graph.ainvoke(initial_state)
    report       = final_state["report"]
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


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
