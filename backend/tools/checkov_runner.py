"""
Checkov Runner
--------------
Clones a GitHub repository to a temp directory and runs Checkov scans,
returning structured findings grouped by resource type.
"""

import subprocess
import tempfile
import json
import os
import sys
import shutil
from typing import List, Dict, Any

# Resolve checkov to the venv's Scripts/ directory so subprocess finds it
def _checkov_exe() -> str:
    found = shutil.which("checkov")
    if found:
        return found
    # Derive from current Python executable (works inside venv on Windows)
    scripts_dir = os.path.dirname(sys.executable)
    candidate = os.path.join(scripts_dir, "checkov.exe")
    if os.path.exists(candidate):
        return candidate
    return "checkov"  # last resort


def clone_repo(repo_url: str, github_token: str) -> str:
    """
    Clone a GitHub repository into a temporary directory.

    Args:
        repo_url: HTTPS URL of the repo (e.g. https://github.com/owner/repo).
        github_token: GitHub PAT for private repos (injected into URL).

    Returns:
        Path to the cloned directory.
    """
    tmp_dir = tempfile.mkdtemp(prefix="audittrace_")
    auth_url = (
        repo_url.replace("https://", f"https://{github_token}@")
        if github_token
        else repo_url
    )
    subprocess.run(
        ["git", "clone", "--depth", "1", auth_url, tmp_dir],
        check=True,
        capture_output=True,
    )
    return tmp_dir


def run_checkov(directory: str, framework: str = "all") -> List[Dict[str, Any]]:
    """
    Run Checkov on a local directory.

    Args:
        directory: Path to the cloned repository.
        framework: Checkov framework filter (e.g. "terraform", "cloudformation", "all").

    Returns:
        List of failed check dicts.
    """
    cmd = [
        _checkov_exe(),
        "--directory", directory,
        "--output", "json",
        "--quiet",
    ]
    if framework != "all":
        cmd += ["--framework", framework]

    result = subprocess.run(cmd, capture_output=True, text=True)

    try:
        data = json.loads(result.stdout)
        # checkov output can be a list (one entry per framework) or a single dict
        if isinstance(data, list):
            failed = []
            for section in data:
                failed.extend(section.get("results", {}).get("failed_checks", []))
            return failed
        return data.get("results", {}).get("failed_checks", [])
    except (json.JSONDecodeError, AttributeError):
        return []


def get_code_snippet(file_path: str, line_range: List[int], context: int = 3) -> str:
    """Return lines from a file with surrounding context."""
    if not os.path.exists(file_path):
        return ""
    with open(file_path, "r", errors="replace") as f:
        lines = f.readlines()
    start = max(0, line_range[0] - 1 - context)
    end = min(len(lines), line_range[-1] + context)
    return "".join(
        f"{i + start + 1}: {lines[i + start]}" for i in range(end - start)
    )
