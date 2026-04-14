"""
AuditTrace — LangGraph Orchestration
--------------------------------------
Wires the Planner → Executor → Critic pipeline using LangGraph's
StateGraph so each agent runs as a discrete node with shared state.
"""

import os
from typing import TypedDict, List, Dict, Any

from langgraph.graph import StateGraph, END
from dotenv import load_dotenv

from agents import PlannerAgent, ExecutorAgent, CriticAgent, ComplianceRequirement
from agents.executor import Finding
from tools import extract_text, chunk_by_section, clone_repo

load_dotenv()


# ---------------------------------------------------------------------------
# Shared pipeline state
# ---------------------------------------------------------------------------

class AuditState(TypedDict):
    pdf_path: str
    repo_url: str
    policy_chunks: List[str]
    requirements: List[ComplianceRequirement]
    repo_local_path: str
    findings_map: Dict[str, List[Finding]]
    report: Dict[str, Any]


# ---------------------------------------------------------------------------
# Node functions (one per agent)
# ---------------------------------------------------------------------------

def plan_node(state: AuditState) -> AuditState:
    """Planner: parse PDF → extract requirements."""
    text = extract_text(state["pdf_path"])
    chunks = chunk_by_section(text)
    planner = PlannerAgent()
    requirements: List[ComplianceRequirement] = []
    for chunk in chunks:
        requirements.extend(planner.decompose(chunk))
    return {**state, "policy_chunks": chunks, "requirements": requirements}


def execute_node(state: AuditState) -> AuditState:
    """Executor: clone repo → run Checkov → map findings to requirements."""
    token = os.environ["GITHUB_TOKEN"]
    local_path = clone_repo(state["repo_url"], token)
    executor = ExecutorAgent(local_path)
    findings_map = executor.execute(state["requirements"])
    return {**state, "repo_local_path": local_path, "findings_map": findings_map}


def critic_node(state: AuditState) -> AuditState:
    """Critic: build compliance trace graph + suggest fixes."""
    critic = CriticAgent()
    report = critic.generate_report(state["requirements"], state["findings_map"])
    return {**state, "report": report}


# ---------------------------------------------------------------------------
# Graph assembly
# ---------------------------------------------------------------------------

def build_graph() -> StateGraph:
    graph = StateGraph(AuditState)
    graph.add_node("planner", plan_node)
    graph.add_node("executor", execute_node)
    graph.add_node("critic", critic_node)

    graph.set_entry_point("planner")
    graph.add_edge("planner", "executor")
    graph.add_edge("executor", "critic")
    graph.add_edge("critic", END)

    return graph.compile()


# ---------------------------------------------------------------------------
# FastAPI wrapper
# ---------------------------------------------------------------------------

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
import shutil, tempfile

app = FastAPI(title="AuditTrace API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

audit_graph = build_graph()


@app.post("/audit")
async def run_audit(
    pdf: UploadFile = File(...),
    repo_url: str = Form(...),
):
    """
    Upload a compliance PDF and provide a GitHub repo URL.
    Returns the full compliance trace report.
    """
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        shutil.copyfileobj(pdf.file, tmp)
        pdf_path = tmp.name

    initial_state: AuditState = {
        "pdf_path": pdf_path,
        "repo_url": repo_url,
        "policy_chunks": [],
        "requirements": [],
        "repo_local_path": "",
        "findings_map": {},
        "report": {},
    }

    final_state = await audit_graph.ainvoke(initial_state)
    return final_state["report"]


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
