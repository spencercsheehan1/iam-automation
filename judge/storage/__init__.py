"""Audit-trail persistence.

DynamoDB is the only backend (see dynamodb.py for the table layout).
Configure it with JUDGE_DYNAMODB_TABLE and AWS_REGION plus AWS credentials.
"""

from __future__ import annotations

from storage.dynamodb import load_all_results, load_latest_run, save_results

__all__ = ["load_all_results", "load_latest_run", "save_results"]
