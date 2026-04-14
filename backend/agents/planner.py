"""
Planner Agent
-------------
Receives the parsed text of a Compliance PDF and decomposes it into
a structured list of technical requirements that can be evaluated
against live infrastructure.
"""

from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from pydantic import BaseModel
from typing import List


class ComplianceRequirement(BaseModel):
    clause_id: str          # e.g. "SOC2-CC6.1"
    clause_text: str        # original policy sentence
    requirement_type: str   # e.g. "encryption", "access_control", "logging"
    check_targets: List[str]  # e.g. ["s3_bucket", "iam_policy"]
    severity: str           # "critical" | "high" | "medium" | "low"


DECOMPOSE_PROMPT = ChatPromptTemplate.from_messages([
    ("system", (
        "You are a security compliance expert. Given a block of compliance policy text, "
        "extract every distinct technical requirement. For each requirement, output a JSON "
        "object with fields: clause_id, clause_text, requirement_type, check_targets, severity."
    )),
    ("human", "{policy_text}"),
])


class PlannerAgent:
    """Decomposes a compliance PDF into actionable technical requirements."""

    def __init__(self, model: str = "gpt-4o-mini"):
        self.llm = ChatOpenAI(model=model, temperature=0)
        self.chain = DECOMPOSE_PROMPT | self.llm

    def decompose(self, policy_text: str) -> List[ComplianceRequirement]:
        """
        Args:
            policy_text: Raw text extracted from the compliance PDF.

        Returns:
            List of structured ComplianceRequirement objects.
        """
        # TODO: implement structured output parsing with JsonOutputParser
        # and chunk large PDFs before processing
        response = self.chain.invoke({"policy_text": policy_text})
        # Placeholder: return empty list until parser is wired in
        return []
