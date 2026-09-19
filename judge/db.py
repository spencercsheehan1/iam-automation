"""Audit-trail persistence — backend dispatcher.

Selects the storage backend via JUDGE_DB_BACKEND:
  sqlite   (default) — local file, used for local dev / sample mode. See
           db_sqlite.py.
  dynamodb — used in production (a container's local disk doesn't
           survive restarts/redeploys or scale past one instance). See
           db_dynamo.py.

Both backends expose the same three functions, so app.py and evaluator
callers don't need to know which one is active.
"""

from __future__ import annotations

import os

from evaluator import EvaluationResult


def _backend():
    name = os.environ.get("JUDGE_DB_BACKEND", "sqlite").strip().lower()
    if name == "sqlite":
        import db_sqlite

        return db_sqlite
    if name == "dynamodb":
        import db_dynamo

        return db_dynamo
    raise ValueError(f"Unknown JUDGE_DB_BACKEND: {name!r} (expected 'sqlite' or 'dynamodb')")


def save_results(results: list[EvaluationResult]) -> None:
    _backend().save_results(results)


def load_all_results() -> list[dict]:
    return _backend().load_all_results()


def load_latest_run() -> list[dict]:
    return _backend().load_latest_run()
