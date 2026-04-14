"""
Critic Agent
------------
Receives the mapped findings from the Executor and:
  1. Generates a Compliance Trace — a graph linking code locations to
     policy clauses.
  2. Produces human-readable violation summaries.
  3. Drafts a Fix-PR patch for each violation.
"""

from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from typing import List, Dict, Any
from .planner import ComplianceRequirement
from .executor import Finding
import networkx as nx


FIX_PROMPT = ChatPromptTemplate.from_messages([
    ("system", (
        "You are an expert infrastructure-as-code engineer. Given a policy clause "
        "and a failing Checkov check, produce a minimal unified diff patch that "
        "fixes the infrastructure code to satisfy the policy. Output only the diff."
    )),
    ("human", (
        "Policy clause: {clause_text}\n\n"
        "Failing check:\n{finding}\n\n"
        "Relevant code snippet:\n{code_snippet}"
    )),
])


class ComplianceTrace:
    """
    A directed graph where:
      - Nodes are either policy clauses or code locations (file:line).
      - Edges represent 'violates' relationships.
    """

    def __init__(self):
        self.graph = nx.DiGraph()

    def add_violation(self, clause_id: str, file_path: str, line: int, message: str):
        self.graph.add_node(clause_id, type="clause")
        code_node = f"{file_path}:{line}"
        self.graph.add_node(code_node, type="code", file=file_path, line=line)
        self.graph.add_edge(code_node, clause_id, relation="violates", message=message)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize graph to a dict suitable for the frontend (vis.js / D3)."""
        return {
            "nodes": [
                {"id": n, **self.graph.nodes[n]}
                for n in self.graph.nodes
            ],
            "edges": [
                {"from": u, "to": v, **self.graph.edges[u, v]}
                for u, v in self.graph.edges
            ],
        }


class CriticAgent:
    """Generates compliance traces and fix suggestions."""

    def __init__(self, model: str = "gpt-4o"):
        self.llm = ChatOpenAI(model=model, temperature=0)
        self.fix_chain = FIX_PROMPT | self.llm

    def build_trace(
        self,
        requirements: List[ComplianceRequirement],
        findings_map: Dict[str, List[Finding]],
    ) -> ComplianceTrace:
        """Build the compliance trace graph from mapped findings."""
        trace = ComplianceTrace()
        for req in requirements:
            for finding in findings_map.get(req.clause_id, []):
                file_path = finding.get("file_path", "unknown")
                line = finding.get("file_line_range", [0])[0]
                message = finding.get("check_result", {}).get("result", "FAILED")
                trace.add_violation(req.clause_id, file_path, line, message)
        return trace

    def suggest_fix(
        self,
        requirement: ComplianceRequirement,
        finding: Finding,
        code_snippet: str,
    ) -> str:
        """Return a unified diff patch that fixes the violation."""
        response = self.fix_chain.invoke({
            "clause_text": requirement.clause_text,
            "finding": str(finding),
            "code_snippet": code_snippet,
        })
        return response.content

    def generate_report(
        self,
        requirements: List[ComplianceRequirement],
        findings_map: Dict[str, List[Finding]],
    ) -> Dict[str, Any]:
        """
        Full report output:
          - compliance_trace: graph dict for the frontend
          - violations: list of {clause, finding, suggested_fix}
          - summary: overall pass/fail counts
        """
        trace = self.build_trace(requirements, findings_map)
        violations = []
        for req in requirements:
            for finding in findings_map.get(req.clause_id, []):
                # TODO: extract real code snippet from the repo
                fix = self.suggest_fix(req, finding, code_snippet="")
                violations.append({
                    "clause_id": req.clause_id,
                    "clause_text": req.clause_text,
                    "severity": req.severity,
                    "file": finding.get("file_path"),
                    "line": finding.get("file_line_range"),
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
            },
        }
