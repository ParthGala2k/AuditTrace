"""
Consensus Engine
----------------
Given pre-distilled requirements (from policies/*.json) and Checkov findings:

1. Keyword matching produces candidate (requirement, finding) pairs — fast, shared.
2. Each of 3 LLMs reviews ALL candidates in a single batched call and confirms
   which mappings are genuine violations. This is 3 LLM calls total.
3. Violations are ranked by how many models confirmed them:
     3/3 → HIGH CONFIDENCE
     2/3 → LIKELY
     1/3 → UNCERTAIN
"""

import asyncio
import json
from typing import List, Dict, Any

from langchain_core.prompts import ChatPromptTemplate
from .planner import ComplianceRequirement
from .executor import ExecutorAgent, Finding
from .llm import get_llm

MODELS = [
    "openai/gpt-4o-mini",
    "deepseek/deepseek-chat",
    "meta-llama/llama-3.1-70b-instruct",
]

CONFIDENCE_LABEL = {3: "HIGH", 2: "LIKELY", 1: "UNCERTAIN"}

MAX_CANDIDATES = 60  # cap to keep confirmation calls fast

CONFIRM_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "You are a security compliance expert. "
     "You will be given a list of candidate compliance violations — each is a Checkov "
     "infrastructure finding mapped to a policy requirement. "
     "For each candidate, decide: does this Checkov finding genuinely violate the stated "
     "requirement? Reply ONLY with a JSON object in the exact format: "
     '{"confirmations": [true, false, true, ...]} '
     "with one boolean per candidate, in the same order."),
    ("human",
     "Candidates:\n{candidates_json}"),
])


def _keyword_candidates(
    requirements: List[ComplianceRequirement],
    all_findings: List[Finding],
) -> List[Dict]:
    """
    Use ExecutorAgent's keyword matching to produce (req, finding) candidate pairs.
    Returns a flat list capped at MAX_CANDIDATES, sorted by severity.
    """
    dummy = ExecutorAgent.__new__(ExecutorAgent)
    dummy.repo_path = ""

    _sev = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    candidates = []

    for req in requirements:
        for finding in all_findings:
            if dummy._matches(finding, req):
                candidates.append({
                    "requirement": req.model_dump(),
                    "finding": {
                        "check_id":       finding.get("check_id"),
                        "resource":       finding.get("resource"),
                        "file_path":      finding.get("file_path"),
                        "file_line_range": finding.get("file_line_range"),
                    },
                })

    # Sort critical/high first, then cap
    candidates.sort(key=lambda c: _sev.get(c["requirement"].get("severity", "low"), 3))
    return candidates[:MAX_CANDIDATES]


def _confirm_batch(model: str, candidates: List[Dict]) -> List[bool]:
    """
    Single batched LLM call: ask the model to confirm each candidate.
    Returns a list of booleans, one per candidate.
    """
    llm   = get_llm(model, temperature=0)
    chain = CONFIRM_PROMPT | llm

    candidates_json = json.dumps(
        [{"index": i, **c} for i, c in enumerate(candidates)],
        indent=2,
    )

    try:
        response = chain.invoke({"candidates_json": candidates_json})
        result   = json.loads(response.content)
        confs    = result.get("confirmations", [])
        # Pad with False if model returned fewer booleans than candidates
        while len(confs) < len(candidates):
            confs.append(False)
        return [bool(c) for c in confs[:len(candidates)]]
    except Exception as e:
        print(f"[consensus] {model} confirmation error: {e} — defaulting to keyword match")
        return [True] * len(candidates)   # on error, trust keyword match


async def run_consensus(
    requirements: List[ComplianceRequirement],
    all_findings: List[Finding],
    models: List[str] | None = None,
) -> Dict[str, Any]:
    """
    Run consensus matching across multiple models.

    Args:
        requirements:  Pre-distilled requirements loaded from policies/*.json.
        all_findings:  Raw Checkov findings from the scanned repo.
        models:        Override model list (defaults to MODELS).

    Returns:
        Report dict with violations ranked by confidence, compliance_trace, summary.
    """
    active_models = models or MODELS

    # Step 1 — shared keyword matching (deterministic, one pass)
    candidates = _keyword_candidates(requirements, all_findings)
    print(f"[consensus] {len(candidates)} candidate violations → sending to {len(active_models)} models")

    if not candidates:
        return _empty_report(active_models)

    # Step 2 — 3 batched confirmation calls in parallel
    loop = asyncio.get_event_loop()
    confirmations: List[List[bool]] = await asyncio.gather(*[
        loop.run_in_executor(None, _confirm_batch, model, candidates)
        for model in active_models
    ])

    # Step 3 — vote: count how many models confirmed each candidate
    violations = []
    for i, candidate in enumerate(candidates):
        votes         = [confirmations[m][i] for m in range(len(active_models))]
        score         = sum(votes)
        models_agreed = [active_models[m] for m, v in enumerate(votes) if v]

        if score == 0:
            continue   # no model confirmed → skip

        req     = candidate["requirement"]
        finding = candidate["finding"]

        violations.append({
            "clause_id":        req["clause_id"],
            "clause_text":      req["clause_text"],
            "severity":         req["severity"],
            "requirement_type": req["requirement_type"],
            "check_id":         finding["check_id"],
            "resource":         finding["resource"],
            "file":             finding["file_path"],
            "line":             finding["file_line_range"],
            "consensus_score":  score,
            "confidence":       CONFIDENCE_LABEL.get(score, "UNCERTAIN"),
            "models_agreed":    models_agreed,
        })

    # Sort: highest confidence first, then severity
    _sev = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    violations.sort(key=lambda v: (
        -v["consensus_score"],
        _sev.get(v.get("severity", "low"), 3),
    ))

    n = len(active_models)
    return {
        "models_used":      active_models,
        "violations":       violations,
        "compliance_trace": _build_trace(violations),
        "summary": {
            "total_violations": len(violations),
            "high_confidence":  sum(1 for v in violations if v["consensus_score"] == n),
            "likely":           sum(1 for v in violations if v["consensus_score"] == n - 1),
            "uncertain":        sum(1 for v in violations if v["consensus_score"] == 1),
            "models_run":       n,
        },
    }


def _build_trace(violations: List[Dict]) -> Dict[str, Any]:
    nodes, edges = {}, []
    for v in violations:
        cid  = v["clause_id"]
        line = (v.get("line") or [0])[0]
        fkey = f"{(v.get('file') or '?').split('/')[-1]}:{line}"

        nodes.setdefault(cid,  {"id": cid,  "type": "clause", "label": cid})
        nodes.setdefault(fkey, {"id": fkey, "type": "code",   "label": fkey})
        edges.append({
            "from":       fkey,
            "to":         cid,
            "check_id":   v.get("check_id"),
            "confidence": v.get("confidence"),
        })

    return {"nodes": list(nodes.values()), "edges": edges}


def _empty_report(models: List[str]) -> Dict[str, Any]:
    return {
        "models_used":      models,
        "violations":       [],
        "compliance_trace": {"nodes": [], "edges": []},
        "summary": {
            "total_violations": 0,
            "high_confidence":  0,
            "likely":           0,
            "uncertain":        0,
            "models_run":       len(models),
        },
    }
