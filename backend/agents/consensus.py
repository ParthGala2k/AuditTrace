"""
Consensus Engine — False-Positive Filtering
-------------------------------------------
Each model independently judges every Checkov finding as
GENUINE / FALSE_POSITIVE / UNCERTAIN given its surrounding HCL context.

This is the real value-add over Checkov alone: Checkov fires rule-based
alerts with no context, so it produces a large noisy alert list. The LLMs
read the actual resource block and reason about whether the finding is a
true security issue in this codebase or a false positive (test resource,
example code, compensating policy, intentional public-by-design, etc.).

consensus_score now counts GENUINE votes:
  3 = all models say GENUINE → HIGH    confidence true positive
  2 = two models say GENUINE → LIKELY  probably real
  1 = one  model  says GENUINE → UNCERTAIN, needs human review
  0 = all models say FP        → SUPPRESSED (excluded from violations list)
"""

import json
import asyncio
from typing import List, Dict, Any

from langchain_core.prompts import ChatPromptTemplate
from .planner import ComplianceRequirement
from .executor import Finding
from .llm import get_llm

import hashlib, pathlib

_CACHE_DIR = pathlib.Path(__file__).parent.parent / "mapping_cache"
_CACHE_DIR.mkdir(exist_ok=True)

# Bump this any time the prompt or output schema changes — old cache entries
# become invalid automatically.
TASK_VERSION = "v3-fpfilter"


def _cache_key(model: str, findings: List[Finding], requirements: List[ComplianceRequirement]) -> str:
    """
    Stable hash keyed by task version + model + check_ids + clause_ids +
    a digest of the HCL blocks (so different code produces different cache
    entries even for the same check_ids).
    """
    check_ids  = sorted({f.get("check_id", "") for f in findings})
    clause_ids = sorted(r.clause_id for r in requirements)
    hcl_digest = hashlib.sha256(
        "".join((f.get("hcl_block") or "") for f in findings).encode()
    ).hexdigest()[:12]
    payload = "|".join([TASK_VERSION, model, ",".join(check_ids), ",".join(clause_ids), hcl_digest])
    return hashlib.sha256(payload.encode()).hexdigest()[:20]


def _load_cache(key: str) -> Dict[int, dict] | None:
    path = _CACHE_DIR / f"{key}.json"
    if path.exists():
        with open(path) as f:
            return {int(k): v for k, v in json.load(f).items()}
    return None


def _save_cache(key: str, verdicts: Dict[int, dict]):
    path = _CACHE_DIR / f"{key}.json"
    with open(path, "w") as f:
        json.dump({str(k): v for k, v in verdicts.items()}, f)


MODELS = [
    "openai/gpt-4o-mini",
    "deepseek/deepseek-chat",
    "meta-llama/llama-3.1-70b-instruct",
]

CONFIDENCE_LABEL = {3: "HIGH", 2: "LIKELY", 1: "UNCERTAIN"}

# HCL blocks make each finding much larger — reduce batch size accordingly
MAX_FINDINGS_PER_CALL = 25
# Truncate any HCL block longer than this to keep prompts bounded
MAX_HCL_CHARS = 700


JUDGE_SYSTEM = (
    "You are a senior cloud security engineer triaging Checkov findings.\n"
    "For each finding you are given:\n"
    "  - the Checkov check_id and the resource it fired on\n"
    "  - the file path\n"
    "  - the surrounding Terraform/HCL block\n"
    "  - the CIS AWS clause it putatively violates\n\n"
    "Decide whether the finding is:\n"
    "  GENUINE         - a real compliance violation that should be fixed\n"
    "  FALSE_POSITIVE  - looks like a violation but is fine in context\n"
    "                    (test/example code, mitigated by another resource,\n"
    "                    intentionally public, dev-only environment, compensating\n"
    "                    control elsewhere in the file)\n"
    "  UNCERTAIN       - cannot tell without more code or business context\n\n"
    "Be honest: do not call something GENUINE just because Checkov flagged it.\n"
    "If the HCL block, file path, or naming clearly suggests the finding does not\n"
    "represent a real risk, mark it FALSE_POSITIVE.\n\n"
    "Return ONLY valid JSON in the exact shape:\n"
    '{{"verdicts": {{"0": {{"v": "GENUINE", "c": "CIS-1.4", "r": "one short reason"}}, ...}}}}\n'
    "where:\n"
    "  v = GENUINE | FALSE_POSITIVE | UNCERTAIN\n"
    "  c = clause_id from the requirements list (or null if v=FALSE_POSITIVE)\n"
    "  r = one-sentence justification (<= 20 words)\n"
    "Output every finding index. Do not include any other text."
)

