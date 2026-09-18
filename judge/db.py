"""SQLite persistence for evaluation results (the audit trail).

Append-only: every run of Judge inserts new rows, never overwrites past
evaluations, so "inspect previous results" (PRD §15.11) always has
history to show.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path

from evaluator import EvaluationResult

DEFAULT_DB_PATH = Path(__file__).parent / "judge.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS evaluations (
    evaluation_id TEXT PRIMARY KEY,
    user TEXT NOT NULL,
    role TEXT NOT NULL,
    decision TEXT NOT NULL,
    reason TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    evaluated_at TEXT NOT NULL,
    employee_attributes_used TEXT
);
"""


def get_connection(path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.execute(SCHEMA)
    conn.commit()
    return conn


def save_results(results: list[EvaluationResult], path: Path = DEFAULT_DB_PATH) -> None:
    conn = get_connection(path)
    try:
        conn.executemany(
            """
            INSERT INTO evaluations
                (evaluation_id, user, role, decision, reason, policy_version,
                 evaluated_at, employee_attributes_used)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    str(uuid.uuid4()),
                    r.user,
                    r.role,
                    r.decision,
                    r.reason,
                    r.policy_version,
                    r.evaluated_at,
                    json.dumps(r.employee_attributes_used) if r.employee_attributes_used else None,
                )
                for r in results
            ],
        )
        conn.commit()
    finally:
        conn.close()


def load_all_results(path: Path = DEFAULT_DB_PATH) -> list[dict]:
    """Return every stored evaluation, most recent first."""
    conn = get_connection(path)
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM evaluations ORDER BY evaluated_at DESC, rowid DESC"
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def load_latest_run(path: Path = DEFAULT_DB_PATH) -> list[dict]:
    """Return only the rows from the most recent evaluation timestamp."""
    all_rows = load_all_results(path)
    if not all_rows:
        return []
    latest_ts = all_rows[0]["evaluated_at"]
    return [row for row in all_rows if row["evaluated_at"] == latest_ts]
