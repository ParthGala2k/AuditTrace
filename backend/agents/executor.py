"""
Executor Agent
--------------
Takes a list of ComplianceRequirements from the Planner and runs
infrastructure scanning tools (Checkov, Terraform Plan) against the
connected GitHub repository. Returns raw findings per requirement.
"""

import subprocess
import json
import tempfile
import os
from typing import List, Dict, Any
from .planner import ComplianceRequirement


class Finding(dict):
    """
    A single Checkov or Terraform finding.
    Keys: check_id, resource, file_path, line_range, status, message
    """


class ExecutorAgent:
    """Runs policy-as-code scanners against cloned infrastructure code."""

    def __init__(self, repo_local_path: str):
        """
        Args:
            repo_local_path: Local path to the cloned GitHub repository.
        """
        self.repo_path = repo_local_path

    def run_checkov(self) -> List[Finding]:
        """Run Checkov against the repository and return parsed findings."""
        result = subprocess.run(
            [
                "checkov",
                "--directory", self.repo_path,
                "--output", "json",
                "--quiet",
            ],
            capture_output=True,
            text=True,
        )
        try:
            data = json.loads(result.stdout)
            failed = data.get("results", {}).get("failed_checks", [])
            return [Finding(f) for f in failed]
        except json.JSONDecodeError:
            return []

    def run_terraform_plan(self) -> Dict[str, Any]:
        """
        Run `terraform plan -json` inside any terraform directory found.
        Returns the parsed plan output.
        """
        # TODO: detect terraform dirs, run init + plan, parse output
        return {}

    def execute(self, requirements: List[ComplianceRequirement]) -> Dict[str, List[Finding]]:
        """
        Map each requirement to the relevant Checkov findings.

        Returns:
            Dict keyed by clause_id → list of matching findings.
        """
        all_findings = self.run_checkov()
        mapped: Dict[str, List[Finding]] = {req.clause_id: [] for req in requirements}

        for req in requirements:
            for finding in all_findings:
                # TODO: implement semantic matching between finding and requirement
                # using embeddings similarity instead of keyword match
                check_id: str = finding.get("check_id", "")
                if any(target in check_id.lower() for target in req.check_targets):
                    mapped[req.clause_id].append(finding)

        return mapped