JUDGE_HUMAN = (
    "FINDINGS:\n{findings_text}\n\n"
    "CIS REQUIREMENTS (clause_id -> clause | targets):\n{requirements_text}"
)

JUDGE_PROMPT = ChatPromptTemplate.from_messages([
    ("system", JUDGE_SYSTEM),
    ("human",  JUDGE_HUMAN),
])


def _truncate(text: str, n: int) -> str:
    if not text:
        return ""
    if len(text) <= n:
        return text
    return text[: n - 3] + "..."


def _format_findings(findings: List[Finding]) -> str:
    blocks = []
    for i, f in enumerate(findings):
        cid  = f.get("check_id", "?")
        res  = f.get("resource", "")
        path = (f.get("file_path") or "").replace("\\", "/")
        hcl  = _truncate((f.get("hcl_block") or "").strip(), MAX_HCL_CHARS)
        blocks.append(
            f"--- finding {i} ---\n"
            f"check_id : {cid}\n"
            f"resource : {res}\n"
            f"file     : {path}\n"
            f"hcl:\n{hcl if hcl else '(no block available)'}"
        )
    return "\n\n".join(blocks)


def _format_requirements(requirements: List[ComplianceRequirement]) -> str:
    lines = []
    for r in requirements:
        targets = ", ".join(r.check_targets[:4])
        clause  = r.clause_text[:80].replace("\n", " ")
        lines.append(f"{r.clause_id}: {clause} | [{targets}]")
    return "\n".join(lines)


def _judge(model: str, findings: List[Finding], requirements: List[ComplianceRequirement]) -> Dict[int, dict]:
    """
    Per-model verdict for every finding. Returns {idx: {v, c, r}}.
    Cached by (task_version + model + check_ids + clause_ids + hcl_digest).
    """
    cache_key = _cache_key(model, findings, requirements)
    cached    = _load_cache(cache_key)
    if cached is not None:
        print(f"[consensus] {model.split('/')[-1]} loaded {len(cached)} verdicts from cache")
        return cached

    llm   = get_llm(model, temperature=0)
    chain = JUDGE_PROMPT | llm

    all_verdicts: Dict[int, dict] = {}

    for batch_start in range(0, len(findings), MAX_FINDINGS_PER_CALL):
        batch = findings[batch_start : batch_start + MAX_FINDINGS_PER_CALL]

        findings_text     = _format_findings(batch)
        requirements_text = _format_requirements(requirements)

        print(f"[consensus] {model.split('/')[-1]} judging batch {batch_start}-{batch_start+len(batch)-1}...")

        try:
            response = chain.invoke({
                "findings_text":     findings_text,
                "requirements_text": requirements_text,
            })
            raw = (response.content or "").strip()
            if "```" in raw:
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]

            data     = json.loads(raw.strip())
            verdicts = data.get("verdicts", {})

            for idx_str, verdict in verdicts.items():
                try:
                    abs_idx = int(idx_str) + batch_start
                    if not isinstance(verdict, dict):
                        continue
                    v = (verdict.get("v") or "").upper()
                    if v not in {"GENUINE", "FALSE_POSITIVE", "UNCERTAIN"}:
                        continue
                    all_verdicts[abs_idx] = {
                        "v": v,
                        "c": verdict.get("c"),
                        "r": (verdict.get("r") or "")[:240],
                    }
                except (ValueError, AttributeError):
                    pass

        except Exception as e:
            print(f"[consensus] {model} batch {batch_start} error: {e}")
            # On error: leave batch un-verdicted

    print(f"[consensus] {model.split('/')[-1]} judged {len(all_verdicts)}/{len(findings)} findings")
    _save_cache(cache_key, all_verdicts)
    return all_verdicts


