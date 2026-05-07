"""
SQLite persistence layer for versioned audit history.
"""

import sqlite3
import json
import os
from datetime import datetime
from typing import Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "audittrace.db")


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS projects (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                repo_url    TEXT UNIQUE NOT NULL,
                created_at  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS audits (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id       INTEGER NOT NULL REFERENCES projects(id),
                version          INTEGER NOT NULL,
                timestamp        TEXT NOT NULL,
                model_used       TEXT,
                compliance_score REAL,
                clauses_checked  INTEGER,
                clauses_failing  INTEGER,
                total_violations INTEGER,
                report_json      TEXT NOT NULL
            );
        """)


def _severity_weight(severity: str) -> float:
    return {"critical": 4.0, "high": 3.0, "medium": 2.0, "low": 1.0}.get(
        severity.lower(), 1.0
    )


def compute_compliance_score(report: dict) -> float:
    """
    Weighted compliance score 0–100.
    Each failing clause is penalized proportional to its max violation severity.
    """
    violations = report.get("violations", [])
    summary = report.get("summary", {})
    clauses_checked = summary.get("clauses_checked", 0)
    if clauses_checked == 0:
        return 100.0

    # Group violations by clause, take max severity weight per clause
    clause_weights: dict[str, float] = {}
    for v in violations:
        cid = v.get("clause_id", "")
        w = _severity_weight(v.get("severity", "low"))
        clause_weights[cid] = max(clause_weights.get(cid, 0), w)

    max_possible = clauses_checked * 4.0  # all critical
    penalty = sum(clause_weights.values())
    score = max(0.0, (1 - penalty / max_possible) * 100)
    return round(score, 2)


def get_or_create_project(repo_url: str) -> int:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM projects WHERE repo_url = ?", (repo_url,)
        ).fetchone()
        if row:
            return row["id"]
        cur = conn.execute(
            "INSERT INTO projects (repo_url, created_at) VALUES (?, ?)",
            (repo_url, datetime.utcnow().isoformat()),
        )
        return cur.lastrowid


def next_version(project_id: int) -> int:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT MAX(version) as v FROM audits WHERE project_id = ?",
            (project_id,),
        ).fetchone()
        return (row["v"] or 0) + 1


def save_audit(repo_url: str, model: str, report: dict) -> dict:
    """Persist an audit and return {project_id, version, compliance_score}."""
    init_db()
    score = compute_compliance_score(report)
    summary = report.get("summary", {})
    project_id = get_or_create_project(repo_url)
    version = next_version(project_id)

    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO audits
                (project_id, version, timestamp, model_used, compliance_score,
                 clauses_checked, clauses_failing, total_violations, report_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                version,
                datetime.utcnow().isoformat(),
                model,
                score,
                summary.get("clauses_checked", 0),
                summary.get("clauses_failing", 0),
                summary.get("total_violations", 0),
                json.dumps(report),
            ),
        )

    return {"project_id": project_id, "version": version, "compliance_score": score}


def get_history(repo_url: str) -> list[dict]:
    """Return all audit versions for a repo, oldest first."""
    init_db()
    with get_conn() as conn:
        project = conn.execute(
            "SELECT id FROM projects WHERE repo_url = ?", (repo_url,)
        ).fetchone()
        if not project:
            return []
        rows = conn.execute(
            """
            SELECT version, timestamp, model_used, compliance_score,
                   clauses_checked, clauses_failing, total_violations
            FROM audits WHERE project_id = ?
            ORDER BY version ASC
            """,
            (project["id"],),
        ).fetchall()
        return [dict(r) for r in rows]


def get_audit_report(repo_url: str, version: int) -> Optional[dict]:
    """Return the full report JSON for a specific version."""
    init_db()
    with get_conn() as conn:
        project = conn.execute(
            "SELECT id FROM projects WHERE repo_url = ?", (repo_url,)
        ).fetchone()
        if not project:
            return None
        row = conn.execute(
            "SELECT report_json FROM audits WHERE project_id = ? AND version = ?",
            (project["id"], version),
        ).fetchone()
        return json.loads(row["report_json"]) if row else None
