"""Audit-trail persistence.

DynamoDB is the only backend (see db_dynamo.py for the table layout).
This module keeps the `db` import path that app.py uses. Configure it with
JUDGE_DYNAMODB_TABLE and AWS_REGION plus AWS credentials.
"""

from __future__ import annotations

from db_dynamo import load_all_results, load_latest_run, save_results

__all__ = ["load_all_results", "load_latest_run", "save_results"]