async def run_consensus(
    requirements: List[ComplianceRequirement],
    all_findings: List[Finding],
    models: List[str] | None = None,
) -> Dict[str, Any]:
    """
    Run independent FP-filter judgement across all models, then aggregate.

    A finding becomes a 'violation' when at least one model labels it
    GENUINE. consensus_score = number of models that labeled it GENUINE.
    Findings that all models label FALSE_POSITIVE are suppressed.
    """
    active_models = models or MODELS

    if not all_findings:
        return _empty_report(active_models)

    print(f"[consensus] {len(all_findings)} findings x {len(requirements)} requirements x {len(active_models)} models")

    req_by_id = {r.clause_id: r for r in requirements}

    loop = asyncio.get_event_loop()
    per_model_verdicts: List[Dict[int, dict]] = await asyncio.gather(*[
        loop.run_in_executor(None, _judge, model, all_findings, requirements)
        for model in active_models
    ])

    _sev = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    violations: List[dict] = []
    suppressed_count = 0
    uncertain_count  = 0

    for idx, finding in enumerate(all_findings):
        per_model: Dict[str, dict] = {}
        for model, verdicts in zip(active_models, per_model_verdicts):
            v = verdicts.get(idx)
            if v:
                per_model[model] = v

        genuine_models = [m for m, v in per_model.items() if v["v"] == "GENUINE"]
        fp_models      = [m for m, v in per_model.items() if v["v"] == "FALSE_POSITIVE"]
        unc_models     = [m for m, v in per_model.items() if v["v"] == "UNCERTAIN"]

        # All voting models said FP -> suppress
        if not genuine_models and fp_models and not unc_models:
            suppressed_count += 1
            continue
        # No GENUINE vote -> not a violation, just uncertain
        if not genuine_models:
            uncertain_count += 1
            continue

        clause_votes: Dict[str, int] = {}
        for m in genuine_models:
            c = per_model[m].get("c")
            if c:
                clause_votes[c] = clause_votes.get(c, 0) + 1
        clause_id = max(clause_votes, key=clause_votes.get) if clause_votes else None
        req       = req_by_id.get(clause_id) if clause_id else None

        if req is None and requirements:
            req = requirements[0]

        score      = len(genuine_models)
        confidence = CONFIDENCE_LABEL.get(score, "UNCERTAIN")

        violations.append({
            "clause_id":        req.clause_id if req else (clause_id or "UNKNOWN"),
            "clause_text":      req.clause_text if req else "",
            "severity":         req.severity if req else "medium",
            "requirement_type": req.requirement_type if req else "unknown",
            "check_id":         finding.get("check_id"),
            "resource":         finding.get("resource"),
            "file":             finding.get("file_path"),
            "line":             finding.get("file_line_range"),
            "hcl_block":        finding.get("hcl_block"),
            "consensus_score":  score,
            "confidence":       confidence,
            "models_agreed":    genuine_models,
            "models_disagreed": [m for m in active_models if m not in genuine_models],
            "per_model":        per_model,
        })

    violations.sort(key=lambda v: (
        -v["consensus_score"],
        _sev.get((v.get("severity") or "low"), 3),
    ))

    n = len(active_models)
    return {
        "models_used":      active_models,
        "violations":       violations,
        "compliance_trace": _build_trace(violations),
        "summary": {
            "total_violations": len(violations),
            "high_confidence":  sum(1 for v in violations if v["consensus_score"] == n),
            "likely":           sum(1 for v in violations if v["consensus_score"] == n - 1) if n > 1 else 0,
            "uncertain":        sum(1 for v in violations if v["consensus_score"] == 1),
            "suppressed":       suppressed_count,
            "no_verdict":       uncertain_count,
            "models_run":       n,
            "findings_scanned": len(all_findings),
        },
    }


def _build_trace(violations: List[Dict]) -> Dict[str, Any]:
    nodes, edges = {}, []
    for v in violations:
        cid  = v["clause_id"]
        line = (v.get("line") or [0])[0]
        fkey = f"{(v.get('file') or '?').replace(chr(92), '/').split('/')[-1]}:{line}"

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
            "suppressed":       0,
            "no_verdict":       0,
            "models_run":       len(models),
            "findings_scanned": 0,
        },
    }
