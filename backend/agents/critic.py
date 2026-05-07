"""
Critic Agent
------------
Receives the mapped findings from the Executor and:
  1. Generates a Compliance Trace — a graph linking code locations to
     policy clauses.
  2. Produces human-readable violation summaries.
  3. Drafts a Fix-PR patch for each violation.
"""

import os
import sys
from langchain_core.prompts import ChatPromptTemplate
from typing import List, Dict, Any
from .planner import ComplianceRequirement
from .executor import Finding
from .llm import get_llm
import networkx as nx

# Use absolute import so critic.py works both from backend/ and during tests
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from tools.checkov_runner import get_code_snippet


FIX_PROMPT = ChatPromptTemplate.from_messages([
    ("system", (
        "You are an expert infrastructure-as-code engineer. Given a policy clause "
        "and a failing Checkov check, produce a minimal unified diff patch that "
        "fixes the infrastructure code to satisfy the policy. Output only the diff, "
        "no explanations."
    )),
    ("human", (
        "Policy clause: {clause_text}\n\n"
        "Failing Checkov check: {finding}\n\n"
        "Relevant code:\n{code_snippet}"
    )),
])


class ComplianceTrace:
    """
    Directed graph where:
      - Nodes are policy clauses (type='clause') or code locations (type='code').
      - Edges are 'violates' relationships from code → clause.
    """

    def __init__(self):
        self.graph = nx.DiGraph()

    def add_violation(self, clause_id: str, file_path: str, line: int, check_id: str):
        self.graph.add_node(clause_id, type="clause", label=clause_id)
        code_node = f"{os.path.basename(file_path)}:{line}"
        self.graph.add_node(
            code_node, type="code", file=file_path, line=line, label=code_node
        )
        self.graph.add_edge(code_node, clause_id, relation="violates", check_id=check_id)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a dict for vis-network (nodes + edges arrays)."""
        return {
            "nodes": [{"id": n, **self.graph.nodes[n]} for n in self.graph.nodes],
            "edges": [
                {"from": u, "to": v, **self.graph.edges[u, v]}
                for u, v in self.graph.edges
            ],
        }


class CriticAgent:
    """Generates the compliance trace graph and fix suggestions."""

    def __init__(self, model: str | None = None):
        self.llm = get_llm(model)
        self.fix_chain = FIX_PROMPT | self.llm

    def build_trace(
        self,
        requirements: List[ComplianceRequirement],
        findings_map: Dict[str, List[Finding]],
    ) -> ComplianceTrace:
        trace = ComplianceTrace()
        for req in requirements:
            for finding in findings_map.get(req.clause_id, []):
                file_path = finding.get("file_path", "unknown")
                line = (finding.get("file_line_range") or [0])[0]
                check_id = finding.get("check_id", "")
                trace.add_violation(req.clause_id, file_path, line, check_id)
        return trace

    def suggest_fix(
        self,
        requirement: ComplianceRequirement,
        finding: Finding,
        code_snippet: str,
    ) -> str:
        response = self.fix_chain.invoke({
            "clause_text": requirement.clause_text,
            "finding": str(finding),
            "code_snippet": code_snippet or "(no code snippet available)",
        })
        return response.content

    def generate_report(
        self,
        requirements: List[ComplianceRequirement],
        findings_map: Dict[str, List[Finding]],
        repo_local_path: str = "",
    ) -> Dict[str, Any]:
        trace = self.build_trace(requirements, findings_map)
        violations = []

        for req in requirements:
            for finding in findings_map.get(req.clause_id, []):
                file_path = finding.get("file_path", "")
                line_range = finding.get("file_line_range") or [1, 1]

                # Pull real code lines from the cloned repo
                snippet = get_code_snippet(file_path, line_range) if file_path else ""
                fix = self.suggest_fix(req, finding, snippet)

                violations.append({
                    "clause_id": req.clause_id,
                    "clause_text": req.clause_text,
                    "severity": req.severity,
                    "requirement_type": req.requirement_type,
                    "check_id": finding.get("check_id"),
                    "resource": finding.get("resource"),
                    "file": file_path,
                    "line": line_range,
                    "code_snippet": snippet,
                    "suggested_fix": fix,
                })

        total = sum(len(v) for v in findings_map.values())
        return {
            "compliance_trace": trace.to_dict(),
            "violations": violations,
            "summary": {
                "total_violations": total,
                "clauses_checked": len(requirements),
                "clauses_failing": sum(1 for v in findings_map.values() if v),
                "clauses_passing": sum(1 for v in findings_map.values() if not v),
            },
        }
