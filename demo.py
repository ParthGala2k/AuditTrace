"""
AuditTrace demo script.

Usage:
    # Step 1 — distill the PDF once (only needed once ever):
    python scripts/distill_policy.py "CIS_AWS.pdf" --name cis_aws_v7

    # Step 2 — start the backend:
    cd backend && uvicorn main:app --reload

    # Step 3 — run the audit (no PDF needed):
    python demo.py --policy cis_aws_v7 --repo https://github.com/bridgecrewio/terragoat
"""

import sys
import json
import argparse
import requests

API_URL = "http://localhost:8000/audit"
CONFIDENCE_TAG = {"HIGH": "!!!", "LIKELY": "!! ", "UNCERTAIN": "?  "}


def run(policy: str, repo_url: str):
    print(f"\nRunning consensus audit...")
    print(f"  Policy : {policy}")
    print(f"  Repo   : {repo_url}\n")

    resp = requests.post(
        API_URL,
        data={"repo_url": repo_url, "policy": policy},
        timeout=600,
    )

    if not resp.ok:
        print(f"ERROR {resp.status_code}: {resp.text}")
        sys.exit(1)

    report  = resp.json()
    summary = report.get("summary", {})

    print("=" * 65)
    print("AUDIT SUMMARY")
    print("=" * 65)
    print(f"  Version          : v{report.get('version')}")
    print(f"  Compliance score : {report.get('compliance_score')}%")
    print(f"  Models run       : {summary.get('models_run')}")
    print(f"  Total violations : {summary.get('total_violations')}")
    print(f"  High confidence  : {summary.get('high_confidence')}  (all models agree)")
    print(f"  Likely           : {summary.get('likely')}  (2/3 models agree)")
    print(f"  Uncertain        : {summary.get('uncertain')}  (1/3 models flagged)")

    print("\nTOP VIOLATIONS")
    print("=" * 65)
    for v in report.get("violations", [])[:15]:
        tag = CONFIDENCE_TAG.get(v.get("confidence", ""), "   ")
        sev = v.get("severity", "?").upper()[:8]
        print(f"  {tag} [{sev:8}] {v.get('clause_id')} — {v.get('check_id')}")
        print(f"         {v.get('file')}:{(v.get('line') or ['?'])[0]}")
        print(f"         confidence={v.get('confidence')}  agreed={v.get('models_agreed')}")
        print()

    out = "report.json"
    with open(out, "w") as f:
        json.dump(report, f, indent=2)
    print(f"Full report saved → {out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", required=True, help="Policy name, e.g. cis_aws_v7")
    parser.add_argument("--repo",   required=True, help="GitHub repo URL")
    args = parser.parse_args()
    run(policy=args.policy, repo_url=args.repo)
