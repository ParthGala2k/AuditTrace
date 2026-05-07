"""
CIS-aware policy distillation script.

Reads the full CIS AWS Foundations Benchmark PDF, detects each numbered
control (1.1, 2.1.1, etc.) as a self-contained chunk, extracts structured
requirements via a single LLM, and writes policies/<name>.json.

Usage (from project root, venv active):
    python scripts/distill_policy.py "CIS_AWS.pdf" --name cis_aws_v7

Output: policies/<name>.json  — commit this to the repo.
"""

import sys
import os
import json
import re
import argparse
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

import fitz  # PyMuPDF
from pydantic import BaseModel, Field
from typing import List
from agents.llm import get_llm

# ---------------------------------------------------------------------------
# Pydantic model for a single extracted CIS control
# ---------------------------------------------------------------------------

class CISControl(BaseModel):
    clause_id:        str            # "CIS-1.4"
    clause_text:      str            # verbatim "Ensure ..." sentence
    rationale:        str            # 1-2 sentence why it matters
    remediation_hint: str            # brief what to change in IaC
    requirement_type: str            # encryption | access_control | logging |
                                     # networking | monitoring | backup |
                                     # patching | secrets_management
    check_targets:    List[str]      # Terraform resource types, e.g. ["aws_s3_bucket"]
    level:            int            # CIS Profile Level: 1 or 2
    severity:         str            # critical | high | medium | low
    automated:        bool           # True if "(Automated)" in title


class CISControlList(BaseModel):
    controls: List[CISControl] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Step 1 — extract full text and split into per-control chunks
# ---------------------------------------------------------------------------

# Matches lines like "1.4 Ensure..." or "2.1.1 Ensure..."
_CONTROL_RE = re.compile(
    r"^(\d+\.\d+(?:\.\d+)?)\s+(Ensure\b.+|Avoid\b.+|Do not\b.+|Use\b.+|Enable\b.+)",
    re.MULTILINE | re.IGNORECASE,
)
MIN_CONTROL_CHARS = 300   # ignore very short matches (e.g. cross-references)


def extract_controls(pdf_path: str) -> List[dict]:
    """
    Read every page of the PDF, detect CIS control headings, and return
    a list of {number, title, text} dicts — one per control.
    """
    doc       = fitz.open(pdf_path)
    full_text = "\n".join(page.get_text() for page in doc)
    print(f"  Extracted {len(full_text):,} characters from {len(doc)} pages")

    matches = list(_CONTROL_RE.finditer(full_text))
    print(f"  Found {len(matches)} candidate control headings")

    controls = []
    for i, m in enumerate(matches):
        start       = m.start()
        end         = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)
        body        = full_text[start:end].strip()

        if len(body) < MIN_CONTROL_CHARS:
            continue   # skip cross-references / table-of-contents entries

        controls.append({
            "number": m.group(1),
            "title":  m.group(2).strip(),
            "text":   body,
        })

    print(f"  Kept {len(controls)} controls after length filter\n")
    return controls


# ---------------------------------------------------------------------------
# Step 2 — LLM extraction (one call per control)
# ---------------------------------------------------------------------------

SYSTEM = (
    "You are a security compliance engineer extracting structured data from a "
    "CIS AWS Foundations Benchmark control. "
    "Return only valid JSON matching the requested schema. "
    "For check_targets, list only real Terraform AWS resource type strings "
    "(e.g. 'aws_s3_bucket', 'aws_iam_user'). "
    "Derive severity: Level 1 Automated → high, Level 1 Manual → medium, "
    "Level 2 → medium, Level 2 critical wording → high."
)

HUMAN = """Extract a structured compliance requirement from this CIS control.

Control text:
{text}

Return JSON with exactly these fields:
- clause_id: "CIS-{number}" (use the control number above)
- clause_text: the main "Ensure ..." requirement sentence verbatim
- rationale: 1-2 sentences on why this matters
- remediation_hint: brief description of what Terraform resource/attribute to fix
- requirement_type: one of [encryption, access_control, logging, networking, monitoring, backup, patching, secrets_management]
- check_targets: list of Terraform resource type strings
- level: integer 1 or 2 (from "Profile Applicability")
- severity: one of [critical, high, medium, low]
- automated: true if "(Automated)" appears in the title, else false
"""


def extract_one(llm, control: dict, retries: int = 2) -> CISControl | None:
    """Run structured LLM extraction for a single control. Retries on failure."""

    class _Wrapper(BaseModel):
        clause_id:        str
        clause_text:      str
        rationale:        str
        remediation_hint: str
        requirement_type: str
        check_targets:    List[str]
        level:            int
        severity:         str
        automated:        bool

    structured = llm.with_structured_output(_Wrapper)
    prompt     = HUMAN.format(text=control["text"][:4000], number=control["number"])

    for attempt in range(retries + 1):
        try:
            result = structured.invoke([
                {"role": "system",  "content": SYSTEM},
                {"role": "user",    "content": prompt},
            ])
            # Force clause_id format
            if not result.clause_id.startswith("CIS-"):
                result.clause_id = f"CIS-{control['number']}"
            return CISControl(**result.model_dump())
        except Exception as e:
            if attempt < retries:
                time.sleep(2)
            else:
                print(f"    ERROR on {control['number']}: {e}")
                return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf",     help="Path to the CIS AWS Foundations Benchmark PDF")
    parser.add_argument("--name",  required=True, help="Policy key, e.g. cis_aws_v7")
    parser.add_argument("--model", default="openai/gpt-4o-mini")
    args = parser.parse_args()

    out_dir  = os.path.join(os.path.dirname(__file__), "..", "..", "policies")
    out_path = os.path.join(out_dir, f"{args.name}.json")
    os.makedirs(out_dir, exist_ok=True)

    if os.path.exists(out_path):
        print(f"Policy '{args.name}' already exists at {out_path}.")
        print("Delete it to re-distill.")
        sys.exit(0)

    print(f"Model : {args.model}")
    print(f"PDF   : {args.pdf}\n")

    # Step 1 — chunk by control
    print("Step 1 — extracting controls from PDF...")
    controls = extract_controls(args.pdf)

    # Step 2 — LLM extraction
    print(f"Step 2 — extracting requirements ({len(controls)} controls)...\n")
    llm          = get_llm(args.model, temperature=0)
    requirements = []
    seen_ids     = set()
    failed       = 0

    for i, ctrl in enumerate(controls):
        print(f"  [{i+1:>3}/{len(controls)}] {ctrl['number']:>6}  {ctrl['title'][:55]}")
        result = extract_one(llm, ctrl)

        if result is None:
            failed += 1
            continue

        if result.clause_id in seen_ids:
            # Duplicate — append sub-index to keep it
            result.clause_id = f"{result.clause_id}b"

        seen_ids.add(result.clause_id)
        requirements.append(result)

    # Step 3 — save
    payload = {
        "name":              args.name,
        "source_pdf":        os.path.basename(args.pdf),
        "model_used":        args.model,
        "requirement_count": len(requirements),
        "failed_extractions": failed,
        "requirements":      [r.model_dump() for r in requirements],
    }

    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2)

    print(f"\nDone.")
    print(f"  Extracted : {len(requirements)} requirements")
    print(f"  Failed    : {failed}")
    print(f"  Saved to  : {out_path}")
    print(f"\nCommit policies/ to git. The /audit endpoint loads it directly.")


if __name__ == "__main__":
    main()
