"""
Planner Agent
-------------
Receives the parsed text of a Compliance PDF and decomposes it into
a structured list of technical requirements that can be evaluated
against live infrastructure.
"""

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel
from typing import List

from .llm import get_llm


class ComplianceRequirement(BaseModel):
    clause_id: str          # e.g. "CIS-1.4", "NIST-AC-2"
    clause_text: str        # original policy sentence
    requirement_type: str   # e.g. "encryption", "access_control", "logging", "networking"
    check_targets: List[str]  # Terraform resource types, e.g. ["aws_s3_bucket", "aws_iam_user"]
    severity: str           # "critical" | "high" | "medium" | "low"


class ComplianceRequirementList(BaseModel):
    requirements: List[ComplianceRequirement]


DECOMPOSE_PROMPT = ChatPromptTemplate.from_messages([
    ("system", (
        "You are a security compliance expert who maps policy clauses to infrastructure checks.\n"
        "Given a block of compliance policy text, extract every distinct technical requirement.\n\n"
        "For each requirement produce:\n"
        "- clause_id: a short identifier like 'CIS-1.4' or 'NIST-AC-2' derived from the text\n"
        "- clause_text: the original policy sentence (verbatim)\n"
        "- requirement_type: one of 'encryption', 'access_control', 'logging', 'networking', "
        "'monitoring', 'backup', 'patching', 'secrets_management'\n"
        "- check_targets: list of Terraform resource types this applies to "
        "(e.g. ['aws_s3_bucket', 'aws_iam_user'])\n"
        "- severity: one of 'critical', 'high', 'medium', 'low'\n\n"
        "Return ONLY requirements that are concrete and checkable against infrastructure code. "
        "Ignore purely administrative or procedural policies."
    )),
    ("human", "{policy_text}"),
])


class PlannerAgent:
    """Decomposes a compliance PDF into actionable technical requirements."""

    def __init__(self, model: str | None = None):
        self.llm = get_llm(model)

    def decompose(self, policy_text: str) -> List[ComplianceRequirement]:
        """
        Args:
            policy_text: A chunk of text extracted from the compliance PDF.

        Returns:
            List of structured ComplianceRequirement objects.
        """
        structured_llm = self.llm.with_structured_output(ComplianceRequirementList)
        messages = DECOMPOSE_PROMPT.format_messages(policy_text=policy_text)
        result: ComplianceRequirementList = structured_llm.invoke(messages)
        return result.requirements if result else []
