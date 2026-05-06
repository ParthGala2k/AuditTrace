"""
Executor Agent
--------------
Takes a list of ComplianceRequirements from the Planner and runs
infrastructure scanning tools (Checkov) against the connected GitHub
repository. Returns raw findings per requirement.
"""

import subprocess
import json
from typing import List, Dict, Any
from .planner import ComplianceRequirement

# Terraform resource type → Checkov check_id keyword mappings
# Used to improve finding→requirement matching beyond plain keyword search.
RESOURCE_TO_CHECK_KEYWORDS: Dict[str, List[str]] = {
    "aws_s3_bucket": ["s3", "CKV_AWS_20", "CKV_AWS_19", "CKV_AWS_18"],
    "aws_iam_user": ["iam_user", "CKV_AWS_9", "CKV_AWS_10"],
    "aws_iam_policy": ["iam_policy", "CKV_AWS_40"],
    "aws_security_group": ["security_group", "CKV_AWS_24", "CKV_AWS_25"],
    "aws_rds_instance": ["rds", "CKV_AWS_16", "CKV_AWS_17"],
    "aws_db_instance": ["rds", "CKV_AWS_16", "CKV_AWS_17"],
    "aws_ebs_volume": ["ebs", "CKV_AWS_3"],
    "aws_kms_key": ["kms", "CKV_AWS_7"],
    "aws_cloudtrail": ["cloudtrail", "CKV_AWS_35"],
    "aws_vpc": ["vpc", "CKV_AWS_2"],
    "aws_lambda_function": ["lambda", "CKV_AWS_45"],
    "aws_eks_cluster": ["eks", "CKV_AWS_39"],
    "aws_elb": ["elb", "alb", "CKV_AWS_91"],
    "aws_alb": ["alb", "CKV_AWS_91"],
    "aws_sns_topic": ["sns", "CKV_AWS_26"],
    "aws_sqs_queue": ["sqs", "CKV_AWS_27"],
    "aws_ecr_repository": ["ecr", "CKV_AWS_32"],
    "aws_cloudwatch_log_group": ["cloudwatch", "CKV_AWS_66"],
}


class Finding(dict):
    """
    A single Checkov finding.
    Keys: check_id, check_type, resource, file_path, file_line_range,
          check_result, resource_address
    """


class ExecutorAgent:
    """Runs Checkov against a cloned infrastructure repository."""

    def __init__(self, repo_local_path: str):
        self.repo_path = repo_local_path

    def run_checkov(self) -> List[Finding]:
        """Run Checkov against the repository and return all failed checks."""
        result = subprocess.run(
            [
                "checkov",
                "--directory", self.repo_path,
                "--output", "json",
                "--quiet",
                "--compact",
            ],
            capture_output=True,
            text=True,
        )
        try:
            data = json.loads(result.stdout)
            # Checkov output is a list when multiple frameworks are found
            if isinstance(data, list):
                failed = []
                for section in data:
                    failed.extend(section.get("results", {}).get("failed_checks", []))
                return [Finding(f) for f in failed]
            return [Finding(f) for f in data.get("results", {}).get("failed_checks", [])]
        except (json.JSONDecodeError, AttributeError):
            return []

    def _matches(self, finding: Finding, req: ComplianceRequirement) -> bool:
        """Return True if a Checkov finding is relevant to a compliance requirement."""
        check_id: str = finding.get("check_id", "").lower()
        resource: str = finding.get("resource", "").lower()

        for target in req.check_targets:
            target_lower = target.lower()
            # Direct resource type match
            if target_lower in resource:
                return True
            # Keyword match against check_id
            if target_lower in check_id:
                return True
            # Extended keyword lookup
            for keyword in RESOURCE_TO_CHECK_KEYWORDS.get(target_lower, []):
                if keyword.lower() in check_id or keyword.lower() in resource:
                    return True

        return False

    def execute(self, requirements: List[ComplianceRequirement]) -> Dict[str, List[Finding]]:
        """
        Map each compliance requirement to the Checkov findings it triggers.

        Returns:
            Dict keyed by clause_id → list of matching findings.
        """
        all_findings = self.run_checkov()
        mapped: Dict[str, List[Finding]] = {req.clause_id: [] for req in requirements}

        for req in requirements:
            for finding in all_findings:
                if self._matches(finding, req):
                    mapped[req.clause_id].append(finding)

        return mapped
