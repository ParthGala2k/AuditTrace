"""
Policy Store
------------
Caches LLM-extracted compliance requirements on disk so a PDF is only
parsed once. Subsequent audits load from the cache instantly.

Cache location: backend/policies/<sha256_of_pdf>.json
"""

import hashlib
import json
import os
from typing import List, Optional

from agents.planner import ComplianceRequirement

POLICIES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "policies")


def _pdf_hash(pdf_path: str) -> str:
    h = hashlib.sha256()
    with open(pdf_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:16]  # 16 hex chars is plenty for a filename


def cache_path(pdf_path: str) -> str:
    os.makedirs(POLICIES_DIR, exist_ok=True)
    return os.path.join(POLICIES_DIR, f"{_pdf_hash(pdf_path)}.json")


def load_cached(pdf_path: str) -> Optional[List[ComplianceRequirement]]:
    """Return cached requirements if they exist, else None."""
    path = cache_path(pdf_path)
    if not os.path.exists(path):
        return None
    with open(path) as f:
        data = json.load(f)
    reqs = [ComplianceRequirement(**r) for r in data["requirements"]]
    print(f"[policy_store] loaded {len(reqs)} requirements from cache ({path})")
    return reqs


def save_cache(pdf_path: str, requirements: List[ComplianceRequirement], meta: dict = None):
    """Persist extracted requirements to disk."""
    path = cache_path(pdf_path)
    payload = {
        "pdf_hash":    _pdf_hash(pdf_path),
        "meta":        meta or {},
        "requirements": [r.model_dump() for r in requirements],
    }
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"[policy_store] saved {len(requirements)} requirements → {path}")


def list_cached() -> List[dict]:
    """Return metadata for all cached policy files."""
    os.makedirs(POLICIES_DIR, exist_ok=True)
    result = []
    for fname in os.listdir(POLICIES_DIR):
        if not fname.endswith(".json"):
            continue
        with open(os.path.join(POLICIES_DIR, fname)) as f:
            data = json.load(f)
        result.append({
            "hash":             data.get("pdf_hash"),
            "meta":             data.get("meta", {}),
            "requirement_count": len(data.get("requirements", [])),
            "file":             fname,
        })
    return result
